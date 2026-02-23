import unittest
import os
import zipfile
from argparse import Namespace
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call
from zipfile import ZipInfo
from typing import Callable

from djmgmt import music
from djmgmt import constants
from djmgmt.common import FileMapping
from djmgmt.music import RecordResult, ProcessResult
from djmgmt.sync import SyncResult, SyncBatchResult
from tests.fixtures import MOCK_INPUT_DIR, MOCK_OUTPUT_DIR

# Primary test classes
class TestCompressDir(unittest.TestCase):
    @patch('djmgmt.common.collect_paths')
    @patch('zipfile.ZipFile')
    def test_success(self,
                     mock_zipfile: MagicMock,
                     mock_collect_paths: MagicMock) -> None:
        '''Tests that a single file in the given directory is written to an archive.'''
        # Set up mocks
        mock_archive = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_archive
        mock_filepath = f"{MOCK_INPUT_DIR}/mock_file.foo"
        mock_collect_paths.return_value = [mock_filepath]
        
        # Call target function
        music.compress_dir(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        mock_zipfile.assert_called_once_with(f"{MOCK_OUTPUT_DIR}.zip", 'w', zipfile.ZIP_DEFLATED)
        mock_archive.write.assert_called_once_with(mock_filepath, arcname='mock_file.foo')

class TestFlattenZip(unittest.TestCase):
    @patch('shutil.rmtree')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('shutil.move')
    @patch('djmgmt.common.collect_paths')
    @patch('djmgmt.music.extract_all_normalized_encodings')
    def test_success(self,
                     mock_extract_all: MagicMock,
                     mock_collect_paths: MagicMock,
                     mock_move: MagicMock,
                     mock_path_exists: MagicMock,
                     mock_listdir: MagicMock,
                     mock_rmtree: MagicMock) -> None:
        '''Tests that all contents of the given zip archive are extracted, flattened into loose files, and the empty directory is removed.'''
        # Set up mocks
        mock_archive_path = f"{MOCK_INPUT_DIR}/file.zip"
        mock_filepath = f"{MOCK_INPUT_DIR}/mock_file.foo"
        mock_collect_paths.return_value = [mock_filepath]
        mock_path_exists.return_value = True
        mock_listdir.return_value = []
        
        # Call target function
        music.flatten_zip(mock_archive_path, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        mock_extract_all.assert_called_once_with(mock_archive_path, MOCK_OUTPUT_DIR)
        mock_move.assert_called_once_with(mock_filepath, MOCK_OUTPUT_DIR)
        mock_rmtree.assert_called_once_with(f"{MOCK_OUTPUT_DIR}/file")

class TestStandardizeLossless(unittest.TestCase):
    MOCK_EXTENSIONS = {'a'}
    MOCK_HINTS = {'b'}
    MOCK_TEMP_PATH = 'mock_temp_path'
    MOCK_INPUT_FILE = 'mock_input_file'

    def setUp(self) -> None:
        self.mock_temp_dir = patch('tempfile.TemporaryDirectory').start()
        self.mock_encode   = patch('djmgmt.encode.encode_lossless').start()
        self.mock_remove   = patch('os.remove').start()
        self.mock_sweep    = patch('djmgmt.music.sweep').start()
        self.addCleanup(patch.stopall)

        self.mock_temp_dir.return_value.__enter__.return_value = self.MOCK_TEMP_PATH
        self.mock_encode.return_value = [(self.MOCK_INPUT_FILE, 'mock_output_file')]

    def test_success(self) -> None:
        '''Tests that the encoding function is run and all encoded files are removed.'''
        actual = music.standardize_lossless(MOCK_INPUT_DIR, self.MOCK_EXTENSIONS, self.MOCK_HINTS)

        ## Check calls
        self.mock_temp_dir.assert_called_once()
        self.mock_encode.assert_called_once_with(MOCK_INPUT_DIR, self.MOCK_TEMP_PATH, '.aiff', dry_run=False)
        self.mock_remove.assert_called_once_with(self.MOCK_INPUT_FILE)
        self.mock_sweep.assert_called_once_with(self.MOCK_TEMP_PATH, MOCK_INPUT_DIR, self.MOCK_EXTENSIONS, self.MOCK_HINTS, dry_run=False)

        ## Check output
        self.assertEqual(actual, self.mock_encode.return_value)

    def test_success_dry_run(self) -> None:
        '''Tests that helper functions are called with dry run, and no files are removed.'''
        with self.assertLogs(level='INFO') as log_context:
            actual = music.standardize_lossless(MOCK_INPUT_DIR, self.MOCK_EXTENSIONS, self.MOCK_HINTS, dry_run=True)

        ## Check calls
        self.mock_temp_dir.assert_called_once()
        self.mock_encode.assert_called_once_with(MOCK_INPUT_DIR, self.MOCK_TEMP_PATH, '.aiff', dry_run=True)
        self.mock_remove.assert_not_called()
        self.mock_sweep.assert_called_once_with(self.MOCK_TEMP_PATH, MOCK_INPUT_DIR, self.MOCK_EXTENSIONS, self.MOCK_HINTS, dry_run=True)

        ## Check output
        self.assertEqual(actual, self.mock_encode.return_value)

        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove', dry_run_logs[0])

class TestSweep(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_collect_paths   = patch('djmgmt.common.collect_paths').start()
        self.mock_path_exists     = patch('os.path.exists').start()
        self.mock_is_prefix_match = patch('djmgmt.music.is_prefix_match').start()
        self.mock_zipfile         = patch('zipfile.ZipFile').start()
        self.mock_move            = patch('shutil.move').start()
        self.addCleanup(patch.stopall)

        self.mock_path_exists.return_value     = False
        self.mock_is_prefix_match.return_value = False

    def test_sweep_music_files(self) -> None:
        '''Test that loose music files are swept.'''
        mock_filenames = [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{p}" for p in mock_filenames]

        actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS, music.PREFIX_HINTS)

        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.assertEqual(self.mock_path_exists.call_count, len(mock_filenames))
        self.mock_is_prefix_match.assert_not_called()
        self.mock_zipfile.assert_not_called()
        self.mock_move.assert_has_calls([call(i, o) for i, o in expected])
        self.assertEqual(actual, expected)

    def test_skip_sweep_non_music_files(self) -> None:
        '''Test that loose, non-music files skipped.'''
        mock_filenames = ['track_0.foo', 'img_0.jpg', 'img_1.jpeg', 'img_2.png']
        self.mock_collect_paths.return_value = mock_filenames

        actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS, music.PREFIX_HINTS)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.assertEqual(self.mock_path_exists.call_count, len(mock_filenames))
        self.mock_is_prefix_match.assert_not_called()
        self.mock_zipfile.assert_not_called()
        self.mock_move.assert_not_called()
        self.assertEqual(actual, [])

    def test_sweep_prefix_archive(self) -> None:
        '''Test that a prefix zip archive is swept to the output directory.'''
        mock_filename = 'mock_valid_prefix.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.return_value = [mock_input_path]
        self.mock_is_prefix_match.return_value = True

        actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS, music.PREFIX_HINTS)

        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_path_exists.assert_called_once_with(expected_output_path)
        self.mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        self.mock_zipfile.assert_not_called()
        self.mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])

    def test_sweep_music_archive(self) -> None:
        '''Test that a zip containing only music files is swept to the output directory.'''
        mock_filename = 'mock_music_archive.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.return_value = [mock_input_path]

        mock_archive = MagicMock()
        mock_archive.namelist.return_value = [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        self.mock_zipfile.return_value.__enter__.return_value = mock_archive

        actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS, music.PREFIX_HINTS)

        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_path_exists.assert_called_once_with(expected_output_path)
        self.mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        self.mock_zipfile.assert_called_once()
        self.mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])

    def test_sweep_album_archive(self) -> None:
        '''Test that a zip containing music files and a cover photo is swept to the output directory.'''
        mock_filename = 'mock_album_archive.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.return_value = [mock_input_path]

        mock_archive = MagicMock()
        mock_archive.namelist.return_value  = [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        mock_archive.namelist.return_value += ['mock_cover.jpg']
        self.mock_zipfile.return_value.__enter__.return_value = mock_archive

        actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS, music.PREFIX_HINTS)

        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_path_exists.assert_called_once_with(expected_output_path)
        self.mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        self.mock_zipfile.assert_called_once()
        self.mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])

    def test_dry_run(self) -> None:
        '''Test that dry_run=True skips file moves and logs operations.'''
        mock_filenames = ['track1.mp3', 'track2.aiff']
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{p}" for p in mock_filenames]

        with self.assertLogs(level='INFO') as log_context:
            actual = music.sweep(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, constants.EXTENSIONS,
                                 music.PREFIX_HINTS, dry_run=True)

        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[0]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[0]}"),
            (f"{MOCK_INPUT_DIR}/{mock_filenames[1]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[1]}")
        ]

        self.mock_move.assert_not_called()
        self.assertListEqual(actual, expected)

        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 2)
        self.assertIn('move', dry_run_logs[0])
        self.assertIn('move', dry_run_logs[1])

