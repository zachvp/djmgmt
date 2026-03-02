import io
import unittest
import os
from unittest.mock import patch, MagicMock, call, AsyncMock

from djmgmt import constants

# Test targets
from djmgmt import encode
from djmgmt.encode import Namespace

# Constants
MOCK_INPUT = '/mock/input'
MOCK_OUTPUT = '/mock/output'


class TestEncodeLossless(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_get_size             = patch('os.path.getsize').start()
        self.mock_open                 = patch('builtins.open').start()
        self.mock_ffmpeg_lossless      = patch('djmgmt.encode.ffmpeg_lossless').start()
        self.mock_ffmpeg_lossless_flac = patch('djmgmt.encode.ffmpeg_lossless_flac').start()
        self.mock_skip_bit_depth       = patch('djmgmt.encode.check_skip_bit_depth').start()
        self.mock_skip_sample_rate     = patch('djmgmt.encode.check_skip_sample_rate').start()
        self.mock_collect_paths        = patch('djmgmt.common.collect_paths').start()
        self.mock_input                = patch('builtins.input').start()
        self.mock_setup_storage        = patch('djmgmt.encode.setup_storage').start()
        self.mock_run_command_async    = patch('djmgmt.encode.run_command_async').start()
        self.mock_subprocess_run       = patch('subprocess.run').start()
        self.mock_log_dry_run          = patch('djmgmt.common.log_dry_run').start()
        self.addCleanup(patch.stopall)

        # Shared defaults
        self.mock_skip_bit_depth.return_value   = False
        self.mock_skip_sample_rate.return_value = False

    async def test_success_async_single_batch(self) -> None:
        '''Tests that a single file can be processed asynchrounously.'''
        # Set up mocks
        self.mock_collect_paths.return_value = [f'{MOCK_INPUT}/file_0.aif']

        # Call target function, encoding to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, extension='.aiff')

        # Assert that methods depending on optional arguments are not called.
        self.mock_setup_storage.assert_not_called()
        self.mock_input.assert_not_called()

        # Assert that bit depth and sample rate were only checked for the AIF file;
        # WAV files should always be processed without checking this data.
        self.assertTrue(self.mock_skip_sample_rate.call_count == 1 or self.mock_skip_bit_depth.call_count == 1)

        # Assert expected calls for each input file
        self.mock_ffmpeg_lossless.assert_has_calls([
            call(f"{MOCK_INPUT}/file_0.aif", f"{MOCK_OUTPUT}/file_0.aiff"),
        ])

        # Assert no file was opened, as only default 'encode_lossless' arguments were used
        self.mock_open.assert_not_called()

        # Assert that getsize was called for input and output for each track
        self.assertEqual(self.mock_get_size.call_count, 2)

        # Assert the expected function output result
        self.assertEqual(actual, [
            (f"{MOCK_INPUT}/file_0.aif", f"{MOCK_OUTPUT}/file_0.aiff")
        ])

        # Async expectations
        self.mock_run_command_async.assert_called_once()

    async def test_success_async_multiple_batches(self) -> None:
        '''Test that an amount of files exceeding the given thread count processes all files.'''
        # Set up mocks
        self.mock_collect_paths.return_value = [f'{MOCK_INPUT}/file_{i}.aif' for i in range(5)]

        # Call target function, encoding to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, extension='.aiff', threads=4)

        # Assert that methods depending on optional arguments are not called.
        self.mock_setup_storage.assert_not_called()
        self.mock_input.assert_not_called()

        # Assert that bit depth and sample rate were only checked for the AIF file;
        # WAV files should always be processed without checking this data.
        self.assertTrue(self.mock_skip_sample_rate.call_count == 5 or self.mock_skip_bit_depth.call_count == 5)

        # Assert expected calls for each input file
        self.mock_ffmpeg_lossless.assert_has_calls([
            call(f"{MOCK_INPUT}/file_{i}.aif", f"{MOCK_OUTPUT}/file_{i}.aiff") for i in range(5)
        ])

        # Assert no file was opened, as only default 'encode_lossless' arguments were used
        self.mock_open.assert_not_called()

        # Assert that getsize was called for input and output for each track
        self.assertEqual(self.mock_get_size.call_count, 10)

        # Assert the expected function output result
        self.assertEqual(actual, [
            (f"{MOCK_INPUT}/file_{i}.aif", f"{MOCK_OUTPUT}/file_{i}.aiff") for i in range(5)
        ])

        # Async expectations
        # One task and command should be created for each file
        self.assertEqual(self.mock_run_command_async.call_count, 5)

    async def test_success_no_extension(self) -> None:
        '''Tests that the output files retain their corresponding input extensions if no extension provided.'''
        # Setup mocks
        mock_paths = [os.path.join(MOCK_INPUT, 'file_0.aif'), os.path.join(MOCK_INPUT, 'file_1.wav')]
        self.mock_collect_paths.return_value = mock_paths

        # Call target function, no extension given
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, threads=4)

        # Assert expectations
        expected = [
            (mock_paths[0], os.path.join(MOCK_OUTPUT, 'file_0.aif')),
            (mock_paths[1], os.path.join(MOCK_OUTPUT, 'file_1.wav'))
        ]
        self.assertListEqual(actual, expected)

    async def test_success_optional_store_path(self) -> None:
        '''Tests that passing the optional store_path argument succeeds.'''
        # Setup mocks
        self.mock_collect_paths.return_value = [f'{MOCK_INPUT}/file_0.aif', f'{MOCK_INPUT}/file_1.wav']

        # Call target function, encoding to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, '.aiff', store_path_dir='/mock/store/path')

        # Assert that storage is set up once and opened to write each file and the cumulative file size.
        self.mock_setup_storage.assert_called_once()
        self.assertEqual(self.mock_open.call_count, 3)

        # Ensure the argument does not disrupt other expected/unexpected calls
        self.mock_input.assert_not_called()
        self.mock_ffmpeg_lossless.assert_called()
        self.mock_get_size.assert_called()

        # Assert the expected function output result
        self.assertEqual(actual, [
            (f"{MOCK_INPUT}/file_0.aif", f"{MOCK_OUTPUT}/file_0.aiff"),
            (f"{MOCK_INPUT}/file_1.wav", f"{MOCK_OUTPUT}/file_1.aiff"),
        ])

    async def test_success_optional_store_skipped(self) -> None:
        '''Tests that passing the optional store_skipped argument succeeds.'''
        # Setup mocks
        self.mock_collect_paths.return_value = [f'{MOCK_INPUT}/file_0.aif', f'{MOCK_INPUT}/file_1.aiff']

        # Mock that first file needs encoding, second file does not and will be skipped
        self.mock_skip_bit_depth.side_effect = [False, True]
        self.mock_skip_sample_rate.return_value = [False, True]

        # Call target function, encoding to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, '.aiff', store_path_dir='/mock/store/path', store_skipped=True)

        # Assert that storage is set up twice and opened to write each file and the cumulative file size.
        self.assertEqual(self.mock_setup_storage.call_count, 2)
        self.assertEqual(self.mock_open.call_count, 2)

        # Ensure the argument does not disrupt other expected/unexpected calls
        self.mock_input.assert_not_called()
        self.mock_ffmpeg_lossless.assert_called()
        self.mock_get_size.assert_called()

        # Assert the expected function output result -- the second file should be skipped
        self.assertEqual(actual, [
            (f"{MOCK_INPUT}/file_0.aif", f"{MOCK_OUTPUT}/file_0.aiff")
        ])

    async def test_dry_run_skips_encoding(self) -> None:
        '''Test encode_lossless with dry_run skips ffmpeg execution and file writes.'''
        # Setup mocks
        mock_paths = [f'{MOCK_INPUT}/file_0.aif', f'{MOCK_INPUT}/file_1.wav']
        self.mock_collect_paths.return_value = mock_paths

        # Call target function with dry_run=True
        result = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, '.aiff', dry_run=True)

        # Assert expectations
        ## Should NOT run ffmpeg
        self.mock_run_command_async.assert_not_called()

        ## Should NOT write storage files
        self.mock_open.assert_not_called()

        ## Should log dry-run operations
        self.assertGreater(self.mock_log_dry_run.call_count, 0)

        ## Should return expected mappings
        expected = [
            (mock_paths[0], f'{MOCK_OUTPUT}/file_0.aiff'),
            (mock_paths[1], f'{MOCK_OUTPUT}/file_1.aiff')
        ]
        self.assertListEqual(result, expected)

    async def test_success_unsupported_files(self) -> None:
        '''Tests that unsupported files are not processed.'''
        # Setup mocks: collect_paths returns empty because it filters out unsupported extensions
        self.mock_collect_paths.return_value = []

        # Call target function, encoding to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, '.aiff')

        # Assert unexpected calls, as most of the functionality should be skipped with unsupported files as input
        self.mock_setup_storage.assert_not_called()
        self.mock_input.assert_not_called()
        self.mock_skip_sample_rate.assert_not_called()
        self.mock_skip_bit_depth.assert_not_called()
        self.mock_ffmpeg_lossless.assert_not_called()
        self.mock_subprocess_run.assert_not_called()
        self.mock_open.assert_not_called()
        self.mock_get_size.assert_not_called()

        # Assert the expected function output result -- should be empty for unsupported files
        self.assertListEqual(actual, [])

    async def test_success_flac_input(self) -> None:
        '''Tests that a FLAC input file is processed and uses ffmpeg_lossless when output is AIFF.'''
        # Setup mocks
        self.mock_collect_paths.return_value = [os.path.join(MOCK_INPUT, 'file_0.flac')]

        # Call target function, encoding FLAC to AIFF
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, extension='.aiff')

        # Assert FLAC input uses the standard lossless command for AIFF output
        self.mock_ffmpeg_lossless.assert_called_once_with(
            os.path.join(MOCK_INPUT, 'file_0.flac'),
            os.path.join(MOCK_OUTPUT, 'file_0.aiff')
        )
        self.mock_ffmpeg_lossless_flac.assert_not_called()
        self.mock_run_command_async.assert_called_once()

        # No file writes (no store_path_dir set); getsize called for input and output
        self.mock_open.assert_not_called()
        self.assertEqual(self.mock_get_size.call_count, 2)

        # Assert the expected function output result
        self.assertListEqual(actual, [
            (os.path.join(MOCK_INPUT, 'file_0.flac'), os.path.join(MOCK_OUTPUT, 'file_0.aiff'))
        ])

    async def test_success_flac_output(self) -> None:
        '''Tests that encoding to FLAC output uses ffmpeg_lossless_flac.'''
        # Setup mocks
        self.mock_collect_paths.return_value = [os.path.join(MOCK_INPUT, 'file_0.aiff')]

        # Call target function, encoding to FLAC
        actual = await encode.encode_lossless(MOCK_INPUT, MOCK_OUTPUT, extension='.flac')

        # Assert FLAC output uses the FLAC-specific command
        self.mock_ffmpeg_lossless_flac.assert_called_once_with(
            os.path.join(MOCK_INPUT, 'file_0.aiff'),
            os.path.join(MOCK_OUTPUT, 'file_0.flac')
        )
        self.mock_ffmpeg_lossless.assert_not_called()
        self.mock_run_command_async.assert_called_once()

        # No file writes (no store_path_dir set); getsize called for input and output
        self.mock_open.assert_not_called()
        self.assertEqual(self.mock_get_size.call_count, 2)

        # Assert the expected function output result
        self.assertListEqual(actual, [
            (os.path.join(MOCK_INPUT, 'file_0.aiff'), os.path.join(MOCK_OUTPUT, 'file_0.flac'))
        ])


