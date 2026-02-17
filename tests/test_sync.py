# TODO: add coverage for rsync_healthcheck

import unittest
import subprocess
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call
from typing import cast

from djmgmt import sync, constants, subsonic_client

# Constants
DATE_PROCESSED_PAST     = '2025/05 may/19'
DATE_PROCESSED_CURRENT  = '2025/05 may/20'
DATE_PROCESSED_FUTURE   = '2025/05 may/21'

MOCK_INPUT_DIR = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'
MOCK_XML_FILE_PATH = '/mock/xml/file.xml'
MOCK_ARTIST = 'mock_artist'
MOCK_ALBUM = 'mock_album'
MOCK_TITLE = 'mock_title'

COLLECTION_XML = f'''
<?xml version="1.0" encoding="UTF-8"?>

<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="1">
    
    </COLLECTION>
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="2">
            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="_pruned" Type="1" KeyType="0" Entries="0">
            </NODE>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>
'''.strip()

# Primary test classes
class TestIsProcessed(unittest.TestCase):
    # Past dates
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_is_processed_past(self, mock_load: MagicMock) -> None:
        '''Tests that matching date contexts before the processed date are considered processed.'''
        mock_load.return_value = DATE_PROCESSED_CURRENT
        
        actual = sync.SavedDateContext.is_processed(DATE_PROCESSED_PAST)
        
        self.assertTrue(actual, f"Date context '{DATE_PROCESSED_PAST}' is expected to be already processed.")
        mock_load.assert_called_once()
    
    # Current dates
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_is_processed_current(self, mock_load: MagicMock) -> None:
        '''Tests that matching date contexts equal to the processed date are considered processed.'''
        mock_load.return_value = DATE_PROCESSED_CURRENT
        
        actual = sync.SavedDateContext.is_processed(DATE_PROCESSED_CURRENT)
        self.assertTrue(actual, f"Date context '{DATE_PROCESSED_CURRENT}' is expected to be already processed.")
        mock_load.assert_called_once()
    
    # Future dates
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_is_processed_future(self, mock_load: MagicMock) -> None:
        '''Tests that matching date contexts later than the processed date are NOT considered processed.'''
        mock_load.return_value = DATE_PROCESSED_CURRENT
        
        actual = sync.SavedDateContext.is_processed(DATE_PROCESSED_FUTURE)
        self.assertFalse(actual, f"Date context '{DATE_PROCESSED_FUTURE}' is NOT expected to be already processed.")
        mock_load.assert_called_once()

