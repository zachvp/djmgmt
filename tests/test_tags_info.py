import unittest
from unittest.mock import patch, MagicMock

# Test target imports
from djmgmt import tags_info

# Constants
MOCK_INPUT_PATH = '/mock/input/path'
MOCK_INPUT_DIR  = '/mock/input'

# Test classes
class TestPromptLogDuplicates(unittest.TestCase):
    '''Tests for tags_info.log_duplicates'''
    
    @patch('logging.info')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success_duplicates(self,
                                mock_collect_paths: MagicMock,
                                mock_tags_load: MagicMock,
                                mock_log_info: MagicMock) -> None:
        '''Tests that duplicate files are logged.'''
        # Set up mocks
        mock_tags = MagicMock()
        mock_tags_load.side_effect = [mock_tags, mock_tags]
        mock_collect_paths.return_value = [MOCK_INPUT_PATH, MOCK_INPUT_PATH]
        
        # Call target function
        tags_info.log_duplicates(MOCK_INPUT_DIR)
        
        # Assert expectations
        self.assertEqual(mock_tags_load.call_count, 2)
        mock_log_info.assert_called_once()
        
    @patch('logging.info')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success_unique(self,
                                mock_collect_paths: MagicMock,
                                mock_tags_load: MagicMock,
                                mock_log_info: MagicMock) -> None:
        '''Tests that unique files are not logged.'''
        # Set up mocks
        mock_tags_load.side_effect = [MagicMock(), MagicMock()]
        mock_collect_paths.return_value = [MOCK_INPUT_PATH, MOCK_INPUT_PATH]
        
        # Call target function
        tags_info.log_duplicates(MOCK_INPUT_DIR)
        
        # Assert expectations
        self.assertEqual(mock_tags_load.call_count, 2)
        mock_log_info.assert_not_called()
        
    @patch('logging.info')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_error_tag_load(self,
                            mock_collect_paths: MagicMock,
                            mock_tags_load: MagicMock,
                            mock_log_info: MagicMock) -> None:
        '''Tests that tag load failure results in no logged duplicates.'''
        # Set up mocks
        mock_collect_paths.return_value = [MOCK_INPUT_PATH, MOCK_INPUT_PATH]
        mock_tags_load.return_value = None
        
        # Call target function
        tags_info.log_duplicates(MOCK_INPUT_DIR)
        
        # Assert expectations
        self.assertEqual(mock_tags_load.call_count, 2)
        mock_log_info.assert_not_called()

class TestPromptTagsInfoCollectIdentifiers(unittest.TestCase):
    '''Tests for tags_info.collect_identifiers.'''
    
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success(self,
                     mock_collect_paths: MagicMock,
                     mock_tags_load: MagicMock) -> None:
        '''Tests that the identifiers are loaded from the given path.'''
        # Set up mocks
        mock_collect_paths.return_value = [MOCK_INPUT_PATH]
        mock_identifier = 'mock_identifier'
        mock_tags = MagicMock()
        mock_tags.basic_identifier.return_value = mock_identifier
        mock_tags_load.return_value = mock_tags
        
        # Call target function
        actual = tags_info.collect_identifiers(MOCK_INPUT_DIR)
        
        # Assert expectations
        self.assertEqual(actual, [mock_identifier])
    
    @patch('logging.error')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_error_tags_load(self,
                             mock_collect_paths: MagicMock,
                             mock_tags_load: MagicMock,
                             mock_log_error: MagicMock) -> None:
        '''Tests that the identifiers are not loaded from the given path when the track tags can't load.'''
        # Set up mocks
        mock_collect_paths.return_value = [MOCK_INPUT_PATH]
        mock_tags_load.return_value = None
        
        # Call target function
        actual = tags_info.collect_identifiers(MOCK_INPUT_DIR)
        
        # Assert expectations
        self.assertEqual(len(actual), 0)
        mock_log_error.assert_called_once()