class TestFlattenHierarchy(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_collect_paths = patch('djmgmt.common.collect_paths').start()
        self.mock_path_exists   = patch('os.path.exists').start()
        self.mock_move          = patch('shutil.move').start()
        self.addCleanup(patch.stopall)

        self.mock_path_exists.return_value = False

    def test_success_output_path_not_exists(self) -> None:
        '''Tests that all loose files at the input root are flattened to output.'''
        mock_filenames = [f"file_{i}.foo" for i in range(3)]
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]

        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_move.assert_has_calls([call(i, o) for i, o in expected])
        self.assertEqual(actual, expected)

    def test_success_output_path_exists(self) -> None:
        '''Tests that a file is flattened only if its output path doesn't exist.'''
        mock_filenames = [f"file_{i}.foo" for i in range(3)]
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]
        self.mock_path_exists.side_effect = [False, True, True]

        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        expected_input  = f"{MOCK_INPUT_DIR}/{mock_filenames[0]}"
        expected_output = f"{MOCK_OUTPUT_DIR}/{mock_filenames[0]}"
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_move.assert_called_once_with(expected_input, expected_output)
        self.assertEqual(actual, [(expected_input, expected_output)])

    def test_success_dry_run(self) -> None:
        '''Tests that no files are moved, but the dry run results are still returned.'''
        mock_filenames = [f"file_{i}.foo" for i in range(2)]
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]

        with self.assertLogs(level='INFO') as log_context:
            actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, dry_run=True)

        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_move.assert_not_called()
        self.assertEqual(actual, expected)

        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 2)
        self.assertIn('move', dry_run_logs[0])
        self.assertIn('move', dry_run_logs[1])