class TestSyncBatch(unittest.TestCase):
    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    @patch('djmgmt.sync.transfer_files')
    @patch('djmgmt.subsonic_client.call_endpoint')
    @patch('djmgmt.subsonic_client.handle_response')
    @patch('time.sleep')
    def test_success_full_scan(self,
                               mock_sleep: MagicMock,
                               mock_handle_response: MagicMock,
                               mock_call_endpoint: MagicMock,
                               mock_transfer: MagicMock,
                               mock_transform: MagicMock,
                               mock_encode: MagicMock) -> None:
        '''Tests that the function calls the expected dependencies with the proper parameters in a full scan context.'''
        # Setup for full scan
        batch = [('/source/path1.aiff', '/dest/2023/01 january/01/path1.aiff'),
                 ('/source/path2.aiff', '/dest/2023/01 january/01/path2.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/2023/01 january/01/path1.aiff'
        full_scan = True
        
        # Configure mocks
        mock_transform.return_value = '/dest/./2023/01 january/01/'
        mock_transfer.return_value = (0, 'success')
        
        # Mock the API responses - expect endpoints to be called 4 times.
        mock_response = MagicMock(ok=True)
        mock_call_endpoint.return_value = mock_response
        
        # First call returns scanning=true, second call returns scanning=false
        mock_handle_response.side_effect = [{'scanning': 'true'}, {'scanning': 'false'}]
        
        # Call the function
        actual = sync.sync_batch(batch, date_context, dest, full_scan, sync.Namespace.SYNC_MODE_REMOTE)

        # Assert that the expected functions are called with expected parameters.
        self.assertIsInstance(actual, sync.SyncBatchResult)
        self.assertTrue(actual.success, 'Expect call to succeed')
        mock_encode.assert_called_once_with(batch, '.mp3', threads=28, dry_run=False)
        mock_transform.assert_called_once_with(dest)
        mock_transfer.assert_called_once_with(mock_transform.return_value, constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME, dry_run=False)

        # Expect call to start scan, then re-ping when scanning, then stop pinging.
        mock_call_endpoint.assert_has_calls([
            call(subsonic_client.API.START_SCAN, {'fullScan': 'true'}),
            call(subsonic_client.API.GET_SCAN_STATUS),
            call(subsonic_client.API.GET_SCAN_STATUS)
        ])
        mock_sleep.assert_called()

    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    @patch('djmgmt.sync.transfer_files')
    @patch('djmgmt.subsonic_client.call_endpoint')
    @patch('djmgmt.subsonic_client.handle_response')
    def test_success_quick_scan(self,
                                mock_handle_response: MagicMock,
                                mock_call_endpoint: MagicMock,
                                mock_transfer: MagicMock,
                                mock_transform: MagicMock,
                                mock_encode: MagicMock) -> None:
        '''Tests that the  function calls the expected dependencies with the proper parameters in a quick scan context.'''
        # Setup for quick scan
        batch = [('/source/path1.aiff', '/dest/2023/01 january/01/path1.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/2023/01 january/01/path1.aiff'
        full_scan = False
        
        # Configure mocks
        mock_transform.return_value = '/dest/./2023/01 january/01/'
        mock_transfer.return_value = (0, 'success')
        
        # Mock the API responses
        mock_response = MagicMock(ok=True)
        mock_call_endpoint.return_value = mock_response
        
        # Return scanning=false immediately to simulate quick scan
        mock_handle_response.return_value = {'scanning': 'false'}
        
        # Call the function
        actual = sync.sync_batch(batch, date_context, dest, full_scan, sync.Namespace.SYNC_MODE_REMOTE)

        # Assertions
        self.assertIsInstance(actual, sync.SyncBatchResult)
        self.assertTrue(actual.success, 'Expect call to succeed')
        mock_encode.assert_called_once_with(batch, '.mp3', threads=28, dry_run=False)
        mock_transform.assert_called_once_with(dest)
        mock_transfer.assert_called_once()
        mock_call_endpoint.assert_called()

        # Verify the scan parameter is 'false' for quick scan
        # Expect call to start scan, then re-ping when scanning, then stop pinging.
        mock_call_endpoint.assert_has_calls([
            call(subsonic_client.API.START_SCAN, {'fullScan': 'false'}),
            call(subsonic_client.API.GET_SCAN_STATUS),
        ])

    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    def test_error_no_transfer_path(self,
                                    mock_transform: MagicMock,
                                    mock_encode: MagicMock) -> None:
        '''Tests that an error is logged when the destination cannot be transformed into a transfer path.'''
        # Setup
        batch = [('/source/path1.aiff', '/dest/path1.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/path1.aiff'
        full_scan = True

        # Configure mock to return None (no valid transfer path)
        mock_transform.return_value = None

        # Call the function
        actual = sync.sync_batch(batch, date_context, dest, full_scan, sync.Namespace.SYNC_MODE_REMOTE)

        # Assertions
        self.assertIsInstance(actual, sync.SyncBatchResult)
        self.assertFalse(actual.success, 'Expect call to fail')
        mock_encode.assert_called_once_with(batch, '.mp3', threads=28, dry_run=False)
        mock_transform.assert_called_once_with(dest)

    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    @patch('djmgmt.sync.transfer_files')
    @patch('djmgmt.subsonic_client.call_endpoint')
    @patch('djmgmt.subsonic_client.handle_response')
    def test_dry_run_skips_api_calls(self,
                                     mock_handle_response: MagicMock,
                                     mock_call_endpoint: MagicMock,
                                     mock_transfer: MagicMock,
                                     mock_transform: MagicMock,
                                     mock_encode: MagicMock) -> None:
        '''Tests that dry-run mode skips Subsonic API calls.'''
        # Setup
        batch = [('/source/path1.aiff', '/dest/2023/01 january/01/path1.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/2023/01 january/01/path1.aiff'
        full_scan = True

        # Configure mocks
        mock_transform.return_value = '/dest/./2023/01 january/01/'
        mock_transfer.return_value = (23, 'dry run output')

        # Call the function with dry_run=True
        result = sync.sync_batch(batch, date_context, dest, full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=True)

        # Assertions
        self.assertIsInstance(result, sync.SyncBatchResult)
        self.assertEqual(result.date_context, date_context)
        self.assertEqual(result.files_processed, len(batch))
        self.assertTrue(result.success)

        # Verify encode was called with dry_run=True
        mock_encode.assert_called_once_with(batch, '.mp3', threads=28, dry_run=True)

        # Verify transfer was called with dry_run=True
        mock_transfer.assert_called_once_with(mock_transform.return_value, constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME, dry_run=True)

        # Verify API calls were NOT made
        mock_call_endpoint.assert_not_called()
        mock_handle_response.assert_not_called()
        
    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    @patch('djmgmt.sync.transfer_files')
    @patch('djmgmt.subsonic_client.call_endpoint')
    @patch('djmgmt.subsonic_client.handle_response')
    def test_error_api(self,
                       mock_handle_response: MagicMock,
                       mock_call_endpoint: MagicMock,
                       mock_transfer: MagicMock,
                       mock_transform: MagicMock,
                       mock_encode: MagicMock) -> None:
        '''Tests that no exception is thrown and that the correct functions are invoked if the API call fails.'''
        # Setup
        batch = [('/source/path1.aiff', '/dest/2023/01 january/01/path1.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/2023/01 january/01/path1.aiff'
        
        # Configure mocks
        mock_transform.return_value = '/dest/./2023/01 january/01/'
        mock_transfer.return_value = (0, 'success')
        
        # Mock the API responses
        mock_call_endpoint.return_value = MagicMock(ok=False)
        
        # Return scanning=false immediately
        mock_handle_response.return_value = {'scanning': 'false'}
        
        # Call the function, expecting no exception
        try:
            actual = sync.sync_batch(batch, date_context, dest, False, sync.Namespace.SYNC_MODE_REMOTE)
            self.assertIsInstance(actual, sync.SyncBatchResult)
            self.assertFalse(actual.success, 'Expect call to fail')
        except:
            self.fail('No exception expected')
        
        # Assert that only the start scan API was called
        mock_call_endpoint.assert_has_calls([
            call(subsonic_client.API.START_SCAN, {'fullScan': 'false'})
        ])
        
        # Assert that the expected mocks were either called or not
        mock_encode.assert_called_once()
        mock_transform.assert_called_once()
        mock_transfer.assert_called_once()
        mock_handle_response.assert_not_called()

    @patch('djmgmt.encode.encode_lossy')
    @patch('djmgmt.sync.transform_implied_path')
    @patch('djmgmt.sync.transfer_files')
    @patch('djmgmt.subsonic_client.call_endpoint')
    @patch('djmgmt.subsonic_client.handle_response')
    def test_local_mode(self,
                        mock_handle_response: MagicMock,
                        mock_call_endpoint: MagicMock,
                        mock_transfer: MagicMock,
                        mock_transform: MagicMock,
                        mock_encode: MagicMock) -> None:
        '''Tests that local mode only encodes and skips remote transfer and scan.'''
        # Setup
        batch = [('/source/path1.aiff', '/dest/2023/01 january/01/path1.aiff')]
        date_context = '2023/01 january/01'
        dest = '/dest/2023/01 january/01/path1.aiff'
        full_scan = True

        # Call the function with local mode
        actual = sync.sync_batch(batch, date_context, dest, full_scan, sync.Namespace.SYNC_MODE_LOCAL)

        # Assertions
        self.assertIsInstance(actual, sync.SyncBatchResult)
        self.assertTrue(actual.success, 'Expect call to succeed')
        mock_encode.assert_called_once_with(batch, '.mp3', threads=28, dry_run=False)

        # Verify that remote operations are NOT called in local mode
        mock_transform.assert_not_called()
        mock_transfer.assert_not_called()
        mock_call_endpoint.assert_not_called()
        mock_handle_response.assert_not_called()

class TestTransferFiles(unittest.TestCase):
    @patch('subprocess.run')
    @patch('logging.debug')
    @patch('logging.info')
    def test_success(self,
                     mock_log_info: MagicMock,
                     mock_log_debug: MagicMock,
                     mock_subprocess_run: MagicMock) -> None:
        '''Tests that a call with valid input returns the expected success values and calls the proper functions.'''
        # Setup
        source_path = '/source/2023/01 january/01/'
        dest_address = 'rsync://example.com'
        rsync_module = 'music'
        
        # Configure mock
        process_mock = MagicMock(returncode=0, stdout='Transfer successful')
        mock_subprocess_run.return_value = process_mock
        
        # Call the function
        return_code, output = sync.transfer_files(source_path, dest_address, rsync_module)
        
        # Assert success
        self.assertEqual(return_code, 0)
        self.assertEqual(output, 'Transfer successful')
        mock_log_info.assert_called_once()
        self.assertEqual(mock_log_debug.call_count, 2)
        
        # Assert that the rsync command was called
        mock_subprocess_run.assert_called_once()
        self.assertEqual(mock_subprocess_run.call_args[0][0][0], 'rsync')

    @patch('subprocess.run')
    @patch('logging.error')
    def test_error_subprocess(self,
                              mock_log_error: MagicMock,
                              mock_subprocess_run: MagicMock) -> None:
        '''Tests that the function returns the expected error information when the subprocess call fails.'''
        # Setup
        source_path = '/source/2023/01 january/01/'
        dest_address = 'rsync://example.com'
        rsync_module = 'music'
        
        # Configure mock to raise an exception
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(returncode=1, stderr='Error', cmd='mock_cmd')
        
        # Call the function
        return_code, output = sync.transfer_files(source_path, dest_address, rsync_module)
        
        # Assertions
        self.assertEqual(return_code, 1)
        self.assertEqual(output, 'Error')
        mock_log_error.assert_called_once()

    @patch('subprocess.run')
    def test_dry_run_adds_flag(self, mock_subprocess_run: MagicMock) -> None:
        '''Test transfer_files adds --dry-run flag to rsync command.'''
        # Setup
        source_path = '/source/2023/01 january/01/'
        dest_address = 'rsync://example.com'
        rsync_module = 'music'
        process_mock = MagicMock(returncode=0, stdout='would transfer files')
        mock_subprocess_run.return_value = process_mock

        # Call with dry_run=True
        return_code, output = sync.transfer_files(source_path, dest_address, rsync_module, dry_run=True)

        # Assert rsync command includes --dry-run
        mock_subprocess_run.assert_called_once()
        command = mock_subprocess_run.call_args[0][0]
        self.assertIn('--dry-run', command)
        self.assertEqual(return_code, 0)
        self.assertEqual(output, process_mock.stdout)

    @patch('subprocess.run')
    def test_normal_no_dry_run_flag(self, mock_subprocess_run: MagicMock) -> None:
        '''Test transfer_files excludes --dry-run flag in normal mode.'''
        # Setup
        source_path = '/source/2023/01 january/01/'
        dest_address = 'rsync://example.com'
        rsync_module = 'music'
        process_mock = MagicMock(returncode=0, stdout='transferred files')
        mock_subprocess_run.return_value = process_mock

        # Call with dry_run=False (default)
        return_code, output = sync.transfer_files(source_path, dest_address, rsync_module, dry_run=False)

        # Assert rsync command does NOT include --dry-run
        mock_subprocess_run.assert_called_once()
        command = mock_subprocess_run.call_args[0][0]
        self.assertNotIn('--dry-run', command)
        self.assertEqual(return_code, 0)
        self.assertEqual(output, process_mock.stdout)

class TestSyncMappings(unittest.TestCase):
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_success_one_context(self,
                                 mock_load: MagicMock,
                                 mock_save: MagicMock,
                                 mock_sync_batch: MagicMock) -> None:
        '''Tests that a single batch with mappings in the same date context is synced properly.'''
        # Set up mocks
        mock_load.return_value = ''
        mock_sync_batch.return_value = sync.SyncBatchResult('2025/05 may/20', 2, True)

        # Set up call input
        mappings = [
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
            ('input/path/track_1.mp3', '/output/2025/05 may/20/artist/album/track_1.mp3'),
        ]

        # Target function
        result = sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)

        # Assert expectations
        ## Expect that a single batch is synced with the given mappings
        mock_sync_batch.assert_called_once()

        ## Expect file to be written with the date context
        mock_save.assert_called_once()

        ## Expect result to be list of SyncBatchResult
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_success_multiple_contexts(self,
                                       mock_load: MagicMock,
                                       mock_save: MagicMock,
                                       mock_sync_batch: MagicMock) -> None:
        '''Tests that two batches with mappings in two date contexts are synced properly.'''
        mock_load.return_value = ''
        
        # Set up call input
        mappings = [
            # Date context 0: 2025/05 may/20
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
            ('input/path/track_1.mp3', '/output/2025/05 may/20/artist/album/track_1.mp3'),
            
            # Date context 1: 2025/05 may/21
            ('input/path/track_2.mp3', '/output/2025/05 may/21/artist/album/track_2.mp3'),
            ('input/path/track_3.mp3', '/output/2025/05 may/21/artist/album/track_3.mp3'),
        ]
        
        # Target function
        sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)
        
        # Assert expectations
        # Expect that a single batch is synced with the given mappings
        self.assertEqual(mock_sync_batch.call_count, 2)
        
        ## Expect file to be written for each date context
        self.assertEqual(mock_save.call_count, 2)
        
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_error_empty_mappings(self,
                                  mock_load: MagicMock,
                                  mock_save: MagicMock,
                                  mock_sync_batch: MagicMock) -> None:
        '''Tests that nothing is synced for an empty mappings list and no error is raised.'''
        # Set up call input
        mappings = []
        
        # Target function
        sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)
        
        # Assert expectations
        mock_sync_batch.assert_not_called()
        mock_load.assert_not_called()
        mock_save.assert_not_called()
    
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_error_sync_batch(self,
                                  mock_load: MagicMock,
                                  mock_save: MagicMock,
                              mock_sync_batch: MagicMock) -> None:
        '''Tests that an error is raised when a batch sync call fails'''
        # Set up mocks
        mock_load.return_value = ''
        mock_sync_batch.return_value = False
        
        # Set up call input
        mappings = [
            # Date context: 2025/05 may/20
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
            ('input/path/track_1.mp3', '/output/2025/05 may/20/artist/album/track_1.mp3'),
        ]
        
        # Target function
        with self.assertRaises(Exception):
            sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)

        # Assert expectations
        # Expect that a single batch is synced with the given mappings
        mock_sync_batch.assert_called_once()
        
        # Expect no calls to open sync state file, because no batches completed
        mock_save.assert_not_called()
    
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_success_outdated_context_single(self,
                                             mock_load: MagicMock,
                                             mock_save: MagicMock,
                                             mock_sync_batch: MagicMock) -> None:
        '''Tests that a mapping with a date context older than the saved date context does not save any date context.'''
        # Set up mocks
        mock_load.return_value = '2100/01 january/ 01'
        
        # Set up call input
        mappings = [
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
        ]
        
        # Target function
        sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)
        
        # Assert expectations
        ## Expect that a single batch is synced with the given mappings
        mock_sync_batch.assert_called_once()
        
        ## Expect no save call
        mock_save.assert_not_called()
        
    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_success_outdated_context_multiple(self,
                                               mock_load: MagicMock,
                                               mock_save: MagicMock,
                                               mock_sync_batch: MagicMock) -> None:
        '''Tests that a mapping with a date context older than the saved date context does not save any date context.'''
        # Set up mocks
        mock_load.return_value = '2100/01 january/ 01'
        
        # Set up call input
        mappings = [
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
            ('input/path/track_0.mp3', '/output/2025/05 may/21/artist/album/track_0.mp3'),
        ]
        
        # Target function
        sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE)
        
        # Assert expectations
        ## Expect that a single batch is synced with the given mappings
        self.assertEqual(mock_sync_batch.call_count, 2)

        ## Expect no save call
        mock_save.assert_not_called()

    @patch('djmgmt.sync.sync_batch')
    @patch('djmgmt.sync.SavedDateContext.save')
    @patch('djmgmt.sync.SavedDateContext.load')
    def test_dry_run_skips_state_save(self,
                                      mock_load: MagicMock,
                                      mock_save: MagicMock,
                                      mock_sync_batch: MagicMock) -> None:
        '''Tests that dry-run mode skips state file saves and returns SyncBatchResult list.'''
        # Set up mocks
        mock_load.return_value = ''
        batch_result_1 = sync.SyncBatchResult('2025/05 may/20', 2, True)
        batch_result_2 = sync.SyncBatchResult('2025/05 may/21', 2, True)
        mock_sync_batch.side_effect = [batch_result_1, batch_result_2]

        # Set up call input
        mappings = [
            # Date context 0: 2025/05 may/20
            ('input/path/track_0.mp3', '/output/2025/05 may/20/artist/album/track_0.mp3'),
            ('input/path/track_1.mp3', '/output/2025/05 may/20/artist/album/track_1.mp3'),

            # Date context 1: 2025/05 may/21
            ('input/path/track_2.mp3', '/output/2025/05 may/21/artist/album/track_2.mp3'),
            ('input/path/track_3.mp3', '/output/2025/05 may/21/artist/album/track_3.mp3'),
        ]

        # Target function with dry_run=True
        result = sync.sync_mappings(mappings, False, sync.Namespace.SYNC_MODE_REMOTE, dry_run=True)

        # Assert expectations
        # Should return list of SyncBatchResult
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertListEqual(result, [batch_result_1, batch_result_2])

        # Expect sync_batch called twice with dry_run=True
        self.assertEqual(mock_sync_batch.call_count, 2)
        for call in mock_sync_batch.call_args_list:
            self.assertTrue(call.kwargs.get('dry_run', False))

        # Expect NO state file saves in dry-run mode
        mock_save.assert_not_called()

class TestRunSyncMappings(unittest.TestCase):
    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    def test_success(self,
                     mock_sync_from_mappings: MagicMock,
                     mock_rsync_healthcheck: MagicMock) -> None:
        # Set up mocks
        mock_mappings = [('/mock/mapping/1', '/mock/mapping/2')]
        
        # Call target function
        mock_full_scan = True
        sync.run_music(mock_mappings, mock_full_scan)
        
        # Assert expectations
        mock_sync_from_mappings.assert_called_once_with(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=False)
        mock_rsync_healthcheck.assert_called_once()
    
    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    def test_exception_sync_from_mappings(self,
                                          mock_sync_from_mappings: MagicMock,
                                          mock_rsync_healthcheck: MagicMock) -> None:
        # Set up mocks
        mock_error = 'Mock error'
        mock_mappings = [('/mock/mapping/1', '/mock/mapping/2')]
        mock_sync_from_mappings.side_effect = Exception(mock_error)
        
        # Call target function
        mock_full_scan = True
        with self.assertRaises(Exception) as e:
            sync.run_music(mock_mappings, mock_full_scan)
            self.assertEqual(e.msg, mock_error)
        
        # Assert expectations
        mock_sync_from_mappings.assert_called_once_with(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=False)
        mock_rsync_healthcheck.assert_called_once()
        
    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    def test_rsync_healthcheck_fail(self,
                                    mock_sync_from_mappings: MagicMock,
                                    mock_rsync_healthcheck: MagicMock) -> None:
        # Set up mocks
        mock_error = 'Mock error'
        mock_mappings = [('/mock/mapping/1', '/mock/mapping/2')]
        mock_rsync_healthcheck.return_value = False

        # Call target function
        mock_full_scan = True
        with self.assertRaises(Exception) as e:
            sync.run_music(mock_mappings, mock_full_scan)
            self.assertEqual(e.msg, mock_error)

        # Assert expectations
        mock_sync_from_mappings.assert_not_called()
        mock_rsync_healthcheck.assert_called_once()

    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    @patch('djmgmt.common.find_date_context')
    def test_end_date_filter(self,
                             mock_find_date_context: MagicMock,
                             mock_sync_from_mappings: MagicMock,
                             mock_rsync_healthcheck: MagicMock) -> None:
        '''Tests that mappings are properly filtered based on the end_date parameter.'''
        # Set up mocks
        mock_mappings = [
            ('/input/track1.aiff', '/output/2025/05 may/19/artist/album/track1.aiff'),
            ('/input/track2.aiff', '/output/2025/05 may/20/artist/album/track2.aiff'),
            ('/input/track3.aiff', '/output/2025/05 may/21/artist/album/track3.aiff'),
        ]

        # Mock date context extraction to return the date from each path
        # Called during sorting (3 times) and filtering (3 times)
        mock_find_date_context.side_effect = [
            ('2025/05 may/19',),  # first mapping - sort
            ('2025/05 may/20',),  # second mapping - sort
            ('2025/05 may/21',),  # third mapping - sort
            ('2025/05 may/19',),  # first mapping - filter
            ('2025/05 may/20',),  # second mapping - filter
            ('2025/05 may/21',),  # third mapping - filter (should be filtered out)
        ]

        # Call target function with end_date
        mock_full_scan = True
        end_date = '2025/05 may/20'
        sync.run_music(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, end_date)

        # Assert expectations
        # Should only sync the first two mappings (dates <= end_date)
        expected_filtered_mappings = [
            ('/input/track1.aiff', '/output/2025/05 may/19/artist/album/track1.aiff'),
            ('/input/track2.aiff', '/output/2025/05 may/20/artist/album/track2.aiff'),
        ]
        mock_sync_from_mappings.assert_called_once_with(expected_filtered_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=False)
        mock_rsync_healthcheck.assert_called_once()
        self.assertEqual(mock_find_date_context.call_count, 6)

    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    def test_dry_run_threaded_to_sync_mappings(self,
                                                mock_sync_from_mappings: MagicMock,
                                                mock_rsync_healthcheck: MagicMock) -> None:
        '''Tests that dry_run parameter is threaded to sync_mappings call.'''
        # Set up mocks
        batch_result_1 = sync.SyncBatchResult('2025/05 may/20', 2, True)
        batch_result_2 = sync.SyncBatchResult('2025/05 may/21', 1, True)
        mock_sync_from_mappings.return_value = [batch_result_1, batch_result_2]

        mock_mappings = [
            ('/input/track1.aiff', '/output/2025/05 may/20/artist/album/track1.aiff'),
            ('/input/track2.aiff', '/output/2025/05 may/20/artist/album/track2.aiff'),
            ('/input/track3.aiff', '/output/2025/05 may/21/artist/album/track3.aiff'),
        ]

        # Call target function with dry_run=True
        mock_full_scan = True
        result = sync.run_music(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=True)

        # Assert expectations
        # Verify dry_run was threaded to sync_mappings
        mock_sync_from_mappings.assert_called_once_with(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=True)
        mock_rsync_healthcheck.assert_called_once()

        # Verify SyncResult is returned with correct structure
        self.assertIsInstance(result, sync.SyncResult)
        self.assertEqual(result.mappings, mock_mappings)
        self.assertEqual(len(result.batches), 2)
        self.assertListEqual(result.batches, [batch_result_1, batch_result_2])

    @patch('djmgmt.sync.rsync_healthcheck')
    @patch('djmgmt.sync.sync_mappings')
    def test_returns_sync_result_structure(self,
                                           mock_sync_from_mappings: MagicMock,
                                           mock_rsync_healthcheck: MagicMock) -> None:
        '''Tests that SyncResult is returned with correct structure in normal mode.'''
        # Set up mocks
        batch_result = sync.SyncBatchResult('2025/05 may/20', 3, True)
        mock_sync_from_mappings.return_value = [batch_result]

        mock_mappings = [
            ('/input/track1.aiff', '/output/2025/05 may/20/artist/album/track1.aiff'),
            ('/input/track2.aiff', '/output/2025/05 may/20/artist/album/track2.aiff'),
            ('/input/track3.aiff', '/output/2025/05 may/20/artist/album/track3.aiff'),
        ]

        # Call target function (normal mode, dry_run defaults to False)
        mock_full_scan = False
        result = sync.run_music(mock_mappings, mock_full_scan)

        # Assert expectations
        # Verify sync_mappings was called with dry_run=False (default)
        mock_sync_from_mappings.assert_called_once_with(mock_mappings, mock_full_scan, sync.Namespace.SYNC_MODE_REMOTE, dry_run=False)

        # Verify SyncResult structure
        self.assertIsInstance(result, sync.SyncResult)
        self.assertEqual(result.mappings, mock_mappings)
        self.assertEqual(len(result.batches), 1)
        self.assertEqual(result.batches[0], batch_result)

        # Verify backward compatibility - normal mode still works
        self.assertTrue(result.batches[0].success)

class TestCreateSyncMappings(unittest.TestCase):
    @patch('djmgmt.sync.SavedDateContext.is_processed')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.generate_date_paths')
    @patch('djmgmt.library.find_node')
    def test_success_nothing_filtered(self,
                                      mock_find_node: MagicMock,
                                      mock_generate_date_paths: MagicMock,
                                      mock_find_date_context: MagicMock,
                                      mock_is_processed: MagicMock) -> None:
        # Set up mocks
        mock_node_pruned = MagicMock()
        mock_node_pruned = [MagicMock(attrib={ constants.ATTR_TRACK_KEY : '1' })]
        mock_node_collection = MagicMock()

        mock_find_node.side_effect = [mock_node_pruned, mock_node_collection]
        mock_generate_date_paths.return_value = [(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)]
        mock_find_date_context.return_value = 'mock_context'        
        mock_is_processed.return_value = False # mock unprocessed contexts
        
        # Call target function
        root = cast(ET.Element, ET.ElementTree(ET.fromstring(COLLECTION_XML)).getroot())
        actual = sync.create_sync_mappings(root, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        self.assertEqual(actual, [(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)])
        mock_generate_date_paths.assert_called_once_with(mock_node_collection,
                                                         MOCK_OUTPUT_DIR,
                                                         playlist_ids={'1'},
                                                         metadata_path=False)
        
    @patch('djmgmt.sync.SavedDateContext.is_processed')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.generate_date_paths')
    @patch('djmgmt.library.find_node')
    def test_success_everything_filtered(self,
                                         mock_find_node: MagicMock,
                                         mock_generate_date_paths: MagicMock,
                                         mock_find_date_context: MagicMock,
                                         mock_is_processed: MagicMock) -> None:
        # Set up mocks
        mock_node_pruned = MagicMock()
        mock_node_pruned = [MagicMock(attrib={ constants.ATTR_TRACK_KEY : '1' })]
        mock_node_collection = MagicMock()

        mock_find_node.side_effect = [mock_node_pruned, mock_node_collection]
        mock_generate_date_paths.return_value = [(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)]
        mock_find_date_context.return_value = 'mock_context'        
        mock_is_processed.return_value = True # mock all processed contexts
        
        # Call target function
        root = cast(ET.Element, ET.ElementTree(ET.fromstring(COLLECTION_XML)).getroot())
        actual = sync.create_sync_mappings(root, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        self.assertEqual(actual, []) # no mappings should be returned, because everything was processed
        mock_generate_date_paths.assert_called_once_with(mock_node_collection,
                                                         MOCK_OUTPUT_DIR,
                                                         playlist_ids={'1'},
                                                         metadata_path=False)

class TestPreviewSync(unittest.TestCase):
    '''Tests for sync.preview_sync.'''

    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.library.extract_track_metadata')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.sync.create_sync_mappings')
    def test_success_new_tracks_only(self,
                                     mock_create_sync_mappings: MagicMock,
                                     mock_find_node: MagicMock,
                                     mock_extract_metadata: MagicMock,
                                     mock_filter_mappings: MagicMock,
                                     mock_compare_tags: MagicMock) -> None:
        '''Tests that new tracks are returned with correct metadata and change_type.'''
        from djmgmt.library import TrackMetadata

        # Setup mocks
        mock_create_sync_mappings.return_value = [
            ('/library/track1.aiff', '/mirror/track1.mp3'),
            ('/library/track2.aiff', '/mirror/track2.mp3')
        ]
        mock_compare_tags.return_value = []
        mock_filter_mappings.return_value = []
        mock_find_node.return_value = MagicMock()

        # Mock metadata extraction
        mock_extract_metadata.side_effect = [
            TrackMetadata('Track 1', 'Artist 1', 'Album 1', '/library/track1.aiff', 'mock_date_added', 'mock_total_time'),
            TrackMetadata('Track 2', 'Artist 2', 'Album 2', '/library/track2.aiff', 'mock_date_added', 'mock_total_time')
        ]

        # Call function
        root = ET.fromstring(COLLECTION_XML)
        result = sync.preview_sync(root, '/mirror', '/library')

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].metadata.title, 'Track 1')
        self.assertEqual(result[0].change_type, 'new')
        self.assertEqual(result[1].metadata.title, 'Track 2')
        self.assertEqual(result[1].change_type, 'new')

    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.library.extract_track_metadata')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.sync.create_sync_mappings')
    def test_success_changed_tracks_only(self,
                                         mock_create_sync_mappings: MagicMock,
                                         mock_find_node: MagicMock,
                                         mock_extract_metadata: MagicMock,
                                         mock_filter_mappings: MagicMock,
                                         mock_compare_tags: MagicMock) -> None:
        '''Tests that changed tracks are returned with correct change_type.'''
        from djmgmt.library import TrackMetadata

        # Setup mocks
        mock_create_sync_mappings.return_value = []
        mock_compare_tags.return_value = [
            ('/library/track1.aiff', '/mirror/track1.mp3')
        ]
        mock_filter_mappings.return_value = [
            ('/library/track1.aiff', '/mirror/track1.mp3')
        ]
        mock_find_node.return_value = MagicMock()
        mock_extract_metadata.return_value = TrackMetadata('Track 1', 'Artist 1', 'Album 1', '/library/track1.aiff', 'mock_date_added', 'mock_total_time')

        # Call function
        root = ET.fromstring(COLLECTION_XML)
        result = sync.preview_sync(root, '/mirror', '/library')

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].metadata.title, 'Track 1')
        self.assertEqual(result[0].change_type, 'changed')

    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.library.extract_track_metadata')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.sync.create_sync_mappings')
    def test_success_mixed_tracks(self,
                                  mock_create_sync_mappings: MagicMock,
                                  mock_find_node: MagicMock,
                                  mock_extract_metadata: MagicMock,
                                  mock_filter_mappings: MagicMock,
                                  mock_compare_tags: MagicMock) -> None:
        '''Tests that both new and changed tracks are returned correctly.'''
        from djmgmt.library import TrackMetadata

        # Setup mocks
        mock_create_sync_mappings.return_value = [
            ('/library/new_track.aiff', '/mirror/new_track.mp3')
        ]
        mock_compare_tags.return_value = [
            ('/library/changed_track.aiff', '/mirror/changed_track.mp3')
        ]
        mock_filter_mappings.return_value = [
            ('/library/changed_track.aiff', '/mirror/changed_track.mp3')
        ]
        mock_find_node.return_value = MagicMock()
        mock_extract_metadata.side_effect = [
            TrackMetadata('New Track', 'Artist', 'Album', '/library/new_track.aiff', 'mock_date_added', 'mock_total_time'),
            TrackMetadata('Changed Track', 'Artist', 'Album', '/library/changed_track.aiff', 'mock_date_added', 'mock_total_time')
        ]

        # Call function
        root = ET.fromstring(COLLECTION_XML)
        result = sync.preview_sync(root, '/mirror', '/library')

        # Assertions
        self.assertEqual(len(result), 2)
        # Check new track
        new_track = [t for t in result if t.change_type == 'new'][0]
        self.assertEqual(new_track.metadata.title, 'New Track')
        # Check changed track
        changed_track = [t for t in result if t.change_type == 'changed'][0]
        self.assertEqual(changed_track.metadata.title, 'Changed Track')

    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.library.extract_track_metadata')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.sync.create_sync_mappings')
    def test_empty_preview(self,
                          mock_create_sync_mappings: MagicMock,
                          mock_find_node: MagicMock,
                          mock_extract_metadata: MagicMock,
                          mock_filter_mappings: MagicMock,
                          mock_compare_tags: MagicMock) -> None:
        '''Tests that empty list is returned when no tracks need syncing.'''
        # Setup mocks
        mock_create_sync_mappings.return_value = []
        mock_compare_tags.return_value = []
        mock_filter_mappings.return_value = []
        mock_find_node.return_value = MagicMock()

        # Call function
        root = ET.fromstring(COLLECTION_XML)
        result = sync.preview_sync(root, '/mirror', '/library')

        # Assertions
        self.assertEqual(len(result), 0)
        mock_extract_metadata.assert_not_called()

    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.library.extract_track_metadata')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.sync.create_sync_mappings')
    def test_track_not_found_in_collection(self,
                                          mock_create_sync_mappings: MagicMock,
                                          mock_find_node: MagicMock,
                                          mock_extract_metadata: MagicMock,
                                          mock_filter_mappings: MagicMock,
                                          mock_compare_tags: MagicMock) -> None:
        '''Tests that tracks with no metadata are skipped.'''
        # Setup mocks
        mock_create_sync_mappings.return_value = [
            ('/library/track1.aiff', '/mirror/track1.mp3')
        ]
        mock_compare_tags.return_value = []
        mock_filter_mappings.return_value = []
        mock_find_node.return_value = MagicMock()
        mock_extract_metadata.return_value = None  # Track not found

        # Call function
        root = ET.fromstring(COLLECTION_XML)
        result = sync.preview_sync(root, '/mirror', '/library')

        # Assertions
        self.assertEqual(len(result), 0)

