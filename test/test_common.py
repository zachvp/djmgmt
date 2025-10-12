import unittest
import logging
import os
from unittest.mock import MagicMock, patch, mock_open
from typing import cast

# Constants
PROJECT_ROOT = os.path.abspath(f"{os.path.dirname(__file__)}/{os.path.pardir}")
MOCK_INPUT = '/mock/input'

# Custom imports
import sys
sys.path.append(PROJECT_ROOT)

from src import common

class TestConfigureLog(unittest.TestCase):
    @patch('logging.basicConfig')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_configure_log_default(self,
                                   mock_makedirs: MagicMock,
                                   mock_path_exists: MagicMock,
                                   mock_basic_config: MagicMock) -> None:
        '''Tests that a default log configuration is created for common.log'''
        # call test target
        common.configure_log()
        
        # assert expectation
        LOG_PATH = f"{PROJECT_ROOT}/src/logs/common.log"
        self.assertEqual(mock_basic_config.call_args.kwargs['filename'], LOG_PATH)
        self.assertEqual(mock_basic_config.call_args.kwargs['level'], logging.DEBUG)
        
    @patch('logging.basicConfig')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_configure_log_custom_args(self,
                                       mock_makedirs: MagicMock,
                                       mock_path_exists: MagicMock,
                                       mock_basic_config: MagicMock) -> None:
        '''Tests that a custom log configuration is respected.'''
        # call test target
        common.configure_log(level=logging.INFO, path=__file__)
        
        # assert expectation
        LOG_PATH = f"{PROJECT_ROOT}/test/logs/test_common.log"
        self.assertEqual(mock_basic_config.call_args.kwargs['filename'], LOG_PATH)
        self.assertEqual(mock_basic_config.call_args.kwargs['level'], logging.INFO)
        
class TestFindDateContext(unittest.TestCase):
    def test_success_basic(self) -> None:
        path = '/data/tracks-output/2022/04 april/24/1-Gloria_Jones_-_Tainted_Love_(single_version).mp3'
        actual = common.find_date_context(path)
        
        self.assertIsNotNone(actual)
        actual = cast(tuple[str, int], actual)
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual, ('2022/04 april/24', 3))
    
    def test_success_tricky_metadata_subpath(self) -> None:
        path = '/Users/user/developer/test-private/data/tracks-output/2024/08 august/18/Paolo Mojo/1983/159678_1983_(Eric_Prydz_Remix).aiff'
        actual = common.find_date_context(path)
        
        self.assertIsNotNone(actual)
        actual = cast(tuple[str, int], actual)
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual, ('2024/08 august/18', 7))
    
    def test_success_invalid_month_name(self):
        path = '/mock/input/2025/08 aug/22/artist/album/track.mp3'
        actual = common.find_date_context(path)
        
        self.assertIsNone(actual)
        
    def test_success_invalid_month_index(self):
        path = '/mock/input/2025/01 august/22/artist/album/track.mp3'
        actual = common.find_date_context(path)
        
        self.assertIsNone(actual)

class TestCollectPaths(unittest.TestCase):
    @patch('os.walk')
    def test_success_simple(self, mock_walk: MagicMock) -> None:
        '''Tests that the full path of a single file is returned.'''
        # Set up mocks
        mock_file = 'mock_file'
        mock_walk.return_value = [(MOCK_INPUT, [], [mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT)
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [f"{MOCK_INPUT}{os.sep}{mock_file}"])
        
    @patch('os.walk')
    def test_success_ignore_hidden_files(self, mock_walk: MagicMock) -> None:
        '''Tests that a hidden file is ignored.'''
        # Set up mocks
        mock_file = 'mock_file'
        mock_hidden = '.mock_hidden'
        mock_walk.return_value = [(MOCK_INPUT, [], [mock_hidden, mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT)
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [f"{MOCK_INPUT}{os.sep}{mock_file}"])
        
    @patch('os.walk')
    def test_success_ignore_hidden_directories(self, mock_walk: MagicMock) -> None:
        '''Tests that a file in a hidden directory is ignored.'''
        # Set up mocks
        mock_file = 'mock_file'
        mock_hidden = '.mock_hidden'
        mock_walk.return_value = [(MOCK_INPUT, [mock_hidden], []),
                                  (os.path.join(MOCK_INPUT, mock_hidden), [], [mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT)
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [])
        
    @patch('os.walk')
    def test_success_filter_include(self, mock_walk: MagicMock) -> None:
        '''Tests that a file that matches the filter is collected.'''
        # Set up mocks
        mock_file = 'mock_file.foo'
        mock_walk.return_value = [(MOCK_INPUT, [], [mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT, filter={'.foo'})
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [f"{MOCK_INPUT}{os.sep}{mock_file}"])
        
    @patch('os.walk')
    def test_success_filter_exclude(self, mock_walk: MagicMock) -> None:
        '''Tests that a file that doesn't match the filter is excluded.'''
        # Set up mocks
        mock_file = 'mock_file.foo'
        mock_walk.return_value = [(MOCK_INPUT, [], [mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT, filter={'.bar'})
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [])
        
    @patch('os.walk')
    def test_success_filter_empty(self, mock_walk: MagicMock) -> None:
        '''Tests that an empty filter still collects the file.'''
        # Set up mocks
        mock_file = 'mock_file.foo'
        mock_walk.return_value = [(MOCK_INPUT, [], [mock_file])]
        
        # Call target function
        actual = common.collect_paths(MOCK_INPUT, filter=set())
        
        # Assert expectations
        mock_walk.assert_called_once_with(MOCK_INPUT)
        self.assertEqual(actual, [f"{MOCK_INPUT}{os.sep}{mock_file}"])

class TestWritePaths(unittest.TestCase):
    @patch('builtins.open', new_callable=mock_open)
    def test_success(self, mock_file_open: MagicMock) -> None:
        '''Tests that the function sorts the paths and writes to the given file'''
        # Set up mocks
        paths = ['b', 'a']
        
        # Call target function
        common.write_paths(paths, MOCK_INPUT)

        # Assert expectations
        mock_file_open.assert_called_once_with(MOCK_INPUT, 'w', encoding='utf-8')
        mock_file = mock_file_open.return_value
        mock_file.writelines.assert_called_once_with(['a\n', 'b\n'])
