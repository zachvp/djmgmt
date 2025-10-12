import unittest
from unittest.mock import patch, MagicMock

# Test target imports
from src import tags_info

# Constants
MOCK_INPUT_PATH = '/mock/input/path'
MOCK_INPUT_DIR  = '/mock/input'

# Test classes
class TestPromptLogDuplicates(unittest.TestCase):
    '''Tests for tags_info.log_duplicates'''
    
    @patch('logging.info')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
    
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
    
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
