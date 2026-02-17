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

# Constants
MOCK_INPUT_DIR  = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'

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
    @patch('djmgmt.music.sweep')
    @patch('os.remove')
    @patch('djmgmt.encode.encode_lossless')
    @patch('tempfile.TemporaryDirectory')
    def test_success(self,
                     mock_temp_dir: MagicMock,
                     mock_encode: MagicMock,
                     mock_remove: MagicMock,
                     mock_sweep: MagicMock) -> None:
        '''Tests that the encoding function is run and all encoded files are removed.'''
        # Set up mocks
        mock_temp_path = 'mock_temp_path'
        mock_input_file = 'mock_input_file'
        mock_temp_dir.return_value.__enter__.return_value = mock_temp_path
        mock_encode.return_value = [(mock_input_file, 'mock_output_file')]
        
        # Call target function
        mock_extensions = {'a'}
        mock_hints = {'b'}
        actual = music.standardize_lossless(MOCK_INPUT_DIR, mock_extensions, mock_hints)
        
        # Assert expectations
        ## Check calls
        mock_temp_dir.assert_called_once()
        mock_encode.assert_called_once_with(MOCK_INPUT_DIR, mock_temp_path, '.aiff', dry_run=False)
        mock_remove.assert_called_once_with(mock_input_file)
        mock_sweep.assert_called_once_with(mock_temp_path, MOCK_INPUT_DIR, mock_extensions, mock_hints, dry_run=False) 
        
        ## Check output
        self.assertEqual(actual, mock_encode.return_value)
        
    @patch('djmgmt.music.sweep')
    @patch('os.remove')
    @patch('djmgmt.encode.encode_lossless')
    @patch('tempfile.TemporaryDirectory')
    def test_success_dry_run(self,
                             mock_temp_dir: MagicMock,
                             mock_encode: MagicMock,
                             mock_remove: MagicMock,
                             mock_sweep: MagicMock) -> None:
        '''Tests that helper functions are called with dry run, and no files are removed.'''
        # Set up mocks
        mock_temp_path = 'mock_temp_path'
        mock_input_file = 'mock_input_file'
        mock_temp_dir.return_value.__enter__.return_value = mock_temp_path
        mock_encode.return_value = [(mock_input_file, 'mock_output_file')]
        
        # Call target function
        mock_extensions = {'a'}
        mock_hints = {'b'}
        with self.assertLogs(level='INFO') as log_context:
            actual = music.standardize_lossless(MOCK_INPUT_DIR, mock_extensions, mock_hints, dry_run=True)
        
        # Assert expectations
        ## Check calls
        mock_temp_dir.assert_called_once()
        mock_encode.assert_called_once_with(MOCK_INPUT_DIR, mock_temp_path, '.aiff', dry_run=True)
        mock_remove.assert_not_called()
        mock_sweep.assert_called_once_with(mock_temp_path, MOCK_INPUT_DIR, mock_extensions, mock_hints, dry_run=True)
        
        ## Check output
        self.assertEqual(actual, mock_encode.return_value)
        
        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove', dry_run_logs[0])

