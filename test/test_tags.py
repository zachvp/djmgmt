# Core dependencies
import unittest
import io
import numpy as np
import mutagen.aiff, mutagen.id3, mutagen.flac, mutagen.mp3, mutagen.wave

from imagehash import ImageHash
from PIL import Image
from unittest.mock import patch, MagicMock
from typing import cast

# Test targets
from src.tags import Tags

# Constants
## Mock input arguments and values
MOCK_INPUT_PATH    = '/mock/input'
MOCK_ARTIST        = 'mock_artist'
MOCK_ALBUM         = 'mock_album'
MOCK_TITLE         = 'mock_title'
MOCK_GENRE         = 'mock_genre'
MOCK_MUSIC_KEY_KEY = 'mock_music_key'
MOCK_IMAGE         = Image.new('RGB', (1, 1), color='white')
MOCK_DIFF          = 'mock_diff'

## Mock tag data keys
MOCK_TITLE_KEY     = 'mock_title_key'
MOCK_ARTIST_KEY    = 'mock_artist_key'
MOCK_ALBUM_KEY     = 'mock_album_key'
MOCK_GENRE_KEY     = 'mock_genre_key'
MOCK_MUSIC_KEY_KEY = 'mock_music_key_key'

## Mock track file data
MOCK_TRACK_TAGS = {
    MOCK_TITLE_KEY     : MOCK_TITLE,
    MOCK_ARTIST_KEY    : MOCK_ARTIST,
    MOCK_ALBUM_KEY     : MOCK_ALBUM,
    MOCK_GENRE_KEY     : MOCK_GENRE,
    MOCK_MUSIC_KEY_KEY : MOCK_MUSIC_KEY_KEY,
}

# Mock classes: Corresponds to each type in constants.EXTENSIONS
class MockMP3(MagicMock, mutagen.mp3.MP3):
    pass

class MockWav(MagicMock, mutagen.wave.WAVE):
    pass

class MockAIFF(MagicMock, mutagen.aiff.AIFF):
    pass

class MockFLAC(MagicMock, mutagen.flac.FLAC):
    pass

