import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

from src import library
from src import constants

# Constants
TRACK_XML = '''
    <TRACK
        TrackID="1"
        Name="Test Track"
        Artist="MOCK_ARTIST"
        Album="MOCK_ALBUM"
        DateAdded="2020-02-03"
        Location="file://localhost/Users/user/Music/DJ/MOCK_FILE.aiff">
    </TRACK>
'''.strip()

COLLECTION_XML = f'''
    <?xml version="1.0" encoding="UTF-8"?>
    <COLLECTION Entries="1">
    {TRACK_XML}
    </COLLECTION>
'''.strip()

# Test classes
class TestGenerateDatePaths(unittest.TestCase):
    @patch('src.common.remove_subpath')
    @patch('src.common.find_date_context')
    @patch('src.library.full_path')
    @patch('src.library.swap_root')
    @patch('src.library.collection_path_to_syspath')
    def test_success_default_parameters(self,
                                        mock_collection_path_to_syspath: MagicMock,
                                        mock_swap_root: MagicMock,
                                        mock_full_path: MagicMock,
                                        mock_date_context: MagicMock,
                                        mock_remove_subpath: MagicMock) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when called with only the required positional arguments.
        '''
        # Set up mocks
        mock_collection_path_to_syspath.return_value = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'
        mock_swap_root.return_value = '/mock/root/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'
        mock_date_context.return_value = ('2020/02 february/03', 5)
        mock_remove_subpath.return_value = '/mock/root/2020/02 february/03/MOCK_FILE.aiff'
        
        # Set up input
        collection = ET.fromstring(COLLECTION_XML)
        
        # Call test function
        actual = library.generate_date_paths(collection, '/mock/root/')
        
        # Assert expectations
        # Output
        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        
        # Dependency calls
        mock_collection_path_to_syspath.assert_called()
        mock_full_path.assert_called_once()
        mock_date_context.assert_called_once()
        mock_remove_subpath.assert_called_once()
    
    @patch('src.common.remove_subpath')
    @patch('src.common.find_date_context')
    @patch('src.library.full_path')
    @patch('src.library.swap_root')
    @patch('src.library.collection_path_to_syspath')
    def test_success_metadata_path(self,
                                   mock_collection_path_to_syspath: MagicMock,
                                   mock_swap_root: MagicMock,
                                   mock_full_path: MagicMock,
                                   mock_date_context: MagicMock,
                                   mock_remove_subpath: MagicMock) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when called with the include metadata in path parameter.
        '''
        # Set up mocks
        mock_collection_path_to_syspath.return_value = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'
        mock_swap_root.return_value = '/mock/root/Music/DJ/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'
        mock_date_context.return_value = ('2020/02 february/03', 5)
        mock_remove_subpath.return_value = '/mock/root/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'
        
        # Set up input
        collection = ET.fromstring(COLLECTION_XML)
        
        # Call test function
        actual = library.generate_date_paths(collection, '/mock/root/', metadata_path=True)
        
        # Assert expectations
        # Output
        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        
        # Dependency calls
        mock_collection_path_to_syspath.assert_called()
        mock_full_path.assert_called_once()
        mock_date_context.assert_called_once()
        mock_remove_subpath.assert_called_once()
        
    @patch('src.common.remove_subpath')
    @patch('src.common.find_date_context')
    @patch('src.library.full_path')
    @patch('src.library.swap_root')
    @patch('src.library.collection_path_to_syspath')
    def test_success_playlist_ids_include(self,
                                          mock_collection_path_to_syspath: MagicMock,
                                          mock_swap_root: MagicMock,
                                          mock_full_path: MagicMock,
                                          mock_date_context: MagicMock,
                                          mock_remove_subpath: MagicMock) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when the collection includes the playlist ID in the given set.
        '''
        # Set up mocks
        mock_collection_path_to_syspath.return_value = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'
        mock_swap_root.return_value = '/mock/root/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'
        mock_date_context.return_value = ('2020/02 february/03', 5)
        mock_remove_subpath.return_value = '/mock/root/2020/02 february/03/MOCK_FILE.aiff'
        
        # Set up input
        collection = ET.fromstring(COLLECTION_XML)
        
        # Call test function
        actual = library.generate_date_paths(collection, '/mock/root/', playlist_ids={'1'})
        
        # Assert expectations
        # Output
        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        
        # Dependency calls
        mock_collection_path_to_syspath.assert_called()
        mock_full_path.assert_called_once()
        mock_date_context.assert_called_once()
        mock_remove_subpath.assert_called_once()
        
    @patch('src.common.remove_subpath')
    @patch('src.common.find_date_context')
    @patch('src.library.full_path')
    @patch('src.library.swap_root')
    @patch('src.library.collection_path_to_syspath')
    def test_success_playlist_ids_exclude(self,
                                          mock_collection_path_to_syspath: MagicMock,
                                          mock_swap_root: MagicMock,
                                          mock_full_path: MagicMock,
                                          mock_date_context: MagicMock,
                                          mock_remove_subpath: MagicMock) -> None:
        '''Tests that a collection with a single track yields an empty path mapping
        when the collection does NOT include the playlist ID in the given set.
        '''
        # Set up mocks
        mock_collection_path_to_syspath.return_value = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        
        # Set up input
        collection = ET.fromstring(COLLECTION_XML)
        
        # Call test function
        actual = library.generate_date_paths(collection, '/mock/root/', playlist_ids={'MOCK_ID_TO_SKIP'})
        
        # Assert expectations
        # Output
        expected = []
        self.assertEqual(actual, expected)
        
        # Dependency calls - only one call expected, the others should be skipped
        mock_collection_path_to_syspath.assert_called_once()
        mock_full_path.assert_not_called()
        mock_date_context.assert_not_called()
        mock_remove_subpath.assert_not_called()

class TestFullPath(unittest.TestCase):
    @patch('src.library.date_path')
    def test_success_default_parameters(self, mock_date_path: MagicMock) -> None:
        '''Tests for expected output with only required positional arguments provided.'''
        # Set up input
        node = ET.fromstring(TRACK_XML)
        
        # Set up mocks
        mock_date_path.return_value = '2020/02 february/03'
        
        # Call test function
        actual = library.full_path(node, constants.REKORDBOX_ROOT, constants.MAPPING_MONTH)
        
        # Assert expectations
        expected = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'
        self.assertEqual(actual, expected)
        
    @patch('src.library.date_path')
    def test_success_include_metadata(self, mock_date_path: MagicMock) -> None:
        '''Tests for expected output with metadata included paramter.'''
        # Set up input
        node = ET.fromstring(TRACK_XML)
        
        # Set up mocks
        mock_date_path.return_value = '2020/02 february/03'
        
        # Call test function
        actual = library.full_path(node, constants.REKORDBOX_ROOT, constants.MAPPING_MONTH, include_metadata=True)
        
        # Assert expectations
        expected = '/Users/user/Music/DJ/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'
        self.assertEqual(actual, expected)

class TestCollectionPathToSyspath(unittest.TestCase):
    def test_success_simple_path(self) -> None:
        '''Tests that the Collection XML Location path format is correctly converted into system format
        when the path contains no URL-encoded characters.'''
        # Set up input
        path = 'file://localhost/Users/user/Music/DJ/MOCK_FILE.aiff'
        
        # Call test function
        actual = library.collection_path_to_syspath(path)
        
        # Assert expectations
        expected = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        self.assertEqual(actual, expected)
        
    def test_success_complex_path(self) -> None:
        '''Tests that the Collection XML Location path format is correctly converted into system format
        when the path contains URL-encoded characters.'''
        # Set up input
        path = 'file://localhost/Users/user/Music/DJ/MOCK%20-%20COMPLEX_PATH.aiff'
        
        # Call test function
        actual = library.collection_path_to_syspath(path)
        
        # Assert expectations
        expected = '/Users/user/Music/DJ/MOCK - COMPLEX_PATH.aiff'
        self.assertEqual(actual, expected)

# Constants: filter path mappings
## track XML with a simple, non-encoded location
TRACK_XML_PLAYLIST_SIMPLE = '''
    <TRACK
        TrackID="1"
        Name="Test Track"
        Artist="MOCK_ARTIST"
        Album="MOCK_ALBUM"
        DateAdded="2020-02-03"
        Location="file://localhost/Users/user/Music/DJ/MOCK_PLAYLIST_FILE.aiff">
    </TRACK>
