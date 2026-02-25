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
import subprocess
import tempfile
import time
import unittest

from djmgmt import config, encode, subsonic_client, sync
from djmgmt.common import FileMapping

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


if __name__ == '__main__':
    unittest.main()
