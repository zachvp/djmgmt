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

    # processed collection is the secondary input to merge_collections
    shutil.copy(config.COLLECTION_PATH_TEMPLATE, config.COLLECTION_PATH_PROCESSED)

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


class TestFlattenHierarchy(unittest.TestCase):
    '''Verifies music.flatten_hierarchy() leaves no subdirectories after sweep+extract.'''

    def test_flatten_hierarchy(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            dest_dir = os.path.join(tmpdir, 'swept')
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)

            music.sweep(source_dir, dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            music.extract(dest_dir, dest_dir)

            files_before = list(common.collect_paths(dest_dir))
            music.flatten_hierarchy(dest_dir, dest_dir)

            # no subdirectories remain
            for item in os.listdir(dest_dir):
                self.assertFalse(os.path.isdir(os.path.join(dest_dir, item)),
                                 f"unexpected subdirectory after flatten: {item}")

            # file count is preserved
            files_after = list(common.collect_paths(dest_dir))
            self.assertEqual(len(files_after), len(files_before))


class TestStandardizeLossless(unittest.TestCase):
    '''Verifies music.standardize_lossless() converts WAV and FLAC to AIFF after sweep+extract+flatten.'''

    def test_standardize_lossless(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            dest_dir = os.path.join(tmpdir, 'swept')
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)

            music.sweep(source_dir, dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            music.extract(dest_dir, dest_dir)
            music.flatten_hierarchy(dest_dir, dest_dir)

            files_before = list(common.collect_paths(dest_dir))
            encoded = music.standardize_lossless(dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)

            # all lossless files were encoded
            self.assertEqual(len(encoded), gen.lossless_file_count)

            # no WAV or FLAC files remain
            for f in common.collect_paths(dest_dir):
                ext = os.path.splitext(f)[1].lower()
                self.assertNotIn(ext, {'.wav', '.flac'}, f"lossless file not converted: {f}")

            # total file count is preserved (each lossless replaced 1-for-1 with aiff)
            files_after = list(common.collect_paths(dest_dir))
            self.assertEqual(len(files_after), len(files_before))


class TestPruneNonMusic(unittest.TestCase):
    '''Verifies music.prune_non_music() removes non-music files after sweep+extract+flatten+standardize.'''

    def test_prune_non_music(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            dest_dir = os.path.join(tmpdir, 'swept')
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)

            music.sweep(source_dir, dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            music.extract(dest_dir, dest_dir)
            music.flatten_hierarchy(dest_dir, dest_dir)
            music.standardize_lossless(dest_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            music.prune_non_music(dest_dir, constants.EXTENSIONS)

            remaining = list(common.collect_paths(dest_dir))

            # only valid music extensions remain
            for f in remaining:
                ext = os.path.splitext(f)[1].lower()
                self.assertIn(ext, constants.EXTENSIONS, f"non-music file not pruned: {f}")

            # music file count matches expected
            self.assertEqual(len(remaining), gen.expected_music_count)


class TestProcess(unittest.TestCase):
    '''Verifies music.process() runs the complete sweep→extract→flatten→encode→prune pipeline.'''

    def setUp(self) -> None:
        _setup_state_dir()

    def test_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            output_dir = os.path.join(tmpdir, 'library')
            os.makedirs(source_dir)
            os.makedirs(output_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)
            result = music.process(source_dir, output_dir, constants.EXTENSIONS, music.PREFIX_HINTS)

            # archive count matches accepted archives
            self.assertEqual(result.archives_extracted, gen.accepted_archive_count)

            # encoded files matches total lossless file count
            self.assertEqual(result.files_encoded, gen.lossless_file_count)

            # processed file count matches expected music count
            self.assertEqual(len(result.processed_files), gen.expected_music_count)

            # all output files exist with valid extensions
            for _, output_path in result.processed_files:
                self.assertTrue(os.path.exists(output_path), f"output file missing: {output_path}")
                ext = os.path.splitext(output_path)[1].lower()
                self.assertIn(ext, constants.EXTENSIONS, f"invalid extension: {output_path}")


class TestRecordCollection(unittest.TestCase):
    '''Verifies library.record_collection() records all processed tracks into the XML collection.'''

    def setUp(self) -> None:
        _setup_state_dir()

    def test_record_collection(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            library_dir = os.path.join(tmpdir, 'library')
            os.makedirs(source_dir)
            os.makedirs(library_dir)

            gen = fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)
            music.process(source_dir, library_dir, constants.EXTENSIONS, music.PREFIX_HINTS)

            record_result = library.record_collection(
                library_dir,
                config.COLLECTION_PATH_TEMPLATE,
                config.COLLECTION_PATH_PROCESSED,
            )

            # correct number of tracks added
            self.assertEqual(record_result.tracks_added, gen.expected_music_count)

            # each track has a non-empty TrackID
            collection_node = library.find_node(record_result.collection_root, constants.XPATH_COLLECTION)
            for track in collection_node.findall(constants.TAG_TRACK):
                track_id = track.get(constants.ATTR_TRACK_ID)
                self.assertIsNotNone(track_id)
                self.assertGreater(len(track_id), 0)  # type: ignore[arg-type]

            # all tracks appear in the _pruned playlist
            pruned = library.find_node(record_result.collection_root, constants.XPATH_PRUNED)
            self.assertEqual(len(pruned.findall(constants.TAG_TRACK)), gen.expected_music_count)


class TestCreateSyncMappings(unittest.TestCase):
    '''Verifies sync.create_sync_mappings() after process() + record_collection().'''

    def setUp(self) -> None:
        _setup_state_dir()

    def test_create_sync_mappings(self) -> None:
        with tempfile.TemporaryDirectory(prefix='djmgmt_e2e_') as tmpdir:
            source_dir = os.path.join(tmpdir, 'new_music')
            library_dir = os.path.join(tmpdir, 'library')
            mirror_dir = os.path.join(tmpdir, 'mirror')
            os.makedirs(source_dir)
            os.makedirs(library_dir)
            os.makedirs(mirror_dir)

            fixture_generator.generate_from_manifest(_MANIFEST_PATH, source_dir)
            music.process(source_dir, library_dir, constants.EXTENSIONS, music.PREFIX_HINTS)
            record_result = library.record_collection(
                library_dir,
                config.COLLECTION_PATH_TEMPLATE,
                config.COLLECTION_PATH_PROCESSED,
            )

            mappings = sync.create_sync_mappings(record_result.collection_root, mirror_dir)

            # mapping count equals the number of tracks in _pruned
            pruned = library.find_node(record_result.collection_root, constants.XPATH_PRUNED)
            pruned_count = len(pruned.findall(constants.TAG_TRACK))
            self.assertEqual(len(mappings), pruned_count)

            # each mapping's library path exists on disk
            for lib_path, _ in mappings:
                self.assertTrue(os.path.exists(lib_path), f"library path does not exist: {lib_path}")


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

            # merged XML: both inputs were empty templates, so the merged result has no tracks
            merged_root = library.load_collection(config.COLLECTION_PATH_MERGED)
            merged_collection = library.find_node(merged_root, constants.XPATH_COLLECTION)
            self.assertEqual(merged_collection.get('Entries'), '0')
            self.assertListEqual(merged_collection.findall(constants.TAG_TRACK), [])
            merged_pruned = library.find_node(merged_root, constants.XPATH_PRUNED)
            self.assertEqual(merged_pruned.get('Entries'), '0')
            self.assertListEqual(merged_pruned.findall(constants.TAG_TRACK), [])

            # recorded XML: verify in-memory root structure
            recorded_root = result.record_result.collection_root
            recorded_collection = library.find_node(recorded_root, constants.XPATH_COLLECTION)
            recorded_tracks = recorded_collection.findall(constants.TAG_TRACK)
            self.assertEqual(len(recorded_tracks), gen.expected_music_count)
            self.assertEqual(recorded_collection.get('Entries'), str(gen.expected_music_count))

            # each track has required non-empty attributes and its file exists on disk
            for track in recorded_tracks:
                track_id = track.get(constants.ATTR_TRACK_ID)
                location = track.get(constants.ATTR_LOCATION)
                date_added = track.get(constants.ATTR_DATE_ADDED)
                self.assertIsNotNone(track_id)
                self.assertGreater(len(track_id), 0)  # type: ignore[arg-type]
                self.assertIsNotNone(location)
                self.assertTrue(location.startswith(config.REKORDBOX_ROOT),  # type: ignore[union-attr]
                                f"Location missing REKORDBOX_ROOT prefix: {location}")
                self.assertIsNotNone(date_added)
                self.assertGreater(len(date_added), 0)  # type: ignore[arg-type]
                file_path = library.collection_path_to_syspath(location)  # type: ignore[arg-type]
                self.assertTrue(os.path.exists(file_path), f"track file missing on disk: {file_path}")

            # _pruned track keys match COLLECTION track IDs exactly
            recorded_pruned = library.find_node(recorded_root, constants.XPATH_PRUNED)
            pruned_keys = {t.get(constants.ATTR_TRACK_KEY) for t in recorded_pruned.findall(constants.TAG_TRACK)}
            collection_ids = {t.get(constants.ATTR_TRACK_ID) for t in recorded_tracks}
            self.assertSetEqual(pruned_keys, collection_ids)
            self.assertEqual(recorded_pruned.get('Entries'), str(gen.expected_music_count))

            # disk-persisted XML matches in-memory result
            disk_root = library.load_collection(config.COLLECTION_PATH_PROCESSED)
            disk_collection = library.find_node(disk_root, constants.XPATH_COLLECTION)
            self.assertEqual(len(disk_collection.findall(constants.TAG_TRACK)), gen.expected_music_count)
            disk_pruned = library.find_node(disk_root, constants.XPATH_PRUNED)
            self.assertEqual(len(disk_pruned.findall(constants.TAG_TRACK)), gen.expected_music_count)


if __name__ == '__main__':
    unittest.main()
