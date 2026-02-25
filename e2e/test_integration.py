'''
E2E integration tests for djmgmt.

Requires the Docker environment to be running:
    docker-compose -f e2e/docker-compose.test.yml up -d

Run from within the djmgmt-test container:
    docker-compose -f e2e/docker-compose.test.yml run --rm djmgmt-test

Or from the host with environment variables set:
    NAVIDROME_HOST=localhost NAVIDROME_PASSWORD=test_password_123 \
    python -m unittest e2e.test_integration -v
'''

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from djmgmt import common, config, constants, encode, music, subsonic_client, sync
from djmgmt.common import FileMapping


def setUpModule() -> None:
    common.configure_log('test_integration')

_SCAN_TIMEOUT_S = 30

# Minimal Rekordbox XML template matching state/collection-template.xml
_COLLECTION_TEMPLATE = '''\
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="0">
    </COLLECTION>
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="3">
            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="dynamic" Type="0" KeyType="0" Entries="2">
                <NODE Name="unplayed" Type="1" KeyType="0" Entries="0"/>
                <NODE Name="played" Type="1" KeyType="0" Entries="0"/>
            </NODE>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>
'''


def _wait_for_scan_complete(test: unittest.TestCase) -> None:
    '''Polls GET_SCAN_STATUS until scanning is false or _SCAN_TIMEOUT_S is exceeded.'''
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        test.assertLess(elapsed, _SCAN_TIMEOUT_S, 'scan did not complete within timeout')

        response = subsonic_client.call_endpoint(subsonic_client.API.GET_SCAN_STATUS)
        content = subsonic_client.handle_response(response, subsonic_client.API.GET_SCAN_STATUS)
        assert content is not None, 'expected non-None scan status response'

        if content[subsonic_client.API.RESPONSE_SCAN_STATUS] == 'false':
            break
        time.sleep(1)


def _setup_state_dir() -> None:
    '''Creates all state directories and files required by sync/library modules.'''
    output_dir = os.path.join(str(config.STATE_DIR), 'output')
    for d in [str(config.STATE_DIR), output_dir]:
        os.makedirs(d, exist_ok=True)

    # collection template is loaded internally by merge_collections and record_collection
    with open(config.COLLECTION_PATH_TEMPLATE, 'w', encoding='utf-8') as f:
        f.write(_COLLECTION_TEMPLATE)

    # processed collection is the secondary input to merge_collections
    with open(config.COLLECTION_PATH_PROCESSED, 'w', encoding='utf-8') as f:
        f.write(_COLLECTION_TEMPLATE)

    # empty sync state so SavedDateContext.load() doesn't crash and batches are not skipped
    open(config.SYNC_STATE_PATH, 'w').close()


def _generate_tagged_mp3(path: str) -> None:
    '''Generates a 1-second silent MP3 with title and artist tags at the given path.
    Tags.load requires at least one of title/artist to be non-None.'''
    subprocess.run(
        ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
         '-t', '1', '-acodec', 'libmp3lame', '-q:a', '9',
         '-metadata', 'title=Test Track', '-metadata', 'artist=Test Artist',
         path, '-y'],
        check=True, capture_output=True
    )


