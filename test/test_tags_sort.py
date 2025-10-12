import unittest
import os
from unittest.mock import patch, MagicMock
from PIL import Image

from src import constants
from src.tags import Tags

# Test targets
from src import tags_sort

# Constants
MOCK_ARTIST        = 'mock_artist'
MOCK_ALBUM         = 'mock_album'
MOCK_TITLE         = 'mock_title'
MOCK_GENRE         = 'mock_genre'
MOCK_MUSIC_KEY_KEY = 'mock_music_key'
MOCK_IMAGE         = Image.new('RGB', (1, 1), color='white')

MOCK_INPUT_DIR = '/mock/input'
MOCK_DATE_ADDED    = 'mock_date_added'

# Helpers
def create_full_mock_tags() -> Tags:
    '''Convenience function to create a tags instance with all possible attributes.'''
    return Tags(MOCK_ARTIST,
                MOCK_ALBUM,
                MOCK_TITLE,
                MOCK_GENRE,
                MOCK_MUSIC_KEY_KEY,
                MOCK_IMAGE)

# Test classes
class TestSortHierarchy(unittest.TestCase):
    '''Tests for tags_sort.sort_hierarchy.'''
    
    @patch('shutil.move')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('src.tags_sort.clean_dirname_simple')
    @patch('src.tags.Tags.load')
    @patch('src.music.prune')
    @patch('os.walk')
    def test_success_default_args(self,
                                  mock_walk: MagicMock,
                                  mock_prune: MagicMock,
                                  mock_load: MagicMock,
                                  mock_clean_dirname: MagicMock,
                                  mock_path_exists: MagicMock,
                                  mock_makedirs: MagicMock,
                                  mock_move: MagicMock) -> None:
        '''Tests that an input file is moved to the expected directory output structure with default arguments.'''
        # Set up mocks
        mock_filename = 'mock_file.mp3'
        mock_walk.return_value = [(MOCK_INPUT_DIR, [], [mock_filename])]
        mock_tags = create_full_mock_tags()
        mock_load.return_value = mock_tags
        mock_clean_dirname.side_effect = [MOCK_ARTIST, MOCK_ALBUM]
        mock_path_exists.return_value = False
        
        # Call target function
        tags_sort.sort_hierarchy(MOCK_INPUT_DIR, False, False, False, constants.MAPPING_MONTH)
        
        # Assert expectations
        mock_prune.assert_called_once()
        expected_output = f"{MOCK_INPUT_DIR}{os.sep}{mock_tags.artist}{os.sep}{mock_tags.album}{os.sep}{mock_filename}"
        mock_move.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_filename}", expected_output)
        mock_makedirs.assert_called_once()
        
    @patch('shutil.move')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('src.tags_sort.date_path')
    @patch('src.tags_sort.clean_dirname_simple')
    @patch('src.tags.Tags.load')
    @patch('src.music.prune')
    @patch('os.walk')
    def test_success_date(self,
                          mock_walk: MagicMock,
                          mock_prune: MagicMock,
                          mock_load: MagicMock,
                          mock_clean_dirname: MagicMock,
                          mock_date_path: MagicMock,
                          mock_path_exists: MagicMock,
                          mock_makedirs: MagicMock,
                          mock_move: MagicMock) -> None:
        '''Tests that an input file is moved to the expected directory output structure with a date argument.'''
        # Set up mocks
        mock_filename = 'mock_file.mp3'
        mock_walk.return_value = [(MOCK_INPUT_DIR, [], [mock_filename])]
        mock_tags = create_full_mock_tags()
        mock_load.return_value = mock_tags
        mock_clean_dirname.side_effect = [MOCK_ARTIST, MOCK_ALBUM]
        mock_date_path.return_value = MOCK_DATE_ADDED
        mock_path_exists.return_value = False
        
        # Call target function
        tags_sort.sort_hierarchy(MOCK_INPUT_DIR, False, True, False, constants.MAPPING_MONTH)
        
        # Assert expectations
        mock_prune.assert_called_once()
        expected_output = f"{MOCK_INPUT_DIR}{os.sep}{MOCK_DATE_ADDED}{os.sep}{mock_tags.artist}{os.sep}{mock_tags.album}{os.sep}{mock_filename}"
        mock_move.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_filename}", expected_output)
        mock_makedirs.assert_called_once()
    
    @patch('logging.info')
    @patch('shutil.move')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('src.tags_sort.clean_dirname_simple')
    @patch('src.tags.Tags.load')
    @patch('src.music.prune')
    @patch('os.walk')
    def test_success_skip_non_music(self,
                                    mock_walk: MagicMock,
                                    mock_prune: MagicMock,
                                    mock_load: MagicMock,
                                    mock_clean_dirname: MagicMock,
                                    mock_path_exists: MagicMock,
                                    mock_makedirs: MagicMock,
                                    mock_move: MagicMock,
                                    mock_log_info: MagicMock) -> None:
        '''Tests that an input file is skipped if it's not a music file.'''
        # Set up mocks
        mock_filename = 'mock_file'
        mock_walk.return_value = [(MOCK_INPUT_DIR, [], [mock_filename])]
        
        # Call target function
        tags_sort.sort_hierarchy(MOCK_INPUT_DIR, False, False, False, constants.MAPPING_MONTH)
        
        # Assert expectations
        mock_walk.assert_called_once()
        mock_prune.assert_called_once()
        mock_load.assert_not_called()
        mock_clean_dirname.assert_not_called()
        mock_path_exists.assert_not_called()
        mock_move.assert_not_called()
        mock_makedirs.assert_not_called()
        mock_log_info.assert_called_once()
        
    @patch('shutil.move')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('src.tags_sort.clean_dirname_simple')
    @patch('src.tags.Tags.load')
    @patch('src.music.prune')
    @patch('os.walk')
    def test_success_skip_tags_load_fail(self,
                                         mock_walk: MagicMock,
                                         mock_prune: MagicMock,
                                         mock_load: MagicMock,
                                         mock_clean_dirname: MagicMock,
                                         mock_path_exists: MagicMock,
                                         mock_makedirs: MagicMock,
                                         mock_move: MagicMock) -> None:
        '''Tests that an input file is skipped if its Tags fail to load.'''
        # Set up mocks
        mock_filename = 'mock_file.mp3'
        mock_walk.return_value = [(MOCK_INPUT_DIR, [], [mock_filename])]
        mock_load.return_value = None
        
        # Call target function
        tags_sort.sort_hierarchy(MOCK_INPUT_DIR, False, False, False, constants.MAPPING_MONTH)
        
        # Assert expectations
        mock_walk.assert_called_once()
        mock_prune.assert_called_once()
        mock_load.assert_called_once()
        mock_clean_dirname.assert_not_called()
        mock_path_exists.assert_not_called()
        mock_move.assert_not_called()
        mock_makedirs.assert_not_called()