class TestExtractAllNormalizedEncodings(unittest.TestCase):
    @patch('zipfile.ZipFile')
    def test_success_fix_filename_encoding(self,
                                           mock_zipfile: MagicMock) -> None:
        '''Tests that all contents of a zip archive are extracted and their filenames normalized.'''
        # Set up mocks
        mock_archive_path = f"{MOCK_INPUT_DIR}/archive.zip"
        
        mock_archive = MagicMock()
        mock_archive.infolist.return_value = [
            ZipInfo(filename='Agoria ft Nin╠âo de Elche - What if earth would turn faster.aiff'),
            ZipInfo(filename='Mariachi Los Camperos - El toro viejo ΓÇö The Old Bull.aiff'),
            ZipInfo(filename='aplicac╠ºo╠âes.mp3'),
            ZipInfo(filename='├ÿostil - Quantic (Original Mix).mp3'),
            ZipInfo(filename='Leitstrahl & Alberto Melloni - Automaton Lover Feat. Furo╠ür Exotica.mp3'),
            ZipInfo(filename='maxtaylorΓÖÜ - summer17 - 08 bumpin.aiff'),
            ZipInfo(filename='Iron Curtis & Johannes Albert - Something Unique feat. Zoot Woman (Johannes Albert Italo Mix).aiff') # no bungled characters
        ]
        
        mock_zipfile.return_value.__enter__.return_value = mock_archive
        
        # Call target function
        actual = music.extract_all_normalized_encodings(mock_archive_path, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        ## Dependent functions called
        mock_zipfile.assert_called_once_with(mock_archive_path, 'r')
        
        ## Check for normalized characters in output list
        expected_filenames = [
            'Agoria ft Niño de Elche - What if earth would turn faster.aiff',
            'Mariachi Los Camperos - El toro viejo — The Old Bull.aiff',
            'aplicações.mp3',
            'Øostil - Quantic (Original Mix).mp3',
            'Leitstrahl & Alberto Melloni - Automaton Lover Feat. Furór Exotica.mp3',
            'maxtaylor♚ - summer17 - 08 bumpin.aiff',
            'Iron Curtis & Johannes Albert - Something Unique feat. Zoot Woman (Johannes Albert Italo Mix).aiff'
        ]
        
        ## Check extract calls
        self.assertEqual(mock_archive.extract.call_args_list[0].args[0].filename, expected_filenames[0])
        self.assertEqual(mock_archive.extract.call_args_list[1].args[0].filename, expected_filenames[1])
        self.assertEqual(mock_archive.extract.call_args_list[2].args[0].filename, expected_filenames[2])
        self.assertEqual(mock_archive.extract.call_args_list[3].args[0].filename, expected_filenames[3])
        self.assertEqual(mock_archive.extract.call_args_list[4].args[0].filename, expected_filenames[4])
        self.assertEqual(mock_archive.extract.call_args_list[5].args[0].filename, expected_filenames[5])
        self.assertEqual(mock_archive.extract.call_args_list[6].args[0].filename, expected_filenames[6])
        
        ## Check output
        expected = (mock_archive_path, expected_filenames)
        self.assertEqual(actual, expected)
        
        ## Check output dir
        for i in range(mock_archive.extract.call_count):
            self.assertEqual(mock_archive.extract.call_args_list[i].args[1], MOCK_OUTPUT_DIR)
        
        ## Total extract calls
        self.assertEqual(mock_archive.extract.call_count, 7)
    
    @patch('zipfile.ZipFile')
    def test_success_empty_zip(self,
                               mock_zipfile: MagicMock) -> None:
        '''Tests that an empty list is returned if there are no zip contents.'''
        # Set up mocks
        mock_archive_path = f"{MOCK_INPUT_DIR}/archive.zip"
        
        mock_archive = MagicMock()
        mock_archive.infolist.return_value = []
        
        mock_zipfile.return_value.__enter__.return_value = mock_archive
        
        # Call target function
        actual = music.extract_all_normalized_encodings(mock_archive_path, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        ## Dependent functions called
        mock_zipfile.assert_called_once_with(mock_archive_path, 'r')
        
        self.assertEqual(actual, (mock_archive_path, []))
        
    @patch('zipfile.ZipFile')
    def test_success_dry_run(self,
                            mock_zipfile: MagicMock) -> None:
        '''Tests that dry_run returns filenames without extracting.'''
        # Set up mocks
        mock_archive_path = f"{MOCK_INPUT_DIR}/archive.zip"

        mock_info_0 = MagicMock(spec=ZipInfo)
        mock_info_0.filename = 'file_0'
        mock_info_1 = MagicMock(spec=ZipInfo)
        mock_info_1.filename = 'file_1'

        mock_archive = MagicMock()
        mock_archive.infolist.return_value = [mock_info_0, mock_info_1]

        mock_zipfile.return_value.__enter__.return_value = mock_archive

        # Call target function
        actual = music.extract_all_normalized_encodings(mock_archive_path, MOCK_OUTPUT_DIR, dry_run=True)

        # Assert expectations
        ## ZipFile opened
        mock_zipfile.assert_called_once_with(mock_archive_path, 'r')

        ## Returns correct structure
        self.assertEqual(actual, (mock_archive_path, ['file_0', 'file_1']))

        ## Extract method NOT called on archive for any info object during dry run
        mock_archive.extract.assert_not_called()

class TestExtract(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_collect_paths = patch('djmgmt.common.collect_paths').start()
        self.mock_path_exists   = patch('os.path.exists').start()
        self.mock_isdir         = patch('os.path.isdir').start()
        self.mock_extract_all   = patch('djmgmt.music.extract_all_normalized_encodings').start()
        self.addCleanup(patch.stopall)
        self.mock_path_exists.return_value = False
        self.mock_isdir.return_value = False

    def test_success(self) -> None:
        '''Tests that all zip archives are extracted.'''
        # Set up mocks
        mock_filename = 'mock_archive.zip'
        mock_file_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        self.mock_collect_paths.return_value = [mock_file_path]
        self.mock_extract_all.return_value = (mock_filename, ['mock_file_0', 'mock_file_1'])

        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_extract_all.assert_called_once_with(mock_file_path, MOCK_OUTPUT_DIR, dry_run=False)
        self.assertEqual(actual, [self.mock_extract_all.return_value])

    def test_success_no_zip_present(self) -> None:
        '''Tests that nothing is extracted if there are no zip archives present in the input directory.'''
        # Set up mocks
        mock_file_path = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        self.mock_collect_paths.return_value = [mock_file_path]

        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_extract_all.assert_not_called()
        self.assertEqual(actual, [])

    def test_success_output_exists(self) -> None:
        '''Tests that nothing is extracted if the output directory exists.'''
        # Set up mocks
        mock_filename = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        self.mock_collect_paths.return_value = [mock_filename]
        self.mock_path_exists.return_value = True
        self.mock_isdir.return_value = True

        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_extract_all.assert_not_called()
        self.assertEqual(actual, [])

class TestCompressAllCLI(unittest.TestCase):
    '''Even though this function calls os.walk, it's not a good use case for common.collect_paths,
    because that collects all absolute filepaths. The music.compress_all_cli function needs all directories, not file paths.'''
    
    @patch('djmgmt.music.compress_dir')
    @patch('os.walk')
    def test_success(self,
                     mock_walk: MagicMock,
                     mock_compress_dir: MagicMock) -> None:
        '''Tests that all directories within a source directory are compressed.'''
        # mock_paths = [f"{MOCK_INPUT_DIR}/mock_dir_0/file_0.foo", f"{MOCK_INPUT_DIR}/mock/nested/file_1.foo"]
        mock_walk.return_value = [(MOCK_INPUT_DIR, ['mock_dir_0', 'mock_dir_1'], []),
                                  (f"{MOCK_INPUT_DIR}/mock_dir_0", [], ['file_0.foo']),
                                  (f"{MOCK_INPUT_DIR}/mock_dir_1", ['nested'], []),
                                  (f"{MOCK_INPUT_DIR}/mock_dir_1/nested", [], ['file_1.foo'])]
        
        # Call target function
        args = Namespace(input=MOCK_INPUT_DIR, output=MOCK_OUTPUT_DIR)
        music.compress_all_cli(args) # type: ignore
        
        # Assert expectations: all directories and subdirectories should be compressed
        mock_walk.assert_called_once_with(MOCK_INPUT_DIR)
        mock_compress_dir.assert_has_calls([
            call(f"{MOCK_INPUT_DIR}/mock_dir_0", f"{MOCK_OUTPUT_DIR}/mock_dir_0"),
            call(f"{MOCK_INPUT_DIR}/mock_dir_1", f"{MOCK_OUTPUT_DIR}/mock_dir_1"),
            call(f"{MOCK_INPUT_DIR}/mock_dir_1/nested", f"{MOCK_OUTPUT_DIR}/nested")
        ])

class TestPruneNonUserDirs(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_get_dirs     = patch('djmgmt.music.get_dirs').start()
        self.mock_is_empty_dir = patch('djmgmt.music.has_no_user_files').start()
        self.mock_rmtree       = patch('shutil.rmtree').start()
        self.addCleanup(patch.stopall)

        self.mock_get_dirs.return_value     = ['mock_empty_dir']
        self.mock_is_empty_dir.return_value = True

    def test_success_remove_empty_dir(self) -> None:
        '''Test that prune removes an empty directory.'''
        actual = music.prune_non_user_dirs('/mock/source/')

        expected_path = '/mock/source/mock_empty_dir'
        self.mock_get_dirs.assert_called()
        self.mock_is_empty_dir.assert_called()
        self.mock_rmtree.assert_called_once_with(expected_path)
        self.assertListEqual(actual, [expected_path])

    def test_success_skip_non_empty_dir(self) -> None:
        '''Test that prune does not remove a non-empty directory.'''
        self.mock_get_dirs.side_effect     = [['mock_non_empty_dir'], []]
        self.mock_is_empty_dir.return_value = False

        actual = music.prune_non_user_dirs('/mock/source/')

        self.mock_get_dirs.assert_called()
        self.mock_is_empty_dir.assert_called()
        self.mock_rmtree.assert_not_called()
        self.assertListEqual(actual, [])

    def test_dry_run(self) -> None:
        '''Test that dry_run=True skips directory removal and logs operations.'''
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_user_dirs('/mock/source/', dry_run=True)

        expected_path = '/mock/source/mock_empty_dir'
        self.mock_get_dirs.assert_called()
        self.mock_is_empty_dir.assert_called()
        self.mock_rmtree.assert_not_called()
        self.assertListEqual(actual, [expected_path])

        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove directory', dry_run_logs[0])
        self.assertIn(expected_path, dry_run_logs[0])

    @patch('djmgmt.music.prune_non_user_dirs')
    def test_success_cli(self, mock_prune_empty: MagicMock) -> None:
        '''Tests that the CLI wrapper calls the correct function.'''
        args = Namespace(input=MOCK_INPUT_DIR, interactive=False)
        music.prune_non_user_dirs_cli(args) # type: ignore

        mock_prune_empty.assert_called_once_with(MOCK_INPUT_DIR, False)

class TestPruneNonMusicFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_collect_paths = patch('djmgmt.common.collect_paths').start()
        self.mock_isdir         = patch('os.path.isdir').start()
        self.mock_os_remove     = patch('os.remove').start()
        self.mock_rmtree        = patch('shutil.rmtree').start()
        self.addCleanup(patch.stopall)
        self.mock_isdir.return_value = False

    def test_success_remove_non_music(self) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock_file.foo']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_called_once_with('/mock/source/mock_file.foo')
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_skip_music(self) -> None:
        '''Tests that top-level music files are not removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, [])

    def test_success_skip_music_subdirectory(self) -> None:
        '''Tests that nested music files are not removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, [])

    def test_success_remove_non_music_subdirectory(self) -> None:
        '''Tests that nested non-music files are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock/dir/0/mock_file.foo']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_called_once_with('/mock/source/mock/dir/0/mock_file.foo')
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_remove_hidden_file(self) -> None:
        '''Tests that hidden files are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/.mock_hidden']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden')
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_remove_zip_archive(self) -> None:
        '''Tests that zip archives are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock.zip']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_called_once_with('/mock/source/mock.zip')
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_remove_app(self) -> None:
        '''Tests that .app archives are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock.app']
        self.mock_isdir.return_value = True

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_called_once_with('/mock/source/mock.app')

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_skip_music_hidden_dir(self) -> None:
        '''Tests that music files in a hidden directory are not removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock_music.mp3']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, [])

    def test_success_remove_non_music_hidden_dir(self) -> None:
        '''Tests that non-music files in a hidden directory are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock.foo']

        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden_dir/mock.foo')
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

    def test_success_dry_run_file(self) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock_file.foo']

        # Call target function and assert expectations
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, dry_run=True)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove', dry_run_logs[0])

    def test_success_dry_run_directory(self) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        self.mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        self.mock_isdir.return_value = True

        # Call target function and assert expectations
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, dry_run=True)

        self.mock_collect_paths.assert_called_once_with('/mock/source/')
        self.mock_isdir.assert_called_once()
        self.mock_os_remove.assert_not_called()
        self.mock_rmtree.assert_not_called()

        self.assertListEqual(actual, self.mock_collect_paths.return_value)

        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove directory', dry_run_logs[0])

    @patch('djmgmt.music.prune_non_music')
    def test_success_cli(self, mock_prune_non_music: MagicMock) -> None:
        '''Tests that the CLI wrapper function exists and is called properly.'''
        # Call target function and assert expectations
        mock_namespace = Namespace(input='/mock/input/', output='/mock/output/', interactive=False)
        music.prune_non_music_cli(mock_namespace, set())  # type: ignore
        mock_prune_non_music.assert_called_once_with(mock_namespace.input, set(), mock_namespace.interactive)

