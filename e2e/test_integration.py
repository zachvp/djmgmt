'''
E2E integration tests for djmgmt.

Run tests from host:
    docker compose -f e2e/docker-compose.test.yml run --rm djmgmt-test
    docker compose -f e2e/docker-compose.test.yml run --build --rm djmgmt-test
'''

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import unittest

import fixture_generator
from djmgmt import common, config, constants, encode, library, music, subsonic_client, sync
from djmgmt.common import FileMapping

_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), 'fixtures/manifests/dummy-files.json')


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


class TestSweep(unittest.TestCase):
    '''Verifies music.sweep() moves music files and valid archives, rejects noise and invalid archives.'''

    def test_sweep(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            dest_dir = os.path.join(tmpdir, 'swept')
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)

            swept = music.sweep(source_dir, dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)

            # correct number of discrete items moved (music files + accepted archives)
            self.assertEqual(len(swept), gen.expected_swept_count)

            # all swept files exist at destination
            for _, dest in swept:
                self.assertTrue(os.path.exists(dest))

            # rejected archives were not swept
            swept_names = {os.path.basename(dest) for _, dest in swept}
            for name in gen.rejected_names:
                self.assertNotIn(name, swept_names)


class TestExtract(unittest.TestCase):
    '''Verifies music.extract() extracts all accepted archives after sweep.'''

    def test_extract(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            dest_dir = os.path.join(tmpdir, 'swept')
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)

            music.sweep(source_dir, dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            extracted = music.extract(dest_dir, dest_dir)

            # one result tuple per accepted archive
            self.assertEqual(len(extracted), gen.accepted_archive_count)

            # total extracted files across all archives matches manifest
            total_extracted = sum(len(files) for _, files in extracted)
            self.assertEqual(total_extracted, gen.expected_archive_file_count)

            # zip files remain at the swept location
            for archive_path, _ in extracted:
                self.assertTrue(os.path.exists(archive_path))


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

            # generate all fixture files from the manifest — music, archives, and noise
            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, new_music_dir)

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

            # only music tracks (individual + accepted archive contents) reach the collection
            self.assertEqual(result.record_result.tracks_added, gen.expected_music_count)
            # all tracks land in today's date context → one sync batch
            self.assertEqual(len(result.sync_result.batches), 1)
            self.assertEqual(result.sync_result.batches[0].files_processed, gen.expected_music_count)
            self.assertTrue(result.sync_result.batches[0].success)


if __name__ == '__main__':
    unittest.main()