'''.strip()

## track XML with a URL-encoded location
TRACK_XML_PLAYLIST_ENCODED = '''
    <TRACK
        TrackID="2"
        Name="Test Track"
        Artist="MOCK_ARTIST"
        Album="MOCK_ALBUM"
        DateAdded="2020-02-03"
        Location="file://localhost/Users/user/Music/DJ/haircuts%20for%20men%20-%20%e8%8a%b1%e3%81%a8%e9%b3%a5%e3%81%a8%e5%b1%b1.aiff">
    </TRACK>
'''.strip()

## track XML not present in playlist
TRACK_XML_COLLECTION = '''
    <TRACK
        TrackID="3"
        Name="Test Track"
        Artist="MOCK_ARTIST"
        Album="MOCK_ALBUM"
        DateAdded="2020-02-03"
        Location="file://localhost/Users/user/Music/DJ/MOCK_COLLECTION_FILE.aiff">
    </TRACK>
'''.strip()

# collection XML that contains 2 tracks present in the '_pruned' playlist, and 1 track that only exists in the collection
DJ_PLAYLISTS_XML = f'''
<?xml version="1.0" encoding="UTF-8"?>

<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="3">
    {TRACK_XML_COLLECTION}
    {TRACK_XML_PLAYLIST_SIMPLE}
    {TRACK_XML_PLAYLIST_ENCODED}
    </COLLECTION>
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="2">
            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="_pruned" Type="1" KeyType="0" Entries="2">
            <TRACK Key="1"/>
            <TRACK Key="2"/>
            </NODE>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>