class TestToolchainHealthcheck(unittest.TestCase):
    '''Verifies that system tools installed in Dockerfile.test are present and callable.'''

    def test_rsync_available(self) -> None:
        result = subprocess.run(['rsync', '--version'], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_ffmpeg_available(self) -> None:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        self.assertEqual(result.returncode, 0)


class TestDependencyHealthcheck(unittest.TestCase):
    '''Sanity checks that all external services are reachable before running functional tests.'''

    def test_navidrome_reachable(self) -> None:
        response = subsonic_client.call_endpoint(subsonic_client.API.PING)
        self.assertEqual(response.status_code, 200)
        content = subsonic_client.handle_response(response, subsonic_client.API.PING)
        assert content is not None, 'expected non-None ping response'
        self.assertEqual(content['status'], 'ok')

    def test_rsync_daemon_reachable(self) -> None:
        self.assertTrue(sync.rsync_healthcheck())


class TestSubsonicScan(unittest.TestCase):
    '''Verifies that a Navidrome library scan can be triggered and completes successfully.'''

    def test_scan_completes(self) -> None:
        response = subsonic_client.call_endpoint(subsonic_client.API.START_SCAN)
        self.assertEqual(response.status_code, 200)
        _wait_for_scan_complete(self)


class TestRsyncTransfer(unittest.TestCase):
    '''Verifies that a file can be transferred to the rsync daemon.'''

    def test_file_transfer(self) -> None:
        fd, source_path = tempfile.mkstemp(suffix='.txt', prefix='djmgmt_e2e_')
        try:
            os.write(fd, b'e2e test transfer')
            os.close(fd)

            returncode, _ = sync.transfer_files(source_path, config.RSYNC_URL, config.RSYNC_MODULE)
            self.assertEqual(returncode, 0)
        finally:
            os.unlink(source_path)


class TestSyncWorkflow(unittest.TestCase):
    '''Verifies the full sync pipeline: encode → rsync transfer → Navidrome scan.'''

    def setUp(self) -> None:
        _setup_state_dir()

    def test_encode_transfer_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_path = os.path.join(tmpdir, 'input.wav')
            dest_path = os.path.join(tmpdir, 'output.mp3')

            # generate a 1-second silent WAV as the encode source
            subprocess.run(
                ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                 '-t', '1', source_path, '-y'],
                check=True, capture_output=True
            )

            # encode to MP3
            mappings: list[FileMapping] = [(source_path, dest_path)]
            asyncio.run(encode.encode_lossy(mappings, '.mp3'))
            self.assertTrue(os.path.exists(dest_path), 'encoded MP3 was not created')

            # transfer encoded file to rsync daemon
            returncode, _ = sync.transfer_files(dest_path, config.RSYNC_URL, config.RSYNC_MODULE)
            self.assertEqual(returncode, 0)

            # trigger scan and wait for completion
            response = subsonic_client.call_endpoint(subsonic_client.API.START_SCAN)
            self.assertEqual(response.status_code, 200)
            _wait_for_scan_complete(self)

    def test_run_music(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_path = os.path.join(tmpdir, 'input.wav')
            # dest must have a date-context path so sync_mappings can batch and
            # transform_implied_path can build the rsync source path
            dest_path = os.path.join(tmpdir, '2020', '01 january', '15', 'input.wav')

            # generate a 1-second silent WAV as the encode source
            subprocess.run(
                ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                 '-t', '1', source_path, '-y'],
                check=True, capture_output=True
            )

            mappings: list[FileMapping] = [(source_path, dest_path)]
            result = sync.run_music(mappings)

            self.assertListEqual(result.mappings, mappings)
            self.assertEqual(len(result.batches), 1)
            self.assertEqual(result.batches[0].files_processed, 1)
            self.assertTrue(result.batches[0].success)


class TestUpdateLibrary(unittest.TestCase):
    '''Verifies the full music.update_library pipeline:
    process → record collection → create sync mappings → run_music.'''

    def setUp(self) -> None:
        _setup_state_dir()

    def test_update_library(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            new_music_dir = os.path.join(tmpdir, 'new_music')
            library_dir = os.path.join(tmpdir, 'library')
            client_mirror_dir = os.path.join(tmpdir, 'mirror')
            collection_export_dir = os.path.join(tmpdir, 'exports')

            for d in [new_music_dir, library_dir, client_mirror_dir, collection_export_dir]:
                os.makedirs(d)

            # generate a tagged MP3 — Tags.load requires title or artist to be non-None
            source_path = os.path.join(new_music_dir, 'test-track.mp3')
            _generate_tagged_mp3(source_path)

            # provide an export XML so find_latest_file returns a valid path for merge_collections
            shutil.copy(config.COLLECTION_PATH_TEMPLATE, os.path.join(collection_export_dir, 'export.xml'))

            result = music.update_library(
                new_music_dir_path=new_music_dir,
                library_path=library_dir,
                client_mirror_path=client_mirror_dir,
                collection_export_dir_path=collection_export_dir,
                processed_collection_path=config.COLLECTION_PATH_PROCESSED,
                merged_collection_path=config.COLLECTION_PATH_MERGED,
                valid_extensions=constants.EXTENSIONS,
                prefix_hints=music.PREFIX_HINTS,
            )

            # one track was added to the collection and _pruned playlist
            self.assertEqual(result.record_result.tracks_added, 1)
            # one sync batch (one date context: today) ran and succeeded
            self.assertEqual(len(result.sync_result.batches), 1)
            self.assertEqual(result.sync_result.batches[0].files_processed, 1)
            self.assertTrue(result.sync_result.batches[0].success)


if __name__ == '__main__':
    unittest.main()