class TestEncodeLossy(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_makedirs          = patch('os.makedirs').start()
        self.mock_path_exists       = patch('os.path.exists').start()
        self.mock_read_ffprobe_json = patch('djmgmt.encode.read_ffprobe_json').start()
        self.mock_guess_cover       = patch('djmgmt.encode.guess_cover_stream_specifier').start()
        self.mock_ffmpeg_lossy      = patch('djmgmt.encode.ffmpeg_lossy').start()
        self.mock_run_command_async = patch('djmgmt.encode.run_command_async').start()
        self.mock_log_dry_run       = patch('djmgmt.common.log_dry_run').start()
        self.addCleanup(patch.stopall)

        # Shared defaults
        self.mock_path_exists.return_value = False
        self.mock_guess_cover.return_value = -1

    async def test_success_required_arguments(self) -> None:
        # Call target function
        SOURCE_FILE = f'{MOCK_INPUT}{os.sep}file_0.aiff'
        DEST_FILE = f'{MOCK_OUTPUT}{os.sep}file_0.mp3'
        mappings = [(SOURCE_FILE, f'{MOCK_OUTPUT}{os.sep}file_0.aiff')]
        result = await encode.encode_lossy(mappings, '.mp3')

        # Assert expectations
        ## Path does not exist, so expect makedirs to be called
        self.mock_makedirs.assert_called_once_with(MOCK_OUTPUT)

        ## Expect these calls once for the single mapping
        self.mock_read_ffprobe_json.assert_called_once_with(SOURCE_FILE)
        self.mock_guess_cover.assert_called_once_with(self.mock_read_ffprobe_json.return_value)
        self.mock_ffmpeg_lossy.assert_called_once_with(SOURCE_FILE, DEST_FILE, map_options=f'-map 0:0')
        self.mock_run_command_async.assert_called_once()

        ## Should return list of mappings
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (SOURCE_FILE, DEST_FILE))

    async def test_dry_run_skips_encoding(self) -> None:
        '''Test encode_lossy with dry_run skips ffmpeg execution and makedirs.'''
        # Call target function with dry_run=True
        SOURCE_FILE = f'{MOCK_INPUT}{os.sep}file_0.aiff'
        DEST_FILE = f'{MOCK_OUTPUT}{os.sep}file_0.mp3'
        mappings = [(SOURCE_FILE, f'{MOCK_OUTPUT}{os.sep}file_0.aiff')]
        result = await encode.encode_lossy(mappings, '.mp3', dry_run=True)

        # Assert expectations
        ## Should NOT create directories
        self.mock_makedirs.assert_not_called()

        ## Should NOT run ffmpeg
        self.mock_run_command_async.assert_not_called()

        ## Should log dry-run operation
        self.mock_log_dry_run.assert_called_once()
        self.assertIn('encode', self.mock_log_dry_run.call_args[0][0])

        ## Should return list of mappings
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], SOURCE_FILE)
        self.assertEqual(result[0][1], DEST_FILE)