# Helpers
def create_mock_image_data() -> bytes:
    '''Generates raw data for a minimal PNG image.'''
    image = Image.new('RGB', (1, 1), color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()

def image_to_bytes(image: Image.Image) -> bytes:
    '''Converts the given PNG image to bytes'''
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()

def create_full_mock_tags() -> Tags:
    '''Convenience function to create a tags instance with all possible attributes.'''
    return Tags(MOCK_ARTIST,
                MOCK_ALBUM,
                MOCK_TITLE,
                MOCK_GENRE,
                MOCK_MUSIC_KEY_KEY,
                MOCK_IMAGE)
    
def configure_mock_track(mock_track: MagicMock, data: dict[str, str] = MOCK_TRACK_TAGS) -> None:
    mock_track.__contains__.side_effect = data.__contains__
    mock_track.__getitem__.side_effect = data.__getitem__
    mock_track.__iter__.side_effect = data.__iter__

class TestTags(unittest.TestCase):
    '''Tests for the Tags class.'''
    
    def test_success_init_full(self) -> None:
        '''Tests that all attributes are properly initialized.'''
        # Call target function
        actual = create_full_mock_tags()
        
        # Assert expectations
        self.assertEqual(actual.artist, MOCK_ARTIST)
        self.assertEqual(actual.album, MOCK_ALBUM)
        self.assertEqual(actual.title, MOCK_TITLE)
        self.assertEqual(actual.genre, MOCK_GENRE)
        self.assertEqual(actual.key, MOCK_MUSIC_KEY_KEY)
        
        ## Image assertions: compare byte contents
        self.assertIsNotNone(actual.cover_image)
        self.assertEqual(image_to_bytes(cast(Image.Image, actual.cover_image)), image_to_bytes(MOCK_IMAGE))
        
    def test_success_str(self) -> None:
        '''Tests that all attributes are present in the string representation.'''
        # Call target function
        actual = str(create_full_mock_tags())
        
        # Assert expectations
        self.assertIn(MOCK_ARTIST, actual)
        self.assertIn(MOCK_ALBUM, actual)
        self.assertIn(MOCK_TITLE, actual)
        self.assertIn(MOCK_GENRE, actual)
        self.assertIn(MOCK_MUSIC_KEY_KEY, actual)
    
    def test_success_eq(self) -> None:
        '''Tests that two Tags instances with identical attributes are considered equal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        self.assertEqual(lhs, rhs)
        
    def test_success_not_eq_artist(self) -> None:
        '''Tests that two Tags instances with different artist attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        rhs.artist = cast(str, rhs.artist)
        rhs.artist += MOCK_DIFF
        
        self.assertNotEqual(lhs, rhs)
        
    def test_success_not_eq_album(self) -> None:
        '''Tests that two Tags instances with different album attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        rhs.album = cast(str, rhs.album)
        rhs.album += MOCK_DIFF
        
        self.assertNotEqual(lhs, rhs)
        
    def test_success_not_eq_title(self) -> None:
        '''Tests that two Tags instances with different title attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        rhs.title = cast(str, rhs.title)
        rhs.title += MOCK_DIFF
        
        self.assertNotEqual(lhs, rhs)
        
    def test_success_not_eq_genre(self) -> None:
        '''Tests that two Tags instances with different genre attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        rhs.genre = cast(str, rhs.genre)
        rhs.genre += MOCK_DIFF
        
        self.assertNotEqual(lhs, rhs)
    
    def test_success_not_eq_key(self) -> None:
        '''Tests that two Tags instances with different key attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        
        rhs.key = cast(str, rhs.key)
        rhs.key += MOCK_DIFF
        
        self.assertNotEqual(lhs, rhs)
        
    @patch('src.tags.Tags._eq_cover_image')
    def test_success_not_eq_cover_image(self, mock_eq_cover: MagicMock) -> None:
        '''Tests that two Tags instances with different cover image attributes are considered unequal.'''
        lhs = create_full_mock_tags()
        rhs = create_full_mock_tags()
        mock_eq_cover.return_value = False
        
        self.assertNotEqual(lhs, rhs)

class TestTagsGetTrackKey(unittest.TestCase):
    '''Tests for Tags.get_track_key'''
    
    def test_success_key_exists(self) -> None:
        '''Tests that a key that exists in the track is found.'''
        # Configure mocks
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        
        # Call target function
        actual = Tags.get_track_key(mock_track, {MOCK_TITLE_KEY})
        
        # Assert expectations
        self.assertEqual(actual, MOCK_TITLE_KEY)
    
    def test_success_key_missing(self) -> None:
        '''Tests that a key missing from the track returns None.'''
        # Configure mocks
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        
        # Call target function
        actual = Tags.get_track_key(mock_track, {'mock_missing_key'})
        
        # Assert expectations
        self.assertIsNone(actual)
        
    @patch('logging.error')
    def test_error_key_missing(self, mock_log_error: MagicMock) -> None:
        '''Tests that a raised ValueError returns None and logs an error.'''
        # Configure mocks
        mock_track = MagicMock()
        mock_track.__contains__.side_effect = ValueError()
        
        # Call target function
        actual = Tags.get_track_key(mock_track, {'mock_missing_key'})
        
        # Assert expectations
        self.assertIsNone(actual)
        mock_log_error.assert_called_once()

class TestTagsExtractTagValue(unittest.TestCase):
    '''Tests for Tags.extract_tag_value'''
    
    @patch('src.tags.Tags.get_track_key')
    def test_success_key_exists_string(self, mock_get_track_key: MagicMock) -> None:
        '''Tests that a tag string is extracted from a tag containing the corresponding entry.'''
        # Configure mocks
        mock_get_track_key.return_value = MOCK_TITLE_KEY
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        
        # Call target function
        actual = Tags.extract_tag_value(mock_track, set())
        
        # Assert expectations
        self.assertEqual(actual, MOCK_TITLE)
    
    @patch('src.tags.Tags.get_track_key')
    def test_success_key_none(self, mock_get_track_key: MagicMock) -> None:
        '''Tests that None is returned if get_track_key returns None.'''
        # Configure mocks
        mock_get_track_key.return_value = None
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        
        # Call target function
        actual = Tags.extract_tag_value(mock_track, set())
        
        # Assert expectations
        self.assertIsNone(actual)

class TestTagsExtractCoverImage(unittest.TestCase):
    '''Tests for Tags.extract_cover_image.'''
    
    # Test cases
    def test_success_mp3(self) -> None:
        '''Tests that the cover image is properly extracted for MP3.'''
        # Set up mocks
        mock_track = MockMP3()
        
        # Run the common test logic for file type
        self.run_extract_cover_id3_filetype(mock_track)
        
    def test_success_wav(self) -> None:
        '''Tests that the cover image is properly extracted for WAV.'''
        # Set up mocks
        mock_track = MockWav()
        
        # Run the common test logic for file type
        self.run_extract_cover_id3_filetype(mock_track)
        
    def test_success_aiff(self) -> None:
        '''Tests that the cover image is properly extracted for AIFF.'''
        # Set up mocks
        mock_track = MockAIFF()
        
        # Run the common test logic for file type
        self.run_extract_cover_id3_filetype(mock_track)
        
    def test_success_flac(self) -> None:
        '''Tests that the cover image is properly extracted for FLAC.'''
        # Set up mocks: FLAC images are stored differently than ID3-like images, so custom mocking is required.
        mock_data = create_mock_image_data()

        ## Mock the track file contents
        mock_track = MockFLAC()
        
        ## Additional mock config for FLAC picture
        picture = mutagen.flac.Picture()
        picture.type = mutagen.id3.PictureType.COVER_FRONT
        picture.data = mock_data
        mock_track.metadata_blocks = []
        mock_track.add_picture(picture)
        
        ## Configure the mock mutagen tags
        mock_tag_data = self.create_mock_tag_data(mock_data, include_tags=False)
        
        # Set the mock attributes
        mock_track.tags = mock_tag_data
        
        # Call target function
        actual = Tags.extract_cover_image(mock_track)
        
        # Assert expectations
        ## Assert that the function extracted the expected image instance
        actual = cast(Image.Image, actual)
        self.assert_image(actual, mock_data)

    def test_success_no_image(self) -> None:
        '''Tests that a track without image metatadata returns None.'''
        # Set up mocks
        mock_track = MagicMock()
        
        # Call target function
        actual = Tags.extract_cover_image(mock_track)
        
        # Assert expectations
        self.assertIsNone(actual)
    
    @patch('logging.warning')
    @patch('PIL.PngImagePlugin.PngImageFile.verify') # mock images use PNG instance
    def test_error_invalid_image(self, mock_verify: MagicMock, mock_log_warning: MagicMock) -> None:
        '''Tests that a track that has corrupted image data will return None and log a warning.'''
        # Set up mocks
        ## Mock track
        mock_track = MockMP3()
        mock_data = create_mock_image_data()
        mock_tag_data = self.create_mock_tag_data(mock_data)
        mock_track.tags = mock_tag_data
        
        ## Mock verification error
        mock_verify.side_effect = Exception('mock image verification error')
        
        # Call target function
        actual = Tags.extract_cover_image(mock_track)
        
        # Assert expectations
        self.assertIsNone(actual)
        mock_log_warning.assert_called()
        
    # Helpers
    def assert_image(self, actual: Image.Image, mock_data: bytes) -> None:
        # Assert image content matches mock data
        self.assertIsNotNone(actual)
        self.assertEqual(image_to_bytes(actual), mock_data)
        
    def create_mock_tag_data(self, mock_data: bytes, include_tags: bool = True) -> MagicMock:
        mock_tag_data = MagicMock()
        tags_data = {}
        if include_tags:
            tags_data = {
                'mock_id3_apic': mutagen.id3.APIC(data=mock_data),
            }

        mock_tag_data.__contains__.side_effect = tags_data.__contains__
        mock_tag_data.__getitem__.side_effect = tags_data.__getitem__
        mock_tag_data.values.side_effect = tags_data.values
        return mock_tag_data
        
    def run_extract_cover_id3_filetype(self, mock_track: MagicMock):
        '''Common test runner for ID3-like file type cases (e.g. MP3, AIFF, WAV).'''
        # Configure mock data for the image and tags
        mock_data = create_mock_image_data()
        
        mock_tag_data = self.create_mock_tag_data(mock_data)
        mock_track.tags = mock_tag_data
        
        # Call target function
        actual = Tags.extract_cover_image(mock_track)
        
        # Assert expectations
        ## Assert that the function extracted the expected image instance
        actual = cast(Image.Image, actual)
        self.assert_image(actual, mock_data)

class TestTagsLoad(unittest.TestCase):
    '''Tests for Tags.load.'''
    
    @patch('src.tags.Tags.extract_cover_image')
    @patch('src.tags.Tags.extract_tag_value')
    @patch('mutagen.File')
    def test_success(self,
                     mock_file_constructor: MagicMock,
                     mock_extract_tag_value: MagicMock,
                     mock_extract_cover_image: MagicMock):
        '''Tests that all Tags attributes can be loaded.'''
        # Configure mocks
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        
        mock_file_constructor.return_value = mock_track
        mock_extract_tag_value.side_effect = [MOCK_TITLE, MOCK_ARTIST, MOCK_ALBUM, MOCK_GENRE, MOCK_MUSIC_KEY_KEY]
        mock_extract_cover_image.return_value = MOCK_IMAGE
        
        # Call target function
        actual = Tags.load(MOCK_INPUT_PATH)
        
        # Assert expectations
        mock_file_constructor.assert_called_once_with(MOCK_INPUT_PATH)
        
        self.assertIsNotNone(actual)
        actual = cast(Tags, actual)
        
        ## Assert existing tags
        self.assertEqual(actual.artist, MOCK_ARTIST)
        self.assertEqual(actual.album, MOCK_ALBUM)
        self.assertEqual(actual.title, MOCK_TITLE)
        self.assertEqual(actual.genre, MOCK_GENRE)
        self.assertEqual(actual.key, MOCK_MUSIC_KEY_KEY)
        self.assertEqual(actual.cover_image, MOCK_IMAGE)
    
    @patch('src.tags.Tags.get_track_key')
    @patch('mutagen.File')
    def test_success_no_artist_no_title(self,
                                        mock_file_constructor: MagicMock,
                                        mock_get_track_key: MagicMock) -> None:
        '''Tests that None is returned when title and artist are missing.'''
        # Set up mocks
        mock_track = MagicMock()
        configure_mock_track(mock_track)
        mock_file_constructor.return_value = mock_track
        
        ## Mock get track key
        mock_get_track_key.side_effect = [None, None, MOCK_ALBUM_KEY, MOCK_GENRE_KEY, MOCK_MUSIC_KEY_KEY]
        
        # Call target function
        actual = Tags.load(MOCK_INPUT_PATH)
        
        # Assert expectations
        self.assertIsNone(actual)
    
    @patch('mutagen.File')
    def test_error_file_load(self,
                             mock_file_constructor: MagicMock) -> None:
        '''Tests that None is returned if the file loading fails.'''
        # Set up mocks
        mock_file_constructor.side_effect = mutagen.MutagenError()
        
        # Call target function
        actual = Tags.load('mock_bad_path')
        
        # Assert expectations
        self.assertIsNone(actual)
    
    @patch('mutagen.File')
    def test_error_file_empty(self,
                              mock_file_constructor: MagicMock) -> None:
        '''Tests that None is returned if the file loading returns None.'''
        # Set up mocks
        mock_file_constructor.return_value = None
        
        # Call target function
        actual = Tags.load(MOCK_INPUT_PATH)
        
        # Assert expectations
        self.assertIsNone(actual)
        
    @patch('mutagen.File')
    def test_error_file_no_tags(self,
                                mock_file_constructor: MagicMock) -> None:
        '''Tests that None is returned if the file tags are None.'''
        # Set up mocks
        mock_file_constructor.tags = None
        
        # Call target function
        actual = Tags.load(MOCK_INPUT_PATH)
        
        # Assert expectations
        self.assertIsNone(actual)

class TestTagsBasicIdentifier(unittest.TestCase):
    '''Tests for Tags.basic_identifier.'''
    
    def test_success_simple(self) -> None:
        '''Test for a Tags instance with only artist and title.'''
        # Call target function
        tags = Tags(artist=MOCK_ARTIST, title=MOCK_TITLE)
        actual = tags.basic_identifier()
        
        # Assert expectations
        self.assertEqual(actual, f"{MOCK_ARTIST} - {MOCK_TITLE}")
    
    def test_success_full(self) -> None:
        '''Test for a Tags instance with all attributes.'''
        # Call target function
        tags = create_full_mock_tags()
        actual = tags.basic_identifier()
        
        # Assert expectations
        self.assertEqual(actual, f"{MOCK_ARTIST} - {MOCK_TITLE}")
        
    def test_success_missing_title(self) -> None:
        '''Test for a Tags instance with no title.'''
        # Call target function
        tags = Tags(artist=MOCK_ARTIST)
        actual = tags.basic_identifier()
        
        # Assert expectations
        self.assertEqual(actual, f"{MOCK_ARTIST} - none")
        
    def test_success_missing_arist(self) -> None:
        '''Test for a Tags instance with no artist.'''
        # Call target function
        tags = Tags(title=MOCK_TITLE)
        actual = tags.basic_identifier()
        
        # Assert expectations
        self.assertEqual(actual, f"none - {MOCK_TITLE}")
    
    def test_success_normalize_format(self) -> None:
        '''Tests that the output is normalized for artist & title with mixed case and trailing title whitespace.'''
        # Call target function
        tags = Tags(title='mOcK_tItLe    ', artist='MoCk_ArTiSt')
        actual = tags.basic_identifier()
        
        # Assert expectations
        self.assertEqual(actual, f"{MOCK_ARTIST} - {MOCK_TITLE}")

class TestTagsHashCoverImage(unittest.TestCase):
    '''Tests for the 'tags.Tags._hash_cover_image' method.'''
    
    @patch('imagehash.phash')
    def test_success_image_present(self, mock_phash: MagicMock) -> None:
        '''Tests that a Tags instance containing an image is hashed with that image.'''
        # Set up mocks
        mock_hash = MagicMock()
        mock_phash.return_value = mock_hash
        
        # Call target function
        tags = create_full_mock_tags()
        actual = tags._hash_cover_image()
        
        # Assert expectations
        self.assertEqual(actual, mock_hash)
        mock_phash.assert_called_once_with(MOCK_IMAGE)
    
    @patch('imagehash.phash')
    def test_success_image_missing(self, mock_phash: MagicMock) -> None:
        '''Tests that a Tags instance missing an image generates None for the hash.'''
        # Call target function with tags that lack image data
        tags = Tags(MOCK_ARTIST,
                    MOCK_ALBUM,
                    MOCK_TITLE,
                    MOCK_GENRE,
                    MOCK_MUSIC_KEY_KEY)
        actual = tags._hash_cover_image()
        
        # Assert expectations
        self.assertIsNone(actual, 'Expect None value for hash when image is missing.')
        mock_phash.assert_not_called()
    
    @patch('logging.error')
    @patch('imagehash.phash')
    def test_error_hash_failure(self, mock_phash: MagicMock, mock_log_error: MagicMock) -> None:
        '''Tests that a hash failure raises the expected error.'''
        # Set up mocks
        mock_phash.side_effect = Exception()
        
        # Call target function, exepting exception due to the mock error
        tags = create_full_mock_tags()
        with self.assertRaises(ValueError):
            tags._hash_cover_image()
            
        # Assert expectations
        mock_phash.assert_called_once_with(MOCK_IMAGE)
        mock_log_error.assert_called()
        
class TestEQCoverImage(unittest.TestCase):
    '''Tests for the 'tags.Tags._eq_cover_image' function.'''
    
    @patch('src.tags.Tags._hash_cover_image')
    def test_success_same_images(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison for images with the same hash returns True.'''
        # Set up mocks
        mock_cover_hash.return_value = ImageHash(np.array([[0, 0, 0, 1]], dtype=np.bool_))
        
        # Call target function
        tags_lhs = Tags()
        tags_rhs = Tags()
        actual = tags_lhs._eq_cover_image(tags_rhs)
        
        # Assert expectations
        self.assertTrue(actual)
        self.assertEqual(mock_cover_hash.call_count, 2)
        
    @patch('src.tags.Tags._hash_cover_image')
    def test_success_different_images(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison for images with different hashes returns True.'''
        # Set up mocks: two different hash return values
        mock_cover_hash.side_effect = [ImageHash(np.array([[0, 0, 0, 1]], dtype=np.bool_)),
                                       ImageHash(np.array([[1, 0, 0, 0]], dtype=np.bool_))]
        
        # Call target function
        tags_lhs = Tags()
        tags_rhs = Tags()
        actual = tags_lhs._eq_cover_image(tags_rhs)
        
        # Assert expectations
        self.assertFalse(actual)
        self.assertEqual(mock_cover_hash.call_count, 2)
    
    @patch('src.tags.Tags._hash_cover_image')
    def test_success_exists_vs_none(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison between Tags containing an image and Tags missing an image returns False.'''
        # Set up mocks: lhs exists, rhs None.
        mock_cover_hash.side_effect = [ImageHash(np.array([[0, 0, 0, 1]], dtype=np.bool_)),
                                       None]
        
        # Call target function
        tags_lhs = Tags()
        tags_rhs = Tags()
        actual = tags_lhs._eq_cover_image(tags_rhs)
        
        # Assert expectations
        self.assertFalse(actual)
        
    @patch('src.tags.Tags._hash_cover_image')
    def test_success_none_vs_exists(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison between Tags missing an image and Tags containing an image returns False.'''
        # Set up mocks: lhs None, rhs exists
        mock_cover_hash.side_effect = [None,
                                       ImageHash(np.array([[0, 0, 0, 1]], dtype=np.bool_))]
        
        # Call target function
        tags_lhs = Tags()
        tags_rhs = Tags()
        actual = tags_lhs._eq_cover_image(tags_rhs)
        
        # Assert expectations
        self.assertFalse(actual)
        
    @patch('src.tags.Tags._hash_cover_image')
    def test_success_none_vs_none(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison between two Tags instances missing an image returns True.'''
        # Set up mocks: both hashes as None
        mock_cover_hash.side_effect = [None, None]
        
        # Call target function
        tags_lhs = Tags()
        tags_rhs = Tags()
        actual = tags_lhs._eq_cover_image(tags_rhs)
        
        # Assert expectations
        self.assertTrue(actual)
    
    @patch('src.tags.Tags._hash_cover_image')
    def test_error_hash(self, mock_cover_hash: MagicMock) -> None:
        '''Tests that comparison resulting in a hash error raises a value error.'''
        # Set up mocks: hash exception
        mock_cover_hash.side_effect = ValueError()
        
        # Call target function, expecting exception and error log
        tags_lhs = Tags()
        tags_rhs = Tags()
        with self.assertRaises(ValueError):
            tags_lhs._eq_cover_image(tags_rhs)
        mock_cover_hash.assert_called()