class TestSweep(unittest.TestCase):
    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_sweep_music_files(self,
                               mock_collect_paths: MagicMock,
                               mock_path_exists: MagicMock,
                               mock_is_prefix_match: MagicMock,
                               mock_zipfile: MagicMock,
                               mock_move: MagicMock) -> None:
        '''Test that loose music files are swept.'''
        # Set up mocks
        mock_filenames = [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        mock_paths = [f"{MOCK_INPUT_DIR}/{p}" for p in mock_filenames]
        mock_collect_paths.return_value = mock_paths
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = False
        
        # Call target function
        actual = music.sweep(MOCK_INPUT_DIR,
                             MOCK_OUTPUT_DIR,
                             constants.EXTENSIONS,
                             music.PREFIX_HINTS)
        
        # Assert expectations
        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}",
            f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.assertEqual(mock_path_exists.call_count, len(mock_filenames))
        mock_is_prefix_match.assert_not_called()
        mock_zipfile.assert_not_called()
        mock_move.assert_has_calls([
            call(input_path, output_path)
            for input_path, output_path in expected
        ])
        
        ## Check output
        self.assertEqual(actual, expected)
    
    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_no_sweep_non_music_files(self,
                                  mock_collect_paths: MagicMock,
                                  mock_path_exists: MagicMock,
                                  mock_is_prefix_match: MagicMock,
                                  mock_zipfile: MagicMock,
                                  mock_move: MagicMock) -> None:
        '''Test that loose, non-music files are not swept.'''
        mock_filenames = [
            'track_0.foo',
            'img_0.jpg'  ,
            'img_1.jpeg' ,
            'img_2.png'  ,
        ]
        # Set up mocks
        mock_collect_paths.return_value = mock_filenames
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = False
        
        # Call target function
        actual = music.sweep(MOCK_INPUT_DIR,
                             MOCK_OUTPUT_DIR,
                             constants.EXTENSIONS,
                             music.PREFIX_HINTS)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.assertEqual(mock_path_exists.call_count, len(mock_filenames))
        mock_is_prefix_match.assert_not_called()
        mock_zipfile.assert_not_called()
        mock_move.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])
    
    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_sweep_prefix_archive(self,
                                  mock_collect_paths: MagicMock,
                                  mock_path_exists: MagicMock,
                                  mock_is_prefix_match: MagicMock,
                                  mock_zipfile: MagicMock,
                                  mock_move: MagicMock) -> None:
        '''Test that a prefix zip archive is swept to the output directory.'''
        # Set up mocks
        mock_filename = 'mock_valid_prefix.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = True
        
        # Call target function
        actual = music.sweep(MOCK_INPUT_DIR,
                             MOCK_OUTPUT_DIR,
                             constants.EXTENSIONS,
                             music.PREFIX_HINTS)
        
        # Assert expectations
        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_path_exists.assert_called_once_with(expected_output_path)
        mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        mock_zipfile.assert_not_called()
        mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        
        ## Check output
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])

    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_sweep_music_archive(self,
                                 mock_collect_paths: MagicMock,
                                 mock_path_exists: MagicMock,
                                 mock_is_prefix_match: MagicMock,
                                 mock_zipfile: MagicMock,
                                 mock_move: MagicMock) -> None:
        '''Test that a zip containing only music files is swept to the output directory.'''
        # Set up mocks
        mock_filename = 'mock_music_archive.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = False
        
        # Mock archive content
        mock_archive = MagicMock()
        mock_archive.namelist.return_value = [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        mock_zipfile.return_value.__enter__.return_value = mock_archive

        # Call target function
        actual = music.sweep(MOCK_INPUT_DIR,
                             MOCK_OUTPUT_DIR,
                             constants.EXTENSIONS,
                             music.PREFIX_HINTS)
        
        # Assert expectations
        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_path_exists.assert_called_once_with(expected_output_path)
        mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        mock_zipfile.assert_called_once()
        mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        
        ## Check output
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])
    
    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_sweep_album_archive(self,
                                 mock_collect_paths: MagicMock,
                                 mock_path_exists: MagicMock,
                                 mock_is_prefix_match: MagicMock,
                                 mock_zipfile: MagicMock,
                                 mock_move: MagicMock) -> None:
        '''Test that a zip containing music files and a cover photo is swept to the output directory.'''
        # Set up mocks
        mock_filename = 'mock_album_archive.zip'
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = False
        
        # Mock archive content
        mock_archive = MagicMock()
        mock_archive.namelist.return_value =  [f"mock_file{ext}" for ext in constants.EXTENSIONS]
        mock_archive.namelist.return_value += ['mock_cover.jpg']
        mock_zipfile.return_value.__enter__.return_value = mock_archive

        # Call target function
        actual = music.sweep(MOCK_INPUT_DIR,
                             MOCK_OUTPUT_DIR,
                             constants.EXTENSIONS,
                             music.PREFIX_HINTS)
        
        # Assert expectations
        expected_output_path = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_path_exists.assert_called_once_with(expected_output_path)
        mock_is_prefix_match.assert_called_once_with(mock_filename, music.PREFIX_HINTS)
        mock_zipfile.assert_called_once()
        mock_move.assert_called_once_with(mock_input_path, expected_output_path)
        
        ## Check output
        self.assertEqual(actual, [(mock_input_path, expected_output_path)])

    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('djmgmt.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_dry_run(self,
                     mock_collect_paths: MagicMock,
                     mock_path_exists: MagicMock,
                     mock_is_prefix_match: MagicMock,
                     mock_zipfile: MagicMock,
                     mock_move: MagicMock) -> None:
        '''Test that dry_run=True skips file moves and logs operations.'''
        # Set up mocks
        mock_filenames = ['track1.mp3', 'track2.aiff']
        mock_paths = [f"{MOCK_INPUT_DIR}/{p}" for p in mock_filenames]
        mock_collect_paths.return_value = mock_paths
        mock_path_exists.return_value = False
        mock_is_prefix_match.return_value = False

        # Call target function with dry_run=True
        with self.assertLogs(level='INFO') as log_context:
            actual = music.sweep(MOCK_INPUT_DIR,
                                MOCK_OUTPUT_DIR,
                                constants.EXTENSIONS,
                                music.PREFIX_HINTS,
                                dry_run=True)

        # Assert expectations
        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[0]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[0]}"),
            (f"{MOCK_INPUT_DIR}/{mock_filenames[1]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[1]}")
        ]

        # Verify shutil.move was NOT called in dry-run mode
        mock_move.assert_not_called()

        # Verify return value still contains expected mappings
        self.assertListEqual(actual, expected)

        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 2)
        self.assertIn('move', dry_run_logs[0])
        self.assertIn('move', dry_run_logs[1])