class TestPromptCompareTags(unittest.TestCase):
    '''Tests for src.tags_info.compare_tags.'''
    
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success_file_match(self, mock_collect_paths: MagicMock, mock_load_tags: MagicMock) -> None:
        '''Tests that matching filenames are returned.'''
        # Set up mocks
        mock_collect_paths.side_effect = [
            ['/mock/source/file_0.mp3'],
            ['/mock/compare/file_0.mp3']
        ]
        mock_load_tags.side_effect = [MagicMock(), MagicMock()]
        
        # Call target function
        actual = tags_info.compare_tags('/mock/source', '/mock/compare')
        
        # Assert expectations
        self.assertEqual(actual, [('/mock/source/file_0.mp3', '/mock/compare/file_0.mp3')])
        self.assertEqual(mock_collect_paths.call_count, 2)
        self.assertEqual(mock_load_tags.call_count, 2)
        
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success_file_difference(self, mock_collect_paths: MagicMock, mock_load_tags: MagicMock) -> None:
        '''Tests that non-matching filenames return no results.'''
        # Set up mocks
        mock_collect_paths.side_effect = [
            ['/mock/source/file_0.mp3'],
            ['/mock/compare/different.mp3']
        ]
        mock_load_tags.side_effect = [MagicMock(), MagicMock()]
        
        # Call target function
        actual = tags_info.compare_tags('/mock/source', '/mock/compare')
        
        # Assert expectations
        self.assertEqual(actual, [])
        self.assertEqual(mock_collect_paths.call_count, 2)
        mock_load_tags.assert_not_called()
        
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_success_load_tags_fail(self, mock_collect_paths: MagicMock, mock_load_tags: MagicMock) -> None:
        '''Tests that no results are returned if tag loading fails.'''
        # Set up mocks
        mock_collect_paths.side_effect = [
            ['/mock/source/file_0.mp3'],
            ['/mock/compare/file_0.mp3']
        ]
        mock_load_tags.return_value = None
        
        # Call target function
        actual = tags_info.compare_tags('/mock/source', '/mock/compare')
        
        # Assert expectations
        self.assertEqual(actual, [])
        self.assertEqual(mock_collect_paths.call_count, 2)
        self.assertEqual(mock_load_tags.call_count, 2)

class TestParseArgs(unittest.TestCase):
    '''Tests for tags_info.parse_args and argument validation.'''

    def test_valid_log_duplicates(self) -> None:
        '''Tests that log_duplicates can be called with only --input.'''
        argv = ['log_duplicates', '--input', '/mock/input']
        args = tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        self.assertEqual(args.function, 'log_duplicates')
        self.assertEqual(args.input, '/mock/input')
        self.assertIsNone(args.output)
        self.assertIsNone(args.comparison)

    def test_valid_write_identifiers(self) -> None:
        '''Tests that write_identifiers can be called with --input and --output.'''
        argv = ['write_identifiers', '--input', '/mock/input', '--output', '/mock/output.txt']
        args = tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        self.assertEqual(args.function, 'write_identifiers')
        self.assertEqual(args.input, '/mock/input')
        self.assertEqual(args.output, '/mock/output.txt')
        self.assertIsNone(args.comparison)

    def test_valid_compare(self) -> None:
        '''Tests that compare can be called with all required arguments.'''
        argv = ['compare', '--input', '/source', '--output', '/out.txt', '--comparison', '/compare']
        args = tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        self.assertEqual(args.function, 'compare')
        self.assertEqual(args.input, '/source')
        self.assertEqual(args.output, '/out.txt')
        self.assertEqual(args.comparison, '/compare')

    @patch('sys.exit')
    def test_missing_input(self, mock_exit: MagicMock) -> None:
        '''Tests that missing --input causes error.'''
        argv = ['log_duplicates']
        tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        mock_exit.assert_called_once_with(2)

    @patch('sys.exit')
    def test_write_identifiers_missing_output(self, mock_exit: MagicMock) -> None:
        '''Tests that write_identifiers requires --output.'''
        argv = ['write_identifiers', '--input', '/mock/input']
        tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        mock_exit.assert_called_once_with(2)

    @patch('sys.exit')
    def test_write_paths_missing_output(self, mock_exit: MagicMock) -> None:
        '''Tests that write_paths requires --output.'''
        argv = ['write_paths', '--input', '/mock/input']
        tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        mock_exit.assert_called_once_with(2)

    @patch('sys.exit')
    def test_compare_missing_comparison(self, mock_exit: MagicMock) -> None:
        '''Tests that compare requires --comparison.'''
        argv = ['compare', '--input', '/source', '--output', '/out.txt']
        tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        mock_exit.assert_called_once_with(2)

    @patch('sys.exit')
    def test_invalid_function(self, mock_exit: MagicMock) -> None:
        '''Tests that invalid function name causes error.'''
        argv = ['invalid_function', '--input', '/mock/input']
        tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        mock_exit.assert_called_once_with(2)

    def test_path_normalization(self) -> None:
        '''Tests that paths are normalized.'''
        argv = ['log_duplicates', '--input', 'relative/path']
        args = tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        # os.path.normpath should have been applied
        import os
        expected_path = os.path.normpath('relative/path')
        self.assertEqual(args.input, expected_path)

    def test_all_paths_normalized(self) -> None:
        '''Tests that all paths (input, output, comparison) are normalized.'''
        argv = ['compare', '--input', 'source/', '--output', 'output/', '--comparison', 'compare/']
        args = tags_info.parse_args(tags_info.Namespace.FUNCTIONS, argv)

        import os
        self.assertEqual(args.input, os.path.normpath('source/'))
        self.assertEqual(args.output, os.path.normpath('output/'))
        self.assertEqual(args.comparison, os.path.normpath('compare/'))