'''.strip()

class TestFilterPathMappings(unittest.TestCase):
    def test_success_mappings_simple(self) -> None:
        '''Tests that the given simple mapping passes through the filter.'''
        
        # Call target function
        mappings = [
            # playlist file: simple
            ('/Users/user/Music/DJ/MOCK_PLAYLIST_FILE.aiff', '/mock/output/MOCK_PLAYLIST_FILE.mp3'),
        ]
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations
        self.assertEqual(actual, mappings)
        
    def test_success_mappings_special_characters(self) -> None:
        '''Tests that the given special character mapping passes through the filter.'''
        
        # Call target function
        mappings = [
            # playlist file: non-standard characters
            ('/Users/user/Music/DJ/haircuts for men - 花と鳥と山.aiff', '/mock/output/haircuts for men - 花と鳥と山.mp3'),
        ]
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations
        self.assertEqual(actual, mappings)
        
    def test_success_mappings_non_playlist_file(self) -> None:
        '''Tests that the given non-playlist file does not pass through the filter.'''
        
        # Call target function
        mappings = [            
            # non-playlist collection file
            ('/Users/user/Music/DJ/MOCK_COLLECTION_FILE.aiff', '/mock/output/MOCK_COLLECTION_FILE.mp3'),
        ]
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations
        self.assertEqual(len(actual), 0)
    
    def test_success_empty_playlist(self) -> None:
        '''Tests that no mappings are filtered for a collection with an empty playlist.'''
        # Prepare input
        ## Create the collection XML with no playlist elements
        COLLECTION_XML_EMPTY_PLAYLIST = f'''
            <?xml version="1.0" encoding="UTF-8"?>

            <DJ_PLAYLISTS Version="1.0.0">
                <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
                <COLLECTION Entries="1">
                {TRACK_XML_COLLECTION}
                {TRACK_XML_PLAYLIST_SIMPLE}
                </COLLECTION>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT" Count="2">
                        <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                        <NODE Name="_pruned" Type="1" KeyType="0" Entries="1">
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
            '''.strip()
        ## Include some collection mappings
        mappings = [
            # playlist file: simple
            ('/Users/user/Music/DJ/MOCK_FILE.aiff', '/mock/output/MOCK_FILE.mp3'),
            
            # non-playlist collection file
            ('/Users/user/Music/DJ/MOCK_COLLECTION_FILE.aiff', '/mock/output/MOCK_COLLECTION_FILE.mp3'),
        ]
        collection = ET.fromstring(COLLECTION_XML_EMPTY_PLAYLIST)
        
        # Call target function
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations: no mappings should return for an empty playlist
        self.assertEqual(len(actual), 0)
    
    def test_success_empty_mapping_input(self) -> None:
        '''Tests that an empty mapping input returns an empty list.'''
        # Prepare input
        mappings = []
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        
        # Call target function
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations: no mappings should return for an empty mappings input
        self.assertEqual(len(actual), 0)
    
    def test_success_invalid_playlist(self) -> None:
        # Prepare input
        mappings = [
            # playlist file: simple
            ('/Users/user/Music/DJ/MOCK_FILE.aiff', '/mock/output/MOCK_FILE.mp3'),
            
            # non-playlist collection file
            ('/Users/user/Music/DJ/MOCK_COLLECTION_FILE.aiff', '/mock/output/MOCK_COLLECTION_FILE.mp3'),
        ]
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        
        # Call target function
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations: no mappings should return for an invalid playlist
        self.assertEqual(len(actual), 0)

class TestLibraryCollectIdentifiers(unittest.TestCase):
    '''Tests for library.collect_identifiers.'''
    
    @patch('src.tags.Tags.load')
    @patch('src.library.collection_path_to_syspath')
    def test_success_no_filter(self,
                               mock_to_syspath: MagicMock,
                               mock_tags_load: MagicMock) -> None:
        '''Tests that the identifiers are loaded from the given collection XML with no playlist filter.'''
        # Set up mocks
        mock_identifier = 'mock_identifier'
        mock_tags = MagicMock()
        mock_tags.basic_identifier.return_value = mock_identifier
        mock_tags_load.return_value = mock_tags
        
        # Call target function
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection)
        
        # Assert expectations
        self.assertEqual(actual, [mock_identifier])
        mock_to_syspath.assert_called_once()
        
    @patch('src.tags.Tags.load')
    @patch('src.library.collection_path_to_syspath')
    def test_success_filter_included(self,
                                     mock_to_syspath: MagicMock,
                                     mock_tags_load: MagicMock) -> None:
        '''Tests that the identifiers are loaded from the given collection XML with a matching playlist filter.'''
        # Set up mocks
        mock_identifier = 'mock_identifier'
        mock_tags = MagicMock()
        mock_tags.basic_identifier.return_value = mock_identifier
        mock_tags_load.return_value = mock_tags
        
        # Call target function
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection, {'1'})
        
        # Assert expectations
        self.assertEqual(actual, [mock_identifier])
        mock_to_syspath.assert_called_once()
        
    @patch('src.tags.Tags.load')
    @patch('src.library.collection_path_to_syspath')
    def test_success_filter_excluded(self,
                                     mock_to_syspath: MagicMock,
                                     mock_tags_load: MagicMock) -> None:
        '''Tests that no identifiers are loaded from the given collection XML with a non-matching playlist filter.'''
        # Set up mocks
        mock_identifier = 'mock_identifier'
        mock_tags = MagicMock()
        mock_tags.basic_identifier.return_value = mock_identifier
        mock_tags_load.return_value = mock_tags
        
        # Call target function
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection, {'mock_exclude_id'})
        
        # Assert expectations
        self.assertEqual(len(actual), 0)
        mock_to_syspath.assert_called_once()
    
    @patch('logging.error')
    @patch('src.tags.Tags.load')
    @patch('src.library.collection_path_to_syspath')
    def test_error_tags_load(self,
                             mock_to_syspath: MagicMock,
                             mock_tags_load: MagicMock,
                             mock_log_error: MagicMock) -> None:
        '''Tests that the identifiers are not loaded from the given collection XML when the track tags can't load.'''
        # Set up mocks
        mock_tags_load.return_value = None
        
        # Call target function
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection)
        
        # Assert expectations
        self.assertEqual(len(actual), 0)
        mock_to_syspath.assert_called_once()
        mock_log_error.assert_called_once()