class TestFlattenHierarchy(unittest.TestCase):
    @patch('shutil.move')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success_output_path_not_exists(self,
                                            mock_collect_paths: MagicMock,
                                            mock_path_exists: MagicMock,
                                            mock_move: MagicMock) -> None:
        '''Tests that all loose files at the input root are flattened to output.'''
        # Set up mocks
        mock_filenames = [
            f"file_{i}.foo"
            for i in range(3)
        ]
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]
        mock_path_exists.return_value = False

        # Call target function        
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}",
             f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_move.assert_has_calls([
            call(input_path, output_path)
            for input_path, output_path in expected
        ])
        
        ## Check output
        self.assertEqual(actual, expected)
        
    @patch('shutil.move')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success_output_path_exists(self,
                                        mock_collect_paths: MagicMock,
                                        mock_path_exists: MagicMock,
                                        mock_move: MagicMock) -> None:
        '''Tests that a file is flattened only if its output path doesn't exist.'''
        # Set up mocks
        mock_filenames = [
            f"file_{i}.foo"
            for i in range(3)
        ]
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]
        mock_path_exists.side_effect = [False, True, True]
        
        # Call target function        
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        expected_input, expected_output = f"{MOCK_INPUT_DIR}/{mock_filenames[0]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[0]}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_move.assert_called_once_with(expected_input, expected_output)
        
        ## Check output
        self.assertEqual(actual, [(expected_input, expected_output)])
        
    @patch('shutil.move')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success_dry_run(self,
                             mock_collect_paths: MagicMock,
                             mock_path_exists: MagicMock,
                             mock_move: MagicMock) -> None:
        '''Tests that no files are moved, but the dry run results are still returned.'''
        # Set up mocks
        mock_filenames = [
            f"file_{i}.foo"
            for i in range(2)
        ]
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}/{f}" for f in mock_filenames]
        mock_path_exists.return_value = False

        # Call target function
        with self.assertLogs(level='INFO') as log_context:
            actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, dry_run=True)
        
        # Assert expectations
        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}",
             f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_move.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, expected)
        
        # Verify dry-run logs
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
    @patch('djmgmt.music.extract_all_normalized_encodings')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success(self,
                     mock_collect_paths: MagicMock,
                     mock_path_exists: MagicMock,
                     mock_isdir: MagicMock,
                     mock_extract_all: MagicMock) -> None:
        '''Tests that all zip archives are extracted.'''
        # Set up mocks
        mock_filename = 'mock_archive.zip'
        mock_file_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_file_path]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        mock_extract_all.return_value = (mock_filename, ['mock_file_0', 'mock_file_1'])
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_extract_all.assert_called_once_with(mock_file_path, MOCK_OUTPUT_DIR, dry_run=False)
        
        # Check output
        self.assertEqual(actual, [mock_extract_all.return_value])
        
    @patch('djmgmt.music.extract_all_normalized_encodings')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success_no_zip_present(self,
                                    mock_collect_paths: MagicMock,
                                    mock_path_exists: MagicMock,
                                    mock_isdir: MagicMock,
                                    mock_extract_all: MagicMock) -> None:
        '''Tests that nothing is extracted if there are no zip archives present in the input directory.'''
        # Set up mocks
        mock_file_path = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        mock_collect_paths.return_value = [mock_file_path]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_extract_all.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])
        
    @patch('djmgmt.music.extract_all_normalized_encodings')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('djmgmt.common.collect_paths')
    def test_success_output_exists(self,
                                   mock_collect_paths: MagicMock,
                                   mock_path_exists: MagicMock,
                                   mock_isdir: MagicMock,
                                   mock_extract_all: MagicMock) -> None:
        '''Tests that nothing is extracted if the output directory exists.'''
        # Set up mocks
        mock_filename = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        mock_collect_paths.return_value = [mock_filename]
        mock_path_exists.return_value = True
        mock_isdir.return_value = True
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_extract_all.assert_not_called()
        
        ## Check output
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
    @patch('shutil.rmtree')
    @patch('djmgmt.music.has_no_user_files')
    @patch('djmgmt.music.get_dirs')
    def test_success_remove_empty_dir(self,
                                      mock_get_dirs: MagicMock,
                                      mock_is_empty_dir: MagicMock,
                                      mock_rmtree: MagicMock) -> None:
        '''Test that prune removes an empty directory.'''
        # Setup mocks
        mock_get_dirs.return_value = ['mock_empty_dir']
        
        # Call target function
        actual = music.prune_non_user_dirs('/mock/source/')

        ## Assert expectations
        ## Check calls
        expected_path = '/mock/source/mock_empty_dir'
        mock_get_dirs.assert_called()
        mock_is_empty_dir.assert_called()
        mock_rmtree.assert_called_once_with(expected_path)
        
        ## Check output
        self.assertListEqual(actual, [expected_path])
        
    @patch('shutil.rmtree')
    @patch('djmgmt.music.has_no_user_files')
    @patch('djmgmt.music.get_dirs')
    def test_success_skip_non_empty_dir(self,
                                        mock_get_dirs: MagicMock,
                                        mock_is_empty_dir: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Test that prune does not remove a non-empty directory.'''
        # Setup mocks
        mock_get_dirs.side_effect = [['mock_non_empty_dir'], []]
        mock_is_empty_dir.return_value = False
        
        # Call target function
        actual = music.prune_non_user_dirs('/mock/source/')

        ## Assert expectations
        ## Check calls
        mock_get_dirs.assert_called()
        mock_is_empty_dir.assert_called()
        mock_rmtree.assert_not_called()
        
        ## Check output
        self.assertListEqual(actual, [])
        
    @patch('shutil.rmtree')
    @patch('djmgmt.music.has_no_user_files')
    @patch('djmgmt.music.get_dirs')
    def test_dry_run(self,
                     mock_get_dirs: MagicMock,
                     mock_is_empty_dir: MagicMock,
                     mock_rmtree: MagicMock) -> None:
        '''Test that dry_run=True skips directory removal and logs operations.'''
        # Setup mocks
        mock_get_dirs.return_value = ['mock_empty_dir']
        mock_is_empty_dir.return_value = True

        # Call target function with dry_run=True
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_user_dirs('/mock/source/', dry_run=True)

        ## Assert expectations
        expected_path = '/mock/source/mock_empty_dir'

        ## Directory identified but NOT removed in dry-run mode
        mock_get_dirs.assert_called()
        mock_is_empty_dir.assert_called()
        mock_rmtree.assert_not_called()

        ## Return value still contains expected paths
        self.assertListEqual(actual, [expected_path])

        ## Verify dry-run logs
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
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_non_music(self,
                                      mock_collect_paths: MagicMock,
                                      mock_os_remove: MagicMock,
                                      mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock_file.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_skip_music(self,
                                mock_collect_paths: MagicMock,
                                mock_os_remove: MagicMock,
                                mock_rmtree: MagicMock) -> None:
        '''Tests that top-level music files are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_skip_music_subdirectory(self,
                                             mock_collect_paths: MagicMock,
                                             mock_os_remove: MagicMock,
                                             mock_rmtree: MagicMock) -> None:
        '''Tests that nested music files are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_non_music_subdirectory(self,
                                                   mock_collect_paths: MagicMock,
                                                   mock_os_remove: MagicMock,
                                                   mock_rmtree: MagicMock) -> None:
        '''Tests that nested non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock/dir/0/mock_file.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock/dir/0/mock_file.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_hidden_file(self,
                                        mock_collect_paths: MagicMock,
                                        mock_os_remove: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Tests that hidden files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_zip_archive(self,
                                        mock_collect_paths: MagicMock,
                                        mock_os_remove: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Tests that zip archives are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock.zip']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock.zip')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('os.path.isdir')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_app(self,
                                mock_collect_paths: MagicMock,
                                mock_isdir: MagicMock,
                                mock_os_remove: MagicMock,
                                mock_rmtree: MagicMock) -> None:
        '''Tests that .app archives are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock.app']
        mock_isdir.return_value = True
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_called_once_with('/mock/source/mock.app')
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_skip_music_hidden_dir(self,
                                           mock_collect_paths: MagicMock,
                                           mock_os_remove: MagicMock,
                                           mock_rmtree: MagicMock) -> None:
        '''Tests that music files in a hidden directory are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_remove_non_music_hidden_dir(self,
                                                 mock_collect_paths: MagicMock,
                                                 mock_os_remove: MagicMock,
                                                 mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files in a hidden directory are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden_dir/mock.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('djmgmt.common.collect_paths')
    def test_success_dry_run_file(self,
                                  mock_collect_paths: MagicMock,
                                  mock_os_remove: MagicMock,
                                  mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        
        # Call target function and assert expectations
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, dry_run=True)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
        
        # Verify dry-run logs
        dry_run_logs = [log for log in log_context.output if '[DRY-RUN]' in log]
        self.assertEqual(len(dry_run_logs), 1)
        self.assertIn('remove', dry_run_logs[0])

    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('os.path.isdir')
    @patch('djmgmt.common.collect_paths')
    def test_success_dry_run_directory(self,
                                       mock_collect_paths: MagicMock,
                                       mock_isdir: MagicMock,
                                       mock_os_remove: MagicMock,
                                       mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        mock_isdir.return_value = True
        
        # Call target function and assert expectations
        with self.assertLogs(level='INFO') as log_context:
            actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, dry_run=True)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_isdir.assert_called_once()
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
        
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
    @patch('djmgmt.common.write_paths')
    @patch('djmgmt.encode.find_missing_art_os')
    @patch('djmgmt.music.standardize_lossless')
    @patch('djmgmt.music.prune_non_music')
    @patch('djmgmt.music.prune_non_user_dirs')
    @patch('djmgmt.music.flatten_hierarchy')
    @patch('djmgmt.music.extract')
    @patch('djmgmt.music.sweep')
    def test_success(self,
                     mock_sweep: MagicMock,
                     mock_extract: MagicMock,
                     mock_flatten: MagicMock,
                     mock_prune_empty: MagicMock,
                     mock_prune_non_music: MagicMock,
                     mock_standardize_lossless: MagicMock,
                     mock_find_missing_art_os: MagicMock,
                     mock_write_paths: MagicMock) -> None:
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

        mock_sweep.side_effect = sweep_side_effect
        mock_extract.side_effect = lambda *_, **__: (mock_call_container.extract(), extract_result)[1]
        mock_flatten.side_effect = lambda *_, **__: (mock_call_container.flatten(), [])[1]
        mock_prune_empty.side_effect = lambda *_, **__: (mock_call_container.prune_non_user_dirs(), [])[1]
        mock_prune_non_music.side_effect = lambda *_, **__: (mock_call_container.prune_non_music(), [])[1]
        mock_standardize_lossless.side_effect = lambda *_, **__: (mock_call_container.standardize_lossless(), standardize_result)[1]
        mock_find_missing_art_os.side_effect = lambda *_, **__: (mock_call_container.find_missing_art_os(), missing_art_result)[1]
        mock_write_paths.side_effect = lambda *_, **__: (mock_call_container.write_paths(), None)[1]

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
        self.assertEqual(mock_sweep.call_count, 2)
        mock_extract.assert_called_once()
        mock_flatten.assert_called_once()

        # find_missing_art_os should be called with processing_dir (temp directory), not output
        # The exact temp dir path varies, so we just verify it's called once with some directory
        mock_find_missing_art_os.assert_called_once()

        self.assertEqual(missing_art_result, mock_write_paths.call_args.args[0])

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
    
    @patch('djmgmt.common.write_paths')
    @patch('djmgmt.encode.find_missing_art_os')
    @patch('djmgmt.music.standardize_lossless')
    @patch('djmgmt.music.prune_non_music')
    @patch('djmgmt.music.prune_non_user_dirs')
    @patch('djmgmt.music.flatten_hierarchy')
    @patch('djmgmt.music.extract')
    @patch('djmgmt.music.sweep')
    def test_dry_run(self,
                     mock_sweep: MagicMock,
                     mock_extract: MagicMock,
                     mock_flatten: MagicMock,
                     mock_prune_empty: MagicMock,
                     mock_prune_non_music: MagicMock,
                     mock_standardize_lossless: MagicMock,
                     mock_find_missing_art_os: MagicMock,
                     mock_write_paths: MagicMock) -> None:
        '''Test that dry_run=True uses copy mode for initial sweep, skips final sweep operations, and preserves source files.'''
        # Configure sweep to return realistic data for both calls
        def sweep_side_effect(*args: object, **kwargs: object) -> list[FileMapping]:
            # Return different data for first and second calls
            if mock_sweep.call_count == 1:
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

        mock_sweep.side_effect = sweep_side_effect
        mock_extract.return_value = []
        mock_flatten.return_value = []
        mock_prune_empty.return_value = []
        mock_prune_non_music.return_value = []
        mock_standardize_lossless.return_value = standardize_result
        mock_find_missing_art_os.return_value = missing_art_result

        # Call target function with dry_run=True
        mock_valid_extensions = {'.mp3', '.wav'}
        mock_prefix_hints = {'prefix'}
        with self.assertLogs(level='INFO') as log_context:
            result = music.process(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, mock_valid_extensions, mock_prefix_hints, dry_run=True)

        ## Assert expectations

        ## Check sweep calls have correct parameters
        self.assertEqual(mock_sweep.call_count, 2)

        # First sweep: should use copy_instead_of_move=True and dry_run=False
        first_sweep_call = mock_sweep.call_args_list[0]
        self.assertEqual(first_sweep_call.kwargs.get('dry_run'), False)
        self.assertEqual(first_sweep_call.kwargs.get('copy_instead_of_move'), True)

        # Second sweep: should use dry_run=True (and copy_instead_of_move defaults to False)
        second_sweep_call = mock_sweep.call_args_list[1]
        self.assertEqual(second_sweep_call.kwargs.get('dry_run'), True)

        ## Temp directory operations should execute normally (dry_run=False)
        # Check extract call
        mock_extract.assert_called_once()
        self.assertEqual(mock_extract.call_args.kwargs.get('dry_run'), False)

        # Check flatten_hierarchy call
        mock_flatten.assert_called_once()
        self.assertEqual(mock_flatten.call_args.kwargs.get('dry_run'), False)

        # Check standardize_lossless call
        mock_standardize_lossless.assert_called_once()
        self.assertEqual(mock_standardize_lossless.call_args.kwargs.get('dry_run'), False)

        # Check prune_non_music call
        mock_prune_non_music.assert_called_once()
        self.assertEqual(mock_prune_non_music.call_args.kwargs.get('dry_run'), False)

        # Check prune_non_user_dirs call
        mock_prune_empty.assert_called_once()
        self.assertEqual(mock_prune_empty.call_args.kwargs.get('dry_run'), False)

        ## write_paths NOT called in dry-run mode
        mock_write_paths.assert_not_called()

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

    @patch('djmgmt.sync.run_music')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.sync.create_sync_mappings')
    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.merge_collections')
    @patch('djmgmt.library.write_root')
    @patch('djmgmt.library.record_collection')
    @patch('djmgmt.common.find_latest_file')
    @patch('djmgmt.music.process')
    def test_success(self,
                     mock_process: MagicMock,
                     mock_find_latest_file: MagicMock,
                     mock_record_collection: MagicMock,
                     mock_write_root: MagicMock,
                     mock_merge_collections: MagicMock,
                     mock_compare_tags: MagicMock,
                     mock_create_sync_mappings: MagicMock,
                     mock_filter_mappings: MagicMock,
                     mock_run_sync_mappings: MagicMock) -> None:
        '''Tests that dependent functions are called with expected parameters.'''
        # Set up mocks
        mock_record_result = RecordResult(collection_root=ET.Element('collection'), tracks_added=2, tracks_updated=1)
        mock_process_result = ProcessResult(processed_files=[('/in', '/out')], missing_art_paths=['missing_art'], archives_extracted=0, files_encoded=0)
        mock_mappings_changed = [self.create_mock_file_mapping(0), self.create_mock_file_mapping(1)]
        mock_mappings_created = [self.create_mock_file_mapping(2)]
        mock_mappings_filtered = [self.create_mock_file_mapping(0)]

        mock_sync_result = SyncResult(mappings=[], batches=[SyncBatchResult(date_context='', files_processed=3, success=True)])

        mock_process.return_value = mock_process_result
        mock_record_collection.return_value = mock_record_result
        mock_run_sync_mappings.return_value = mock_sync_result
        mock_compare_tags.return_value = mock_mappings_changed.copy()
        mock_create_sync_mappings.return_value = mock_mappings_created.copy()
        mock_filter_mappings.return_value = mock_mappings_filtered.copy()

        # Call target function
        mock_library = '/mock/library'
        mock_client_mirror = '/mock/client/mirror'
        mock_extensions = {'.mock_ext'}
        mock_hints = {'mock_hint'}
        actual = music.update_library(MOCK_INPUT_DIR,
                                      mock_library,
                                      mock_client_mirror,
                                      self.MOCK_COLLECTION_EXPORT_DIR,
                                      self.MOCK_PROCESSED_COLLECTION,
                                      self.MOCK_MERGED_COLLECTION,
                                      mock_extensions,
                                      mock_hints)

        # Assert expectations
        ## Call parameters: process
        mock_process.assert_called_once_with(MOCK_INPUT_DIR, mock_library, mock_extensions, mock_hints, dry_run=False)

        # Call parameters: find_latest_file
        mock_find_latest_file.assert_called_once_with(self.MOCK_COLLECTION_EXPORT_DIR)

        # Call parameters: merge_collections
        mock_merge_collections.assert_called_once_with(mock_find_latest_file.return_value, self.MOCK_PROCESSED_COLLECTION)

        # Call parameters: write_root
        mock_write_root.assert_called_once_with(mock_merge_collections.return_value, self.MOCK_MERGED_COLLECTION)

        ## Call parameters: record_collection
        mock_record_collection.assert_called_once_with(mock_library, self.MOCK_MERGED_COLLECTION, self.MOCK_PROCESSED_COLLECTION, dry_run=False)

        ## Call parameters: compare_tags
        mock_compare_tags.assert_called_once_with(mock_library, mock_client_mirror)

        ## Call parameters: create_sync_mappings
        mock_create_sync_mappings.assert_called_once_with(mock_record_result.collection_root, mock_client_mirror)

        ## Call: filter_path_mappings
        mock_filter_mappings.assert_called_once_with(mock_mappings_changed, mock_record_result.collection_root, constants.XPATH_PRUNED)

        ## Call parameters: run_sync_mappings
        expected_mappings = mock_mappings_created + mock_mappings_filtered
        mock_run_sync_mappings.assert_called_once_with(expected_mappings, full_scan=True, dry_run=False)

        ## Result
        self.assertEqual(actual.process_result, mock_process_result)
        self.assertEqual(actual.record_result, mock_record_result)
        self.assertEqual(actual.sync_result, mock_sync_result)
        self.assertListEqual(actual.changed_mappings, mock_mappings_filtered)
        
    @patch('djmgmt.sync.run_music')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.sync.create_sync_mappings')
    @patch('djmgmt.library.write_root')
    @patch('djmgmt.library.merge_collections')
    @patch('djmgmt.library.record_collection')
    @patch('djmgmt.common.find_latest_file')
    @patch('djmgmt.music.process')
    def test_error_sync(self,
                        mock_process: MagicMock,
                        mock_find_latest_file: MagicMock,
                        mock_record_collection: MagicMock,
                        mock_merge_collections: MagicMock,
                        mock_write_root: MagicMock,
                        mock_create_sync_mappings: MagicMock,
                        mock_compare_tags: MagicMock,
                        mock_filter_path_mappings: MagicMock,
                        mock_run_sync_mappings: MagicMock) -> None:
        '''Test that if sync fails, the expected functions are still called and the exception is seen.'''
        # Set up mocks
        mock_error = 'Mock error'
        mock_run_sync_mappings.side_effect = Exception(mock_error)

        # Call target function
        mock_library = '/mock/library'
        mock_client_mirror = '/mock/client/mirror'
        mock_extensions = {'.mock_ext'}
        mock_hints = {'mock_hint'}

        # Assert expectations
        with self.assertRaisesRegex(Exception, mock_error):
            music.update_library(MOCK_INPUT_DIR,
                                 mock_library,
                                 mock_client_mirror,
                                 self.MOCK_COLLECTION_EXPORT_DIR,
                                 self.MOCK_PROCESSED_COLLECTION,
                                 self.MOCK_MERGED_COLLECTION,
                                 mock_extensions,
                                 mock_hints)

        # Functions should be called before exception
        mock_process.assert_called_once()
        mock_record_collection.assert_called_once()
        mock_create_sync_mappings.assert_called_once()
        mock_compare_tags.assert_called_once()
        mock_filter_path_mappings.assert_called_once()
        mock_run_sync_mappings.assert_called_once()
    
    @patch('djmgmt.sync.run_music')
    @patch('djmgmt.library.filter_path_mappings')
    @patch('djmgmt.sync.create_sync_mappings')
    @patch('djmgmt.tags_info.compare_tags')
    @patch('djmgmt.library.write_root')
    @patch('djmgmt.library.merge_collections')
    @patch('djmgmt.library.record_collection')
    @patch('djmgmt.common.find_latest_file')
    @patch('djmgmt.music.process')
    def test_dry_run(self,
                     mock_process: MagicMock,
                     mock_find_latest_file: MagicMock,
                     mock_record_collection: MagicMock,
                     mock_merge_collections: MagicMock,
                     mock_write_root: MagicMock,
                     mock_compare_tags: MagicMock,
                     mock_create_sync_mappings: MagicMock,
                     mock_filter_mappings: MagicMock,
                     mock_run_sync_mappings: MagicMock) -> None:
        '''Tests that dependent functions are called with expected parameters.'''
        # Set up mocks
        mock_record_result = RecordResult(collection_root=ET.Element('collection'), tracks_added=0, tracks_updated=0)
        mock_process_result = ProcessResult(processed_files=[('/in', '/out')], missing_art_paths=['missing_art'], archives_extracted=0, files_encoded=0)
        mock_mappings_changed = [self.create_mock_file_mapping(0), self.create_mock_file_mapping(1)]
        mock_mappings_created = [self.create_mock_file_mapping(2)]
        mock_mappings_filtered = [self.create_mock_file_mapping(0)]

        mock_sync_result = SyncResult(mappings=[], batches=[SyncBatchResult(date_context='', files_processed=3, success=True)])

        mock_record_collection.return_value = mock_record_result
        mock_process.return_value = mock_process_result
        mock_run_sync_mappings.return_value = mock_sync_result
        mock_compare_tags.return_value = mock_mappings_changed.copy()
        mock_create_sync_mappings.return_value = mock_mappings_created.copy()
        mock_filter_mappings.return_value = mock_mappings_filtered.copy()

        # Call target function
        mock_library = '/mock/library'
        mock_client_mirror = '/mock/client/mirror'
        mock_extensions = {'.mock_ext'}
        mock_hints = {'mock_hint'}
        actual = music.update_library(MOCK_INPUT_DIR,
                                      mock_library,
                                      mock_client_mirror,
                                      self.MOCK_COLLECTION_EXPORT_DIR,
                                      self.MOCK_PROCESSED_COLLECTION,
                                      self.MOCK_MERGED_COLLECTION,
                                      mock_extensions,
                                      mock_hints,
                                      dry_run=True)

        # Assert expectations
        ## Call parameters: process
        mock_process.assert_called_once_with(MOCK_INPUT_DIR, mock_library, mock_extensions, mock_hints, dry_run=True)

        ## Call parameters: find_latest_file
        mock_find_latest_file.assert_called_once_with(self.MOCK_COLLECTION_EXPORT_DIR)

        ## Call parameters: merge_collections
        mock_merge_collections.assert_called_once_with(mock_find_latest_file.return_value, self.MOCK_PROCESSED_COLLECTION)

        ## Call parameters: write_root
        mock_write_root.assert_called_once_with(mock_merge_collections.return_value, self.MOCK_MERGED_COLLECTION)

        ## Call parameters: record_collection
        mock_record_collection.assert_called_once_with(mock_library, self.MOCK_MERGED_COLLECTION, self.MOCK_PROCESSED_COLLECTION, dry_run=True)

        ## Call parameters: compare_tags
        mock_compare_tags.assert_called_once_with(mock_library, mock_client_mirror)

        ## Call parameters: create_sync_mappings
        mock_create_sync_mappings.assert_called_once_with(mock_record_result.collection_root, mock_client_mirror)

        ## Call: filter_path_mappings
        mock_filter_mappings.assert_called_once_with(mock_mappings_changed, mock_record_result.collection_root, constants.XPATH_PRUNED)

        ## Call parameters: run_sync_mappings
        expected_mappings = mock_mappings_created + mock_mappings_filtered
        mock_run_sync_mappings.assert_called_once_with(expected_mappings, full_scan=True, dry_run=True)

        ## Result
        self.assertEqual(actual.process_result, mock_process_result)
        self.assertEqual(actual.record_result, mock_record_result)
        self.assertEqual(actual.sync_result, mock_sync_result)
        self.assertListEqual(actual.changed_mappings, mock_mappings_filtered)
        
    def create_mock_file_mapping(self, index: int) -> FileMapping:
        create_mock_path: Callable[[str, int], str] = lambda p, n: os.path.join(p, f"mock_file_{n}")
        return (create_mock_path(MOCK_INPUT_DIR, index), create_mock_path(MOCK_OUTPUT_DIR, index))

class TestParseArgs(unittest.TestCase):
    '''Tests for music.parse_args and argument validation.'''

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

    @patch('os.path.exists', return_value=True)
    def test_valid_update_library(self, mock_exists: MagicMock) -> None:
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

    @patch('sys.exit')
    def test_missing_input(self, mock_exit: MagicMock) -> None:
        '''Tests that missing --input causes error.'''
        argv = ['sweep', '--output', '/out']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_multi_arg_missing_output(self, mock_exit: MagicMock) -> None:
        '''Tests that multi-arg functions require --output.'''
        argv = ['sweep', '--input', '/in']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', return_value=True)
    def test_update_library_missing_client_mirror(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library requires --client-mirror-path.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', return_value=True)
    def test_update_library_missing_collection_export_dir(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library requires --collection-export-dir-path.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/mirror',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', return_value=True)
    def test_update_library_missing_processed_collection(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library requires --processed-collection-path.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/exports',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', return_value=True)
    def test_update_library_missing_merged_collection(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library requires --merged-collection-path.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', side_effect=lambda p: p != '/nonexistent')
    # TODO: refactor tests to use with pattern to assert exceptions rather than checking exit code
    def test_update_library_invalid_client_mirror_path(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library validates client_mirror_path exists.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/nonexistent',
                '--collection-export-dir-path', '/exports',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    @patch('os.path.exists', side_effect=lambda p: p != '/nonexistent')
    def test_update_library_invalid_collection_export_dir_path(self, mock_exists: MagicMock, mock_exit: MagicMock) -> None:
        '''Tests that update_library validates collection_export_dir_path exists.'''
        argv = ['update_library', '--input', '/in', '--output', '/out',
                '--client-mirror-path', '/mirror',
                '--collection-export-dir-path', '/nonexistent',
                '--processed-collection-path', '/processed.xml',
                '--merged-collection-path', '/merged.xml']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

    @patch('sys.exit')
    def test_invalid_function(self, mock_exit: MagicMock) -> None:
        '''Tests that invalid function name causes error.'''
        argv = ['invalid', '--input', '/in', '--output', '/out']
        music.parse_args(music.Namespace.FUNCTIONS, music.Namespace.FUNCTIONS_SINGLE_ARG, argv)

        mock_exit.assert_called_with(2)

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

    @patch('os.path.exists', return_value=True)
    def test_dry_run_with_update_library(self, mock_exists: MagicMock) -> None:
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