class TestProcess(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_sweep                = patch('djmgmt.music.sweep').start()
        self.mock_extract              = patch('djmgmt.music.extract').start()
        self.mock_flatten              = patch('djmgmt.music.flatten_hierarchy').start()
        self.mock_prune_empty          = patch('djmgmt.music.prune_non_user_dirs').start()
        self.mock_prune_non_music      = patch('djmgmt.music.prune_non_music').start()
        self.mock_standardize_lossless = patch('djmgmt.music.standardize_lossless').start()
        self.mock_find_missing_art_os  = patch('djmgmt.encode.find_missing_art_os').start()
        self.mock_write_paths          = patch('djmgmt.common.write_paths').start()
        self.addCleanup(patch.stopall)

    def test_success(self) -> None:
        '''Tests that the process function calls the expected functions in the correct order and returns expected ProcessResults.'''
        # Set up mocks with return values for tracking execution order
        mock_call_container = MagicMock()

        # Configure sweep to return realistic data for both calls
        def sweep_side_effect(*args: object, **kwargs: object) -> list[FileMapping]:
            mock_call_container.sweep()
            # Return different data for first and second calls
            if mock_call_container.sweep.call_count == 1:
                # First sweep: source → temp
                return [
                    ('/source/track1.mp3', '/tmp/xyz/track1.mp3'),
                    ('/source/track2.wav', '/tmp/xyz/track2.wav'),
                    ('/source/archive.zip', '/tmp/xyz/archive.zip')
                ]
            else:
                # Second sweep: temp → output
                return [
                    ('/tmp/xyz/track1.mp3', '/output/track1.mp3'),
                    ('/tmp/xyz/track2.aiff', '/output/track2.aiff'),
                    ('/tmp/xyz/extracted_track.mp3', '/output/extracted_track.mp3')
                ]

        # Configure return values for statistics
        extract_result = [
            ('/tmp/xyz/archive.zip', ['/tmp/xyz/extracted_track.mp3'])
        ]
        standardize_result = [
            ('/tmp/xyz/track2.wav', '/tmp/xyz/track2.aiff')
        ]
        missing_art_result = ['/output/track1.mp3']

        self.mock_sweep.side_effect = sweep_side_effect
        self.mock_extract.side_effect = lambda *_, **__: (mock_call_container.extract(), extract_result)[1]
        self.mock_flatten.side_effect = lambda *_, **__: (mock_call_container.flatten(), [])[1]
        self.mock_prune_empty.side_effect = lambda *_, **__: (mock_call_container.prune_non_user_dirs(), [])[1]
        self.mock_prune_non_music.side_effect = lambda *_, **__: (mock_call_container.prune_non_music(), [])[1]
        self.mock_standardize_lossless.side_effect = lambda *_, **__: (mock_call_container.standardize_lossless(), standardize_result)[1]
        self.mock_find_missing_art_os.side_effect = lambda *_, **__: (mock_call_container.find_missing_art_os(), missing_art_result)[1]
        self.mock_write_paths.side_effect = lambda *_, **__: (mock_call_container.write_paths(), None)[1]

        # Call target function
        mock_valid_extensions = {'a'}
        mock_prefix_hints = {'b'}
        result = music.process(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, mock_valid_extensions, mock_prefix_hints)

        # Assert that the primary dependent functions are called in the correct order
        self.assertEqual(mock_call_container.mock_calls[0], call.sweep())
        self.assertEqual(mock_call_container.mock_calls[1], call.extract())
        self.assertEqual(mock_call_container.mock_calls[2], call.flatten())
        self.assertEqual(mock_call_container.mock_calls[3], call.standardize_lossless())
        self.assertEqual(mock_call_container.mock_calls[4], call.prune_non_music())
        self.assertEqual(mock_call_container.mock_calls[5], call.prune_non_user_dirs())
        self.assertEqual(mock_call_container.mock_calls[6], call.find_missing_art_os())
        self.assertEqual(mock_call_container.mock_calls[7], call.sweep())
        self.assertEqual(mock_call_container.mock_calls[8], call.write_paths())

        # Assert call counts and parameters
        self.assertEqual(self.mock_sweep.call_count, 2)
        self.mock_extract.assert_called_once()
        self.mock_flatten.assert_called_once()

        # find_missing_art_os should be called with processing_dir (temp directory), not output
        # The exact temp dir path varies, so we just verify it's called once with some directory
        self.mock_find_missing_art_os.assert_called_once()

        self.assertEqual(missing_art_result, self.mock_write_paths.call_args.args[0])

        # Assert return value structure and type
        self.assertIsInstance(result, music.ProcessResult)
        self.assertIsInstance(result.processed_files, list)
        self.assertIsInstance(result.missing_art_paths, list)
        self.assertIsInstance(result.archives_extracted, int)
        self.assertIsInstance(result.files_encoded, int)

        # Assert processed files mapped correctly
        expected_processed_files = [('/source/track1.mp3', '/output/track1.mp3'),
                                    ('/source/track2.wav', '/output/track2.aiff'),
                                    ('/source/archive.zip/extracted_track.mp3', '/output/extracted_track.mp3')]
        self.assertListEqual(result.processed_files, expected_processed_files)

        # Assert statistics
        self.assertEqual(result.archives_extracted, 1)
        self.assertEqual(result.files_encoded, 1)
        self.assertEqual(len(result.missing_art_paths), 1)
        self.assertIn('/output/track1.mp3', result.missing_art_paths)

    def test_dry_run(self) -> None:
        '''Test that dry_run=True uses copy mode for initial sweep, skips final sweep operations, and preserves source files.'''
        # Configure sweep to return realistic data for both calls
        def sweep_side_effect(*args: object, **kwargs: object) -> list[FileMapping]:
            # Return different data for first and second calls
            if self.mock_sweep.call_count == 1:
                # First sweep: source → temp (should use copy_instead_of_move=True)
                return [
                    ('/source/track1.mp3', '/tmp/xyz/track1.mp3'),
                    ('/source/track2.wav', '/tmp/xyz/track2.wav')
                ]
            else:
                # Second sweep: temp → output (should have dry_run=True)
                return [
                    ('/tmp/xyz/track1.mp3', '/output/track1.mp3'),
                    ('/tmp/xyz/track2.aiff', '/output/track2.aiff')
                ]

        # Configure return values
        standardize_result = [
            ('/tmp/xyz/track2.wav', '/tmp/xyz/track2.aiff')
        ]
        missing_art_result = ['/tmp/xyz/track1.mp3']

        self.mock_sweep.side_effect = sweep_side_effect
        self.mock_extract.return_value = []
        self.mock_flatten.return_value = []
        self.mock_prune_empty.return_value = []
        self.mock_prune_non_music.return_value = []
        self.mock_standardize_lossless.return_value = standardize_result
        self.mock_find_missing_art_os.return_value = missing_art_result

        # Call target function with dry_run=True
        mock_valid_extensions = {'.mp3', '.wav'}
        mock_prefix_hints = {'prefix'}
        with self.assertLogs(level='INFO') as log_context:
            result = music.process(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, mock_valid_extensions, mock_prefix_hints, dry_run=True)

        ## Assert expectations

        ## Check sweep calls have correct parameters
        self.assertEqual(self.mock_sweep.call_count, 2)

        # First sweep: should use copy_instead_of_move=True and dry_run=False
        first_sweep_call = self.mock_sweep.call_args_list[0]
        self.assertEqual(first_sweep_call.kwargs.get('dry_run'), False)
        self.assertEqual(first_sweep_call.kwargs.get('copy_instead_of_move'), True)

        # Second sweep: should use dry_run=True (and copy_instead_of_move defaults to False)
        second_sweep_call = self.mock_sweep.call_args_list[1]
        self.assertEqual(second_sweep_call.kwargs.get('dry_run'), True)

        ## Temp directory operations should execute normally (dry_run=False)
        # Check extract call
        self.mock_extract.assert_called_once()
        self.assertEqual(self.mock_extract.call_args.kwargs.get('dry_run'), False)

        # Check flatten_hierarchy call
        self.mock_flatten.assert_called_once()
        self.assertEqual(self.mock_flatten.call_args.kwargs.get('dry_run'), False)

        # Check standardize_lossless call
        self.mock_standardize_lossless.assert_called_once()
        self.assertEqual(self.mock_standardize_lossless.call_args.kwargs.get('dry_run'), False)

        # Check prune_non_music call
        self.mock_prune_non_music.assert_called_once()
        self.assertEqual(self.mock_prune_non_music.call_args.kwargs.get('dry_run'), False)

        # Check prune_non_user_dirs call
        self.mock_prune_empty.assert_called_once()
        self.assertEqual(self.mock_prune_empty.call_args.kwargs.get('dry_run'), False)

        ## write_paths NOT called in dry-run mode
        self.mock_write_paths.assert_not_called()

        ## Verify dry-run log for write_paths
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        write_paths_logs = [log for log in dry_run_logs if 'write paths' in log]
        self.assertEqual(len(write_paths_logs), 1)
        self.assertIn(constants.MISSING_ART_PATH, write_paths_logs[0])

        ## Return value contains expected data
        self.assertIsInstance(result, music.ProcessResult)

        # Use assertListEqual for list fields
        expected_processed_files = [
            ('/source/track1.mp3', '/output/track1.mp3'),
            ('/source/track2.wav', '/output/track2.aiff')
        ]
        self.assertListEqual(result.processed_files, expected_processed_files)
        self.assertListEqual(result.missing_art_paths, missing_art_result)

        # Use assertEqual for scalar fields
        self.assertEqual(result.archives_extracted, 0)
        self.assertEqual(result.files_encoded, 1)

class TestProcessCLI(unittest.TestCase):
    @patch('djmgmt.music.process')
    def test_success(self, mock_process: MagicMock) -> None:
        '''Tests that the process function is called with the expected arguments.'''
        # Call target function
        mock_valid_extensions = {'a'}
        mock_prefix_hints = {'b'}
        args = Namespace(input=MOCK_INPUT_DIR, output=MOCK_OUTPUT_DIR)
        music.process_cli(args, mock_valid_extensions, mock_prefix_hints) # type: ignore
        
        # Assert expectations
        mock_process.assert_called_once_with(MOCK_INPUT_DIR,
                                             MOCK_OUTPUT_DIR,
                                             mock_valid_extensions,
                                             mock_prefix_hints)

class TestUpdateLibrary(unittest.TestCase):
    # Test constants for update_library paths
    MOCK_COLLECTION_EXPORT_DIR = '/mock/collection/export'
    MOCK_PROCESSED_COLLECTION = '/mock/processed-collection.xml'
    MOCK_MERGED_COLLECTION = '/mock/merged-collection.xml'
    MOCK_LIBRARY = '/mock/library'
    MOCK_CLIENT_MIRROR = '/mock/client/mirror'
    MOCK_EXTENSIONS = {'.mock_ext'}
    MOCK_HINTS = {'mock_hint'}

    def setUp(self) -> None:
        self.mock_process             = patch('djmgmt.music.process').start()
        self.mock_find_latest_file    = patch('djmgmt.common.find_latest_file').start()
        self.mock_record_collection   = patch('djmgmt.library.record_collection').start()
        self.mock_merge_collections   = patch('djmgmt.library.merge_collections').start()
        self.mock_write_root          = patch('djmgmt.library.write_root').start()
        self.mock_compare_tags        = patch('djmgmt.tags_info.compare_tags').start()
        self.mock_create_sync_mappings = patch('djmgmt.sync.create_sync_mappings').start()
        self.mock_filter_mappings     = patch('djmgmt.library.filter_path_mappings').start()
        self.mock_run_music           = patch('djmgmt.sync.run_music').start()
        self.addCleanup(patch.stopall)

        # Shared default return values
        self.mock_process_result = ProcessResult(
            processed_files=[('/in', '/out')], missing_art_paths=['missing_art'],
            archives_extracted=0, files_encoded=0)
        self.mock_mappings_changed  = [self.create_mock_file_mapping(0), self.create_mock_file_mapping(1)]
        self.mock_mappings_created  = [self.create_mock_file_mapping(2)]
        self.mock_mappings_filtered = [self.create_mock_file_mapping(0)]
        self.mock_sync_result = SyncResult(
            mappings=[], batches=[SyncBatchResult(date_context='', files_processed=3, success=True)])

        self.mock_process.return_value               = self.mock_process_result
        self.mock_compare_tags.return_value          = self.mock_mappings_changed.copy()
        self.mock_create_sync_mappings.return_value  = self.mock_mappings_created.copy()
        self.mock_filter_mappings.return_value       = self.mock_mappings_filtered.copy()
        self.mock_run_music.return_value             = self.mock_sync_result

    def test_success(self) -> None:
        '''Tests that dependent functions are called with expected parameters.'''
        mock_record_result = RecordResult(collection_root=ET.Element('collection'), tracks_added=2, tracks_updated=1)
        self.mock_record_collection.return_value = mock_record_result

        actual = music.update_library(MOCK_INPUT_DIR,
                                      self.MOCK_LIBRARY,
                                      self.MOCK_CLIENT_MIRROR,
                                      self.MOCK_COLLECTION_EXPORT_DIR,
                                      self.MOCK_PROCESSED_COLLECTION,
                                      self.MOCK_MERGED_COLLECTION,
                                      self.MOCK_EXTENSIONS,
                                      self.MOCK_HINTS)

        # Assert expectations
        ## Call parameters: process
        self.mock_process.assert_called_once_with(MOCK_INPUT_DIR, self.MOCK_LIBRARY, self.MOCK_EXTENSIONS, self.MOCK_HINTS, dry_run=False)

        # Call parameters: find_latest_file
        self.mock_find_latest_file.assert_called_once_with(self.MOCK_COLLECTION_EXPORT_DIR)

        # Call parameters: merge_collections
        self.mock_merge_collections.assert_called_once_with(self.mock_find_latest_file.return_value, self.MOCK_PROCESSED_COLLECTION)

        # Call parameters: write_root
        self.mock_write_root.assert_called_once_with(self.mock_merge_collections.return_value, self.MOCK_MERGED_COLLECTION)

        ## Call parameters: record_collection
        self.mock_record_collection.assert_called_once_with(self.MOCK_LIBRARY, self.MOCK_MERGED_COLLECTION, self.MOCK_PROCESSED_COLLECTION, dry_run=False)

        ## Call parameters: compare_tags
        self.mock_compare_tags.assert_called_once_with(self.MOCK_LIBRARY, self.MOCK_CLIENT_MIRROR)

        ## Call parameters: create_sync_mappings
        self.mock_create_sync_mappings.assert_called_once_with(mock_record_result.collection_root, self.MOCK_CLIENT_MIRROR)

        ## Call: filter_path_mappings
        self.mock_filter_mappings.assert_called_once_with(self.mock_mappings_changed, mock_record_result.collection_root, constants.XPATH_PRUNED)

        ## Call parameters: run_sync_mappings
        expected_mappings = self.mock_mappings_created + self.mock_mappings_filtered
        self.mock_run_music.assert_called_once_with(expected_mappings, full_scan=True, dry_run=False)

        ## Result
        self.assertEqual(actual.process_result, self.mock_process_result)
        self.assertEqual(actual.record_result, mock_record_result)
        self.assertEqual(actual.sync_result, self.mock_sync_result)
        self.assertListEqual(actual.changed_mappings, self.mock_mappings_filtered)

    def test_error_sync(self) -> None:
        '''Test that if sync fails, the expected functions are still called and the exception is seen.'''
        mock_error = 'Mock error'
        self.mock_run_music.side_effect = Exception(mock_error)

        with self.assertRaisesRegex(Exception, mock_error):
            music.update_library(MOCK_INPUT_DIR,
                                 self.MOCK_LIBRARY,
                                 self.MOCK_CLIENT_MIRROR,
                                 self.MOCK_COLLECTION_EXPORT_DIR,
                                 self.MOCK_PROCESSED_COLLECTION,
                                 self.MOCK_MERGED_COLLECTION,
                                 self.MOCK_EXTENSIONS,
                                 self.MOCK_HINTS)

        # Functions should be called before exception
        self.mock_process.assert_called_once()
        self.mock_record_collection.assert_called_once()
        self.mock_create_sync_mappings.assert_called_once()
        self.mock_compare_tags.assert_called_once()
        self.mock_filter_mappings.assert_called_once()
        self.mock_run_music.assert_called_once()

    def test_dry_run(self) -> None:
        '''Tests that dependent functions are called with expected parameters.'''
        mock_record_result = RecordResult(collection_root=ET.Element('collection'), tracks_added=0, tracks_updated=0)
        self.mock_record_collection.return_value = mock_record_result

        actual = music.update_library(MOCK_INPUT_DIR,
                                      self.MOCK_LIBRARY,
                                      self.MOCK_CLIENT_MIRROR,
                                      self.MOCK_COLLECTION_EXPORT_DIR,
                                      self.MOCK_PROCESSED_COLLECTION,
                                      self.MOCK_MERGED_COLLECTION,
                                      self.MOCK_EXTENSIONS,
                                      self.MOCK_HINTS,
                                      dry_run=True)

        # Assert expectations
        ## Call parameters: process
        self.mock_process.assert_called_once_with(MOCK_INPUT_DIR, self.MOCK_LIBRARY, self.MOCK_EXTENSIONS, self.MOCK_HINTS, dry_run=True)

        ## Call parameters: find_latest_file
        self.mock_find_latest_file.assert_called_once_with(self.MOCK_COLLECTION_EXPORT_DIR)

        ## Call parameters: merge_collections
        self.mock_merge_collections.assert_called_once_with(self.mock_find_latest_file.return_value, self.MOCK_PROCESSED_COLLECTION)

        ## Call parameters: write_root
        self.mock_write_root.assert_called_once_with(self.mock_merge_collections.return_value, self.MOCK_MERGED_COLLECTION)

        ## Call parameters: record_collection
        self.mock_record_collection.assert_called_once_with(self.MOCK_LIBRARY, self.MOCK_MERGED_COLLECTION, self.MOCK_PROCESSED_COLLECTION, dry_run=True)

        ## Call parameters: compare_tags
        self.mock_compare_tags.assert_called_once_with(self.MOCK_LIBRARY, self.MOCK_CLIENT_MIRROR)

        ## Call parameters: create_sync_mappings
        self.mock_create_sync_mappings.assert_called_once_with(mock_record_result.collection_root, self.MOCK_CLIENT_MIRROR)

        ## Call: filter_path_mappings
        self.mock_filter_mappings.assert_called_once_with(self.mock_mappings_changed, mock_record_result.collection_root, constants.XPATH_PRUNED)

        ## Call parameters: run_sync_mappings
        expected_mappings = self.mock_mappings_created + self.mock_mappings_filtered
        self.mock_run_music.assert_called_once_with(expected_mappings, full_scan=True, dry_run=True)

        ## Result
        self.assertEqual(actual.process_result, self.mock_process_result)
        self.assertEqual(actual.record_result, mock_record_result)
        self.assertEqual(actual.sync_result, self.mock_sync_result)
        self.assertListEqual(actual.changed_mappings, self.mock_mappings_filtered)

    def create_mock_file_mapping(self, index: int) -> FileMapping:
        create_mock_path: Callable[[str, int], str] = lambda p, n: os.path.join(p, f"mock_file_{n}")
        return (create_mock_path(MOCK_INPUT_DIR, index), create_mock_path(MOCK_OUTPUT_DIR, index))

class TestParseArgs(unittest.TestCase):
    '''Tests for music.parse_args and argument validation.'''

    def setUp(self) -> None:
        self.mock_exit   = patch('sys.exit').start()
        self.mock_exists = patch('os.path.exists').start()
        self.addCleanup(patch.stopall)
        self.mock_exists.return_value = True

    def _base_update_library_argv(self, **overrides: str | None) -> list[str]:
        '''Returns a full update_library argv; pass flag=None to omit it.'''
        args: dict[str, str | None] = {
            '--client-mirror-path': '/mirror',
            '--collection-export-dir-path': '/exports',
            '--processed-collection-path': '/processed.xml',
            '--merged-collection-path': '/merged.xml',
            **overrides,
        }
        argv: list[str] = ['update_library', '--input', '/in', '--output', '/out']
        for flag, val in args.items():
            if val is not None:
                argv += [flag, val]
        return argv

    def test_valid_single_arg_function(self) -> None:
        '''Tests that single-arg functions (flatten, prune, etc.) only need --input.'''
        argv = ['flatten', '--input', '/mock/input']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'flatten')
        self.assertEqual(args.input, '/mock/input')
        self.assertEqual(args.output, '/mock/input')  # output defaults to input for single-arg functions

    def test_valid_multi_arg_function(self) -> None:
        '''Tests that multi-arg functions require --input and --output.'''
        argv = ['sweep', '--input', '/src', '--output', '/dst']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'sweep')
        self.assertEqual(args.input, '/src')
        self.assertEqual(args.output, '/dst')

    def test_valid_process(self) -> None:
        '''Tests that process function works with required args.'''
        argv = ['process', '--input', '/in', '--output', '/out']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'process')
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/out')

    def test_valid_update_library(self) -> None:
        '''Tests that update_library works with all required arguments.'''
        argv = ['update_library', '--input', '/in', '--output', '/lib',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'update_library')
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/lib')
        self.assertEqual(args.client_mirror_path, '/mirror')
        self.assertEqual(args.collection_export_dir_path, '/exports')
        self.assertEqual(args.processed_collection_path, '/processed.xml')
        self.assertEqual(args.merged_collection_path, '/merged.xml')

    def test_missing_input(self) -> None:
        '''Tests that missing --input causes error.'''
        argv = ['sweep', '--output', '/out']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.mock_exit.assert_called_with(2)

    def test_multi_arg_missing_output(self) -> None:
        '''Tests that multi-arg functions require --output.'''
        argv = ['sweep', '--input', '/in']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.mock_exit.assert_called_with(2)

    def test_update_library_missing_client_mirror(self) -> None:
        '''Tests that update_library requires --client-mirror-path.'''
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG,
                         self._base_update_library_argv(**{'--client-mirror-path': None}))
        self.mock_exit.assert_called_with(2)

    def test_update_library_missing_collection_export_dir(self) -> None:
        '''Tests that update_library requires --collection-export-dir-path.'''
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG,
                         self._base_update_library_argv(**{'--collection-export-dir-path': None}))
        self.mock_exit.assert_called_with(2)

    def test_update_library_missing_processed_collection(self) -> None:
        '''Tests that update_library requires --processed-collection-path.'''
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG,
                         self._base_update_library_argv(**{'--processed-collection-path': None}))
        self.mock_exit.assert_called_with(2)

    def test_update_library_missing_merged_collection(self) -> None:
        '''Tests that update_library requires --merged-collection-path.'''
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG,
                         self._base_update_library_argv(**{'--merged-collection-path': None}))
        self.mock_exit.assert_called_with(2)

    # TODO: refactor tests to use with pattern to assert exceptions rather than checking exit code
    def test_update_library_invalid_client_mirror_path(self) -> None:
        '''Tests that update_library validates client_mirror_path exists.'''
        self.mock_exists.side_effect = lambda p: p != '/nonexistent'
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/nonexistent',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.mock_exit.assert_called_with(2)

    def test_update_library_invalid_collection_export_dir_path(self) -> None:
        '''Tests that update_library validates collection_export_dir_path exists.'''
        self.mock_exists.side_effect = lambda p: p != '/nonexistent'
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/nonexistent',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.mock_exit.assert_called_with(2)

    def test_invalid_function(self) -> None:
        '''Tests that invalid function name causes error.'''
        argv = ['invalid', '--input', '/in', '--output', '/out']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.mock_exit.assert_called_with(2)

    def test_dry_run_default(self) -> None:
        '''Tests that dry_run defaults to False when not provided.'''
        argv = ['process', '--input', '/in', '--output', '/out']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertFalse(args.dry_run)

    def test_dry_run_enabled(self) -> None:
        '''Tests that --dry-run flag sets dry_run to True.'''
        argv = ['process', '--input', '/in', '--output', '/out', '--dry-run']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertTrue(args.dry_run)

    def test_dry_run_short_flag(self) -> None:
        '''Tests that -d short flag sets dry_run to True.'''
        argv = ['process', '--input', '/in', '--output', '/out', '-d']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertTrue(args.dry_run)

    def test_dry_run_with_update_library(self) -> None:
        '''Tests that dry_run works with update_library and all its required arguments.'''
        argv = ['update_library', '--input', '/in', '--output', '/lib',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml',
                '--dry-run']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'update_library')
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/lib')
        self.assertEqual(args.client_mirror_path, '/mirror')
        self.assertEqual(args.collection_export_dir_path, '/exports')
        self.assertEqual(args.processed_collection_path, '/processed.xml')
        self.assertEqual(args.merged_collection_path, '/merged.xml')
        self.assertTrue(args.dry_run)

    def test_dry_run_with_single_arg_function(self) -> None:
        '''Tests that dry_run works with single-arg functions.'''
        argv = ['flatten', '--input', '/in', '--dry-run']
        args = music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        self.assertEqual(args.function, 'flatten')
        self.assertEqual(args.input, '/in')
        self.assertEqual(args.output, '/in')  # output defaults to input for single-arg functions
        self.assertTrue(args.dry_run)