class TestMain(unittest.TestCase):
    def setUp(self) -> None:
        patch('sys.stdout', new=io.StringIO()).start()
        self.mock_configure_log = patch('djmgmt.common.configure_log_module').start()
        self.addCleanup(patch.stopall)

    @patch('djmgmt.encode.encode_lossless', new_callable=AsyncMock)
    def test_lossless(self, mock_encode: AsyncMock) -> None:
        '''Tests that main() dispatches to encode_lossless with the correct arguments.'''
        encode.main(['encode', Namespace.FUNCTION_LOSSLESS,
                     '--input', MOCK_INPUT, '--output', MOCK_OUTPUT,
                     '--extension', '.aiff', '--store-path', '/mock/store',
                     '--store-skipped', '--dry-run'])

        mock_encode.assert_called_once_with(MOCK_INPUT, MOCK_OUTPUT,
                                            extension='.aiff',
                                            store_path_dir='/mock/store',
                                            store_skipped=True,
                                            dry_run=True)

    @patch('djmgmt.encode.encode_lossy', new_callable=AsyncMock)
    @patch('djmgmt.common.add_output_path')
    @patch('djmgmt.common.collect_paths')
    def test_lossy(self,
                   mock_collect_paths: MagicMock,
                   mock_add_output_path: MagicMock,
                   mock_encode: AsyncMock) -> None:
        '''Tests that main() dispatches to encode_lossy with the correct arguments.'''
        encode.main(['encode', Namespace.FUNCTION_LOSSY,
                     '--input', MOCK_INPUT, '--output', MOCK_OUTPUT,
                     '--extension', '.mp3'])

        mock_collect_paths.assert_called_once_with(MOCK_INPUT)
        mock_add_output_path.assert_called_once_with(MOCK_OUTPUT, mock_collect_paths.return_value, MOCK_INPUT)
        mock_encode.assert_called_once_with(mock_add_output_path.return_value, '.mp3', dry_run=False)

    @patch('djmgmt.common.write_paths')
    @patch('djmgmt.encode.find_missing_art_xml', new_callable=AsyncMock)
    def test_missing_art_xml(self,
                             mock_find_xml: AsyncMock,
                             mock_write_paths: MagicMock) -> None:
        '''Tests that main() dispatches to find_missing_art_xml and writes results.'''
        encode.main(['encode', Namespace.FUNCTION_MISSING_ART,
                     '--input', MOCK_INPUT, '--output', MOCK_OUTPUT,
                     '--scan-mode', Namespace.SCAN_MODE_XML])

        mock_find_xml.assert_called_once_with(MOCK_INPUT, constants.XPATH_COLLECTION, constants.XPATH_PRUNED, threads=72)
        mock_write_paths.assert_called_once_with(mock_find_xml.return_value, MOCK_OUTPUT)

    @patch('djmgmt.common.write_paths')
    @patch('djmgmt.encode.find_missing_art_os', new_callable=AsyncMock)
    def test_missing_art_os(self,
                            mock_find_os: AsyncMock,
                            mock_write_paths: MagicMock) -> None:
        '''Tests that main() dispatches to find_missing_art_os and writes results.'''
        encode.main(['encode', Namespace.FUNCTION_MISSING_ART,
                     '--input', MOCK_INPUT, '--output', MOCK_OUTPUT,
                     '--scan-mode', Namespace.SCAN_MODE_OS])

        mock_find_os.assert_called_once_with(MOCK_INPUT, threads=72)
        mock_write_paths.assert_called_once_with(mock_find_os.return_value, MOCK_OUTPUT)