class TestParseArgs(unittest.TestCase):
    '''Tests for sync.parse_args and argument validation.'''

    def test_valid_sync(self) -> None:
        '''Tests that sync function can be called with required arguments.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/mock/input', '--output', '/mock/output', '--scan-mode', 'quick']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertEqual(args.function, sync.Namespace.FUNCTION_MUSIC)
        self.assertEqual(args.input, '/mock/input')
        self.assertEqual(args.output, '/mock/output')
        self.assertEqual(args.scan_mode, 'quick')
        self.assertEqual(args.sync_mode, 'remote')  # default
        self.assertIsNone(args.end_date)

    def test_valid_with_all_optional_args(self) -> None:
        '''Tests that all optional arguments can be provided.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick',
                '--sync-mode', 'local', '--end-date', '2025/10 october/09']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertEqual(args.function, sync.Namespace.FUNCTION_MUSIC)
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/out')
        self.assertEqual(args.scan_mode, 'quick')
        self.assertEqual(args.sync_mode, 'local')
        self.assertEqual(args.end_date, '2025/10 october/09')

    @patch('sys.exit')
    def test_missing_input(self, mock_exit: MagicMock) -> None:
        '''Tests that missing --input causes error.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--output', '/out', '--scan-mode', 'quick']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_missing_output(self, mock_exit: MagicMock) -> None:
        '''Tests that missing --output causes error.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--scan-mode', 'quick']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_missing_scan_mode(self, mock_exit: MagicMock) -> None:
        '''Tests that missing --scan-mode causes error.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_invalid_function(self, mock_exit: MagicMock) -> None:
        '''Tests that invalid function name causes error.'''
        argv = ['invalid', '--input', '/in', '--output', '/out', '--scan-mode', 'quick']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_invalid_scan_mode(self, mock_exit: MagicMock) -> None:
        '''Tests that invalid scan mode causes error.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'invalid']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_invalid_sync_mode(self, mock_exit: MagicMock) -> None:
        '''Tests that invalid sync mode causes error.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick', '--sync-mode', 'invalid']
        sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        mock_exit.assert_called_with(2)

    def test_path_normalization(self) -> None:
        '''Tests that paths are normalized.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', 'relative/path', '--output', 'output/', '--scan-mode', 'quick']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        import os
        self.assertEqual(args.input, os.path.normpath('relative/path'))
        self.assertEqual(args.output, os.path.normpath('output/'))

    def test_sync_mode_default(self) -> None:
        '''Tests that sync_mode defaults to remote.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertEqual(args.sync_mode, 'remote')

    def test_dry_run_default(self) -> None:
        '''Tests that dry_run defaults to False when not provided.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertFalse(args.dry_run)

    def test_dry_run_enabled(self) -> None:
        '''Tests that --dry-run flag sets dry_run to True.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick', '--dry-run']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertTrue(args.dry_run)

    def test_dry_run_short_flag(self) -> None:
        '''Tests that -d short flag sets dry_run to True.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'quick', '-d']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertTrue(args.dry_run)

    def test_dry_run_with_all_options(self) -> None:
        '''Tests that dry_run works with all other optional arguments.'''
        argv = [sync.Namespace.FUNCTION_MUSIC, '--input', '/in', '--output', '/out', '--scan-mode', 'full',
                '--sync-mode', 'local', '--end-date', '2025/10 october/09', '--dry-run']
        args = sync.parse_args(sync.Namespace.FUNCTIONS, sync.Namespace.SCAN_MODES, sync.Namespace.SYNC_MODES, argv)

        self.assertEqual(args.function, sync.Namespace.FUNCTION_MUSIC)
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/out')
        self.assertEqual(args.scan_mode, 'full')
        self.assertEqual(args.sync_mode, 'local')
        self.assertEqual(args.end_date, '2025/10 october/09')
        self.assertTrue(args.dry_run)
