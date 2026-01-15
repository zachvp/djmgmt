import unittest
import os
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call
from typing import cast

from djmgmt import library
from djmgmt import constants
from djmgmt.tags import Tags

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

XML_BASE = f'''
<?xml version="1.0" encoding="UTF-8"?>

<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="0">
    
    </COLLECTION>
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="2">
            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>
'''.strip()

MOCK_INPUT_DIR       = '/mock/input'
MOCK_OUTPUT_DIR      = '/mock/output'
MOCK_XML_INPUT_PATH  = '/mock/xml/file.xml'
MOCK_XML_OUTPUT_PATH = '/mock/xml/out.xml'
MOCK_ARTIST          = 'mock_artist'
MOCK_ALBUM           = 'mock_album'
MOCK_TITLE           = 'mock_title'
MOCK_GENRE           = 'mock_genre'
MOCK_TONALITY        = 'mock_tonality'
MOCK_DATE_ADDED      = 'mock_date_added'

# Generation functions
def _create_track_xml(index: int) -> str:
    return f'''
        <TRACK
            TrackID="{index}"
            Name="Test Track {index}"
            Artist="MOCK_ARTIST_{index}"
            Album="MOCK_ALBUM_{index}"
            DateAdded="2020-02-03"
            Location="file://localhost/Users/user/Music/DJ/MOCK_FILE_{index}.aiff">
        </TRACK>
    '''.strip()

# Test classes
class TestGenerateDatePaths(unittest.TestCase):
    @patch('djmgmt.common.remove_subpath')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.full_path')
    @patch('djmgmt.library.swap_root')
    @patch('djmgmt.library.collection_path_to_syspath')
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
    
    @patch('djmgmt.common.remove_subpath')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.full_path')
    @patch('djmgmt.library.swap_root')
    @patch('djmgmt.library.collection_path_to_syspath')
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
        
    @patch('djmgmt.common.remove_subpath')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.full_path')
    @patch('djmgmt.library.swap_root')
    @patch('djmgmt.library.collection_path_to_syspath')
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
        
    @patch('djmgmt.common.remove_subpath')
    @patch('djmgmt.common.find_date_context')
    @patch('djmgmt.library.full_path')
    @patch('djmgmt.library.swap_root')
    @patch('djmgmt.library.collection_path_to_syspath')
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
    @patch('djmgmt.library.date_path')
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
        
    @patch('djmgmt.library.date_path')
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
    
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.library.collection_path_to_syspath')
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
        
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.library.collection_path_to_syspath')
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
        
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.library.collection_path_to_syspath')
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
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.library.collection_path_to_syspath')
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

class TestGetPlayedTracks(unittest.TestCase):
    XML_ARCHIVE = f'''
    <?xml version="1.0" encoding="UTF-8"?>

    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        <COLLECTION Entries="2">
            {_create_track_xml(0)}
            {_create_track_xml(1)}
        </COLLECTION>
        <PLAYLISTS>
            <NODE Type="0" Name="ROOT" Count="2">
                <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                <NODE Name="mixtapes" Type="0" KeyType="0" Entries="2">
                    <TRACK Key="0"/>
                    <NODE Name="playlist_0" Type="1" KeyType="0" Entries="1">
                        <TRACK Key="1"/>
                    </NODE>
                </NODE>
            </NODE>
        </PLAYLISTS>
    </DJ_PLAYLISTS>
    '''.strip()
    
    def test_success_exists(self) -> None:
        '''Tests that all tracks in the 'archive' folder are returned.'''
        # Call target function
        root = ET.fromstring(TestGetPlayedTracks.XML_ARCHIVE)
        actual = library.get_played_tracks(root)
        
        # Assert expectations
        self.assertEqual(actual, ['0', '1'])
    
    def test_success_deduplicate(self) -> None:
        '''Tests that only unique track IDs are returned.'''
        # Test data
        XML_DUPLICATES = f'''
        <?xml version="1.0" encoding="UTF-8"?>

        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="3">
                {_create_track_xml(0)}
                {_create_track_xml(1)}
            </COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="2">
                    <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                    <NODE Name="mixtapes" Type="0" KeyType="0" Entries="2">
                        <TRACK Key="0"/>
                        <NODE Name="playlist_0" Type="1" KeyType="0" Entries="2">
                            <TRACK Key="1"/>
                            <TRACK Key="0"/>
                        </NODE>
                        <TRACK Key="1"/>
                    </NODE>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()
        
        # Call target function
        root = ET.fromstring(XML_DUPLICATES)
        actual = library.get_played_tracks(root)
        
        # Assert expectations
        self.assertEqual(actual, ['0', '1'])

class TestGetUnplayedTracks(unittest.TestCase):
    XML_PRUNED = f'''
        <?xml version="1.0" encoding="UTF-8"?>

        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="0">
            
            </COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="2">
                    <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="0">
                        <TRACK Key="0"/>
                        <TRACK Key="1"/>
                    </NODE>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()
    
    @patch('djmgmt.library.get_played_tracks')
    def test_success(self,
                     mock_get_played: MagicMock) -> None:
        '''Tests that the function returns all unplayed tracks.'''
        # Set up mocks
        mock_root = ET.fromstring(TestGetUnplayedTracks.XML_PRUNED)
        mock_get_played.return_value = ['0', '2']
        
        actual = library.get_unplayed_tracks(mock_root)
        
        # Assert expectations
        self.assertEqual(actual, ['1'])

class TestCollectionTemplate(unittest.TestCase):
    '''Tests for the collection-template.xml file structure.'''

    def test_template_file_exists(self) -> None:
        '''Tests that the collection template file exists at the expected path.'''
        self.assertTrue(os.path.exists(constants.COLLECTION_PATH_TEMPLATE),
                       f"Template file not found at {constants.COLLECTION_PATH_TEMPLATE}")

    def test_template_structure_valid(self) -> None:
        '''Tests that the template file has the expected structure for dynamic playlists.'''
        # Load the template file
        tree = ET.parse(constants.COLLECTION_PATH_TEMPLATE)
        root = tree.getroot()

        # Verify root structure
        self.assertEqual(root.tag, 'DJ_PLAYLISTS')
        self.assertEqual(root.get('Version'), '1.0.0')

        # Verify COLLECTION exists and is empty
        collection = root.find(constants.XPATH_COLLECTION)
        self.assertIsNotNone(collection, "COLLECTION node not found")
        assert collection is not None
        self.assertEqual(collection.get('Entries'), '0')
        collection_tracks = collection.findall('.//TRACK')
        self.assertEqual(len(collection_tracks), 0, "COLLECTION should be empty")

        # Verify PLAYLISTS structure
        playlists_root = root.find(constants.XPATH_PLAYLISTS)
        assert playlists_root is not None
        self.assertIsNotNone(playlists_root, "PLAYLISTS ROOT node not found")

        # Count child nodes of ROOT
        root_children = playlists_root.findall('./NODE')
        assert root_children is not None
        self.assertEqual(len(root_children), 3, "ROOT should have 3 child nodes")
        self.assertEqual(playlists_root.get('Count'), '3', "ROOT Count attribute should be 3")

        # Verify _pruned playlist exists
        pruned = root.find(constants.XPATH_PRUNED)
        self.assertIsNotNone(pruned, "_pruned playlist not found")
        assert pruned is not None
        self.assertEqual(pruned.get('Type'), '1')
        self.assertEqual(pruned.get('Entries'), '0')

        # Verify dynamic folder exists
        dynamic = playlists_root.find(".//NODE[@Name='dynamic']")
        self.assertIsNotNone(dynamic, "dynamic folder not found")
        assert dynamic is not None
        self.assertEqual(dynamic.get('Type'), '0', "dynamic should be a folder (Type=0)")

        # Count child nodes of dynamic
        dynamic_children = dynamic.findall('./NODE')
        self.assertEqual(len(dynamic_children), 2, "dynamic should have 2 child nodes")
        self.assertEqual(dynamic.get('Entries'), '2', "dynamic Entries attribute should be 2")

        # Verify unplayed playlist exists
        unplayed = root.find(constants.XPATH_UNPLAYED)
        self.assertIsNotNone(unplayed, "unplayed playlist not found")
        assert unplayed is not None
        self.assertEqual(unplayed.get('Type'), '1', "unplayed should be a playlist (Type=1)")
        self.assertEqual(unplayed.get('Entries'), '0', "unplayed should be empty")
        unplayed_tracks = unplayed.findall('.//TRACK')
        self.assertEqual(len(unplayed_tracks), 0, "unplayed should have no tracks")

        # Verify played playlist exists
        played = root.find(constants.XPATH_PLAYED)
        self.assertIsNotNone(played, "played playlist not found")
        assert played is not None
        self.assertEqual(played.get('Type'), '1', "played should be a playlist (Type=1)")
        self.assertEqual(played.get('Entries'), '0', "played should be empty")
        played_tracks = played.findall('.//TRACK')
        self.assertEqual(len(played_tracks), 0, "played should have no tracks")

class TestRecordTracks(unittest.TestCase):
    '''Tests for library.record_tracks - the shared function for recording playlists.'''

    XML_INPUT = f'''
    <?xml version="1.0" encoding="UTF-8"?>

    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        <COLLECTION Entries="3">
            {_create_track_xml(0)}
            {_create_track_xml(1)}
            {_create_track_xml(2)}
        </COLLECTION>
        <PLAYLISTS>
            <NODE Type="0" Name="ROOT" Count="2">
                <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                <NODE Name="_pruned" Type="1" KeyType="0" Entries="3">
                    <TRACK Key="0"/>
                    <TRACK Key="1"/>
                    <TRACK Key="2"/>
                </NODE>
            </NODE>
        </PLAYLISTS>
    </DJ_PLAYLISTS>
    '''.strip()

    def test_success_unplayed_playlist(self) -> None:
        '''Tests that tracks are correctly written to the unplayed playlist.'''
        # Set up - use actual template file
        template_tree = ET.parse(constants.COLLECTION_PATH_TEMPLATE)
        base_root = template_tree.getroot()

        # Call target function
        track_ids = ['0', '2']
        result = library.add_playlist_tracks(base_root, track_ids, constants.XPATH_UNPLAYED)

        # Verify the unplayed playlist was populated
        unplayed_node = result.find(constants.XPATH_UNPLAYED)
        self.assertIsNotNone(unplayed_node)
        assert unplayed_node is not None
        self.assertEqual(unplayed_node.get('Entries'), '2')
        playlist_tracks = unplayed_node.findall('.//TRACK')
        self.assertEqual(len(playlist_tracks), 2)
        self.assertEqual(playlist_tracks[0].get('Key'), '0')
        self.assertEqual(playlist_tracks[1].get('Key'), '2')

    def test_success_played_playlist(self) -> None:
        '''Tests that tracks are correctly written to the played playlist.'''
        # Set up - use actual template file
        template_tree = ET.parse(constants.COLLECTION_PATH_TEMPLATE)
        base_root = template_tree.getroot()

        # Call target function
        track_ids = ['1']
        result = library.add_playlist_tracks(base_root, track_ids, constants.XPATH_PLAYED)

        # Verify the played playlist was populated
        played_node = result.find(constants.XPATH_PLAYED)
        self.assertIsNotNone(played_node)
        assert played_node is not None
        self.assertEqual(played_node.get('Entries'), '1')
        playlist_tracks = played_node.findall('.//TRACK')
        self.assertEqual(len(playlist_tracks), 1)
        self.assertEqual(playlist_tracks[0].get('Key'), '1')

class TestRecordUnplayedTracks(unittest.TestCase):
    '''Tests for library.record_unplayed_tracks.'''

    @patch('djmgmt.library.add_playlist_tracks')
    @patch('djmgmt.library.get_unplayed_tracks')
    def test_success(self,
                     mock_get_unplayed: MagicMock,
                     mock_add_playlist_tracks: MagicMock) -> None:
        '''Tests that record_unplayed_tracks correctly delegates to record_tracks.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_get_unplayed.return_value = ['1', '3', '5']
        mock_add_playlist_tracks.return_value = MagicMock()

        # Call target function
        result = library.add_unplayed_tracks(mock_collection_root, mock_base_root)

        # Assert expectations
        mock_get_unplayed.assert_called_once_with(mock_collection_root)
        mock_add_playlist_tracks.assert_called_once_with(
            mock_base_root,
            ['1', '3', '5'],
            constants.XPATH_UNPLAYED
        )
        self.assertEqual(result, mock_add_playlist_tracks.return_value)

class TestRecordPlayedTracks(unittest.TestCase):
    '''Tests for library.record_played_tracks.'''

    @patch('djmgmt.library.add_playlist_tracks')
    @patch('djmgmt.library.get_played_tracks')
    def test_success(self,
                     mock_get_played: MagicMock,
                     mock_add_playlist_tracks: MagicMock) -> None:
        '''Tests that record_played_tracks correctly delegates to record_tracks.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_get_played.return_value = ['2', '4', '6']
        mock_add_playlist_tracks.return_value = MagicMock()

        # Call target function
        result = library.add_played_tracks(mock_collection_root, mock_base_root)

        # Assert expectations
        mock_get_played.assert_called_once_with(mock_collection_root)
        mock_add_playlist_tracks.assert_called_once_with(
            mock_base_root,
            ['2', '4', '6'],
            constants.XPATH_PLAYED
        )
        self.assertEqual(result, mock_add_playlist_tracks.return_value)

class TestRecordDynamicTracks(unittest.TestCase):
    '''Tests for library.record_dynamic_tracks.'''

    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.add_unplayed_tracks')
    @patch('djmgmt.library.add_played_tracks')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.library.load_collection')
    def test_success(self,
                     mock_load_collection: MagicMock,
                     mock_find_node: MagicMock,
                     mock_add_played: MagicMock,
                     mock_add_unplayed: MagicMock,
                     mock_xml_write: MagicMock) -> None:
        '''Tests that record_dynamic_tracks loads roots, copies collection, calls both functions, and writes output.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_collection = MagicMock()
        mock_base_collection = MagicMock()

        mock_load_collection.side_effect = [mock_collection_root, mock_base_root]
        mock_find_node.side_effect = [mock_base_collection, mock_collection]
        mock_add_played.return_value = mock_base_root
        mock_add_unplayed.return_value = mock_base_root

        # Call target function
        result = library.record_dynamic_tracks(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        mock_load_collection.assert_any_call(MOCK_INPUT_DIR)
        mock_load_collection.assert_any_call(constants.COLLECTION_PATH_TEMPLATE)

        # Verify collection was copied
        mock_base_collection.clear.assert_called_once()

        mock_add_played.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_add_unplayed.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_xml_write.assert_called_once_with(MOCK_OUTPUT_DIR, encoding='UTF-8', xml_declaration=True)
        self.assertEqual(result, mock_base_root)

class TestRecordCollection(unittest.TestCase):
    '''Tests for library.record_collection.'''
    
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_new_collection_file(self,
                              mock_path_exists: MagicMock,
                              mock_collect_paths: MagicMock,
                              mock_tags_load: MagicMock,
                              mock_xml_parse: MagicMock,
                              mock_xml_write: MagicMock) -> None:
        '''Tests that a single music file is correctly written to a newly created XML collection.'''
        # Set up mocks
        MOCK_PARENT = f"{MOCK_INPUT_DIR}{os.sep}"
        mock_path_exists.side_effect = [False, True]
        mock_collect_paths.return_value = [f"{MOCK_PARENT}mock_file.aiff", f"{MOCK_PARENT}03 - 暴風一族 (Remix).mp3"]
        mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))
        
        # Call the target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert call expectations
        mock_xml_parse.assert_called_once_with(constants.COLLECTION_PATH_TEMPLATE)
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)

        # Assert that the function reads the file tags
        mock_tags_load.assert_has_calls([
            call(mock_collect_paths.return_value[0]),
            call(mock_collect_paths.return_value[1])
        ])

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root

        # Assert that the XML contents are expected
        # Check DJ_PLAYLISTS root node
        self.assertEqual(len(dj_playlists), 3)
        self.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
        self.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})
        
        # Check PRODUCT node
        product = dj_playlists[0]
        self.assertEqual(len(product), 0)
        expected_attrib = {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'}
        self.assertEqual(product.tag, 'PRODUCT')
        self.assertEqual(product.attrib, expected_attrib)
        
        # Check COLLECTION node
        collection = dj_playlists[1]
        self.assertEqual(collection.tag, 'COLLECTION')
        self.assertEqual(collection.attrib, {'Entries': '2'})
        self.assertEqual(len(collection), 2)
        
        # Check TRACK node base attributes
        for track in collection:
            self.assertEqual(track.tag, 'TRACK')
            self.assertEqual(len(track), 0)
            
            self.assertIn(constants.ATTR_TRACK_ID, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_TRACK_ID], r'\d+')
            
            self.assertIn(constants.ATTR_TITLE, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_TITLE], MOCK_TITLE)
            
            self.assertIn(constants.ATTR_ARTIST, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_ARTIST], MOCK_ARTIST)
            
            self.assertIn(constants.ATTR_ALBUM, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_ALBUM], MOCK_ALBUM)
            
            self.assertIn(constants.ATTR_DATE_ADDED, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_DATE_ADDED], r"\d{4}-\d{2}-\d{2}")
            
            self.assertIn(constants.ATTR_GENRE, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_GENRE], MOCK_GENRE)
            
            self.assertIn('Tonality', track.attrib)
            self.assertEqual(track.attrib['Tonality'], MOCK_TONALITY)
            
            self.assertIn(constants.ATTR_PATH, track.attrib)
            # Path content will be different per track, so check outside the loop
            
        # Check URL-encoded paths
        # Check track 0 path: no URL encoding required
        track_0 = collection[0]
        self.assertEqual(track_0.attrib[constants.ATTR_PATH], f"file://localhost{MOCK_INPUT_DIR}/mock_file.aiff")
        
        # Check track 1 path: URL encoding required
        track_1 = collection[1]
        self.assertIn(constants.ATTR_PATH, track_1.attrib)
        self.assertEqual(track_1.attrib[constants.ATTR_PATH].lower(),
                         f"file://localhost{MOCK_INPUT_DIR}/03%20-%20%E6%9A%B4%E9%A2%A8%E4%B8%80%E6%97%8F%20(Remix).mp3".lower())
        
        # Check PLAYLISTS node
        playlists = dj_playlists[2]
        self.assertEqual(len(playlists), 1) # Expect 1 'ROOT' Node
        
        # Check ROOT node
        playlist_root = playlists[0]
        self.assertEqual(playlist_root.tag, 'NODE')
        expected_attrib = {
            'Type' : '0',
            'Name' : 'ROOT',
            'Count': '2'
        }
        self.assertEqual(playlist_root.attrib, expected_attrib)
        
        # Expect 'CUE Analysis Playlist' and '_pruned' Nodes
        self.assertEqual(len(playlist_root), 2)
        
        # Check 'CUE Analysis Playlist' node
        cue_analysis = playlist_root[0]
        self.assertEqual(cue_analysis.tag, 'NODE')
        expected_attrib = {
            'Name'    : "CUE Analysis Playlist",
            'Type'    : "1",
            'KeyType' : "0",
            'Entries' : "0"
        }
        self.assertEqual(cue_analysis.attrib, expected_attrib)
        self.assertEqual(len(cue_analysis), 0) # expect no child nodes
        
        # Check '_pruned' playlist_root Node
        pruned = playlist_root[1]
        self.assertEqual(pruned.tag, 'NODE')
        self.assertIsNotNone(pruned)
        self.assertIn(constants.ATTR_TITLE, pruned.attrib)
        self.assertEqual(pruned.attrib[constants.ATTR_TITLE], '_pruned')
        self.assertEqual(len(pruned), 2)
        
        # Check '_pruned' track
        track = pruned[0]
        self.assertEqual(track.tag, 'TRACK')
        self.assertIn(constants.ATTR_TRACK_KEY, track.attrib)
        self.assertRegex(track.attrib[constants.ATTR_TRACK_KEY], r'\d+')

    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_collection_file_exists(self,
                                 mock_path_exists: MagicMock,
                                 mock_collect_paths: MagicMock,
                                 mock_tags_load: MagicMock,
                                 mock_xml_parse: MagicMock,
                                 mock_xml_write: MagicMock) -> None:
        '''Tests that a single music file is correctly added to an existing XML collection that contains an entry.'''
        # Set up mocks
        FILE_PATH_MUSIC = f"{MOCK_INPUT_DIR}{os.sep}"
        
        mock_path_exists.return_value = True
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}mock_file_0.aiff"]
        mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))
        
        # Insert the first track
        first_result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Reset mocks from first call
        mock_path_exists.reset_mock()
        mock_collect_paths.reset_mock()
        mock_tags_load.reset_mock()
        mock_xml_parse.reset_mock()
        mock_xml_write.reset_mock()
        
        # Set up mocks for second call
        mock_path_exists.return_value = True
        mock_collect_paths.return_value = [f"{FILE_PATH_MUSIC}mock_file_1.aiff", f"{FILE_PATH_MUSIC}03 - 暴風一族 (Remix).mp3"]
        mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        mock_xml_parse.return_value = ET.ElementTree(first_result.collection_root)

        # Call the target function to check that 'mock_file_1' was inserted
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root
            
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_parse.assert_called_with(MOCK_XML_INPUT_PATH)
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        
        # Assert that the function reads the file tags
        mock_tags_load.assert_has_calls([
            call(f"{FILE_PATH_MUSIC}mock_file_1.aiff"),
            call(f"{FILE_PATH_MUSIC}03 - 暴風一族 (Remix).mp3")
        ])
        
        # Assert that the XML contents are expected
        # Check DJ_PLAYLISTS root node
        self.assertEqual(len(dj_playlists), 3)
        self.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
        self.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})
        
        # Check PRODUCT node
        product = dj_playlists[0]
        expected_attrib = {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'}
        self.assertEqual(product.tag, 'PRODUCT')
        self.assertEqual(product.attrib, expected_attrib)
        
        # Check COLLECTION node
        collection = dj_playlists[1]
        self.assertEqual(collection.tag, 'COLLECTION')
        self.assertEqual(collection.attrib, {'Entries': '3'})
        self.assertEqual(len(collection), 3)
        
        # Check TRACK nodes
        for track in collection:
            self.assertEqual(track.tag, 'TRACK')
            self.assertEqual(len(track), 0)
            
            self.assertIn(constants.ATTR_TRACK_ID, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_TRACK_ID], r'\d+')
            
            self.assertIn(constants.ATTR_TITLE, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_TITLE], MOCK_TITLE)
            
            self.assertIn(constants.ATTR_ARTIST, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_ARTIST], MOCK_ARTIST)
            
            self.assertIn(constants.ATTR_ALBUM, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_ALBUM], MOCK_ALBUM)
            
            self.assertIn(constants.ATTR_DATE_ADDED, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_DATE_ADDED], r"\d{4}-\d{2}-\d{2}")
            
            self.assertIn(constants.ATTR_GENRE, track.attrib)
            self.assertEqual(track.attrib[constants.ATTR_GENRE], MOCK_GENRE)
            
            self.assertIn('Tonality', track.attrib)
            self.assertEqual(track.attrib['Tonality'], MOCK_TONALITY)
            
            self.assertIn(constants.ATTR_PATH, track.attrib)
            # Path content will be different per track, so check outside the loop
            
        # Check URL encoded paths
        # Track 0 is skipped, covered in new_file unit test
        # Check track 1 path: no URL encoding required
        track_1 = collection[1]
        self.assertEqual(track_1.attrib[constants.ATTR_PATH], f"file://localhost{MOCK_INPUT_DIR}/mock_file_1.aiff")
        
        # Check track 2 path: URL encoding required
        track_2 = collection[2]
        self.assertIn(constants.ATTR_PATH, track_2.attrib)
        self.assertEqual(track_2.attrib[constants.ATTR_PATH].lower(),
                         f"file://localhost{MOCK_INPUT_DIR}/03%20-%20%E6%9A%B4%E9%A2%A8%E4%B8%80%E6%97%8F%20(Remix).mp3".lower())
        
        # Check PLAYLISTS node
        playlists = dj_playlists[2]
        self.assertIsNotNone(playlists)
        self.assertEqual(len(playlists), 1) # Expect 1 'ROOT' Node
        
        # Check ROOT node
        playlist_root = playlists[0]
        expected_attrib = {
            'Type' : '0',
            'Name' : 'ROOT',
            'Count': '2'
        }
        self.assertEqual(playlist_root.attrib, expected_attrib)
        
        # Expect 'CUE Analysis Playlist' and '_pruned' Nodes
        self.assertEqual(len(playlist_root), 2)
        
        # Check 'CUE Analysis Playlist' node
        cue_analysis = playlist_root[0]
        self.assertEqual(cue_analysis.tag, 'NODE')
        self.assertEqual(playlist_root.tag, 'NODE')
        expected_attrib = {
            'Name'    : "CUE Analysis Playlist",
            'Type'    : "1",
            'KeyType' : "0",
            'Entries' : "0"
        }
        self.assertEqual(cue_analysis.attrib, expected_attrib)
        self.assertEqual(len(cue_analysis), 0) # expect no child nodes
        
        # CHECK '_pruned' playlist
        pruned = playlist_root[1]
        self.assertEqual(pruned.tag, 'NODE')
        self.assertIsNotNone(pruned)
        self.assertIn(constants.ATTR_TITLE, pruned.attrib)
        self.assertEqual(pruned.attrib[constants.ATTR_TITLE], '_pruned')
        self.assertEqual(len(pruned), 3)
        
        # Check '_pruned' tracks
        for track in pruned:
            self.assertEqual(track.tag, 'TRACK')
            self.assertIn(constants.ATTR_TRACK_KEY, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_TRACK_KEY], r'\d+')
            
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_track_exists_same_metadata(self,
                                                mock_path_exists: MagicMock,
                                                mock_collect_paths: MagicMock,
                                                mock_tags_load: MagicMock,
                                                mock_xml_parse: MagicMock,
                                                mock_xml_write: MagicMock) -> None:
        '''Tests that a track is not added to the collection XML if it already exists and the metadata is the same.'''
        # Setup mocks
        mock_file = 'mock_file.mp3'
        existing_track_xml = f'''
        <?xml version="1.0" encoding="UTF-8"?>

        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="1">
                <TRACK {constants.ATTR_TRACK_ID}="1"
                {constants.ATTR_TITLE}="{MOCK_TITLE}"
                {constants.ATTR_ARTIST}="{MOCK_ARTIST}"
                {constants.ATTR_ALBUM}="{MOCK_ALBUM}"
                {constants.ATTR_GENRE}="{MOCK_GENRE}"
                {constants.ATTR_KEY}="{MOCK_TONALITY}"
                {constants.ATTR_DATE_ADDED}="{MOCK_DATE_ADDED}"
                {constants.ATTR_PATH}="file://localhost{MOCK_INPUT_DIR}/{mock_file}" />
            </COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="2">
                    <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="1">
                        <TRACK Key="1" />
                    </NODE>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()
        
        mock_path_exists.return_value = True
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_file}"]
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(existing_track_xml))
        
        # Call target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 1)

        # Assert that the XML contents are the same as before attempting to add the track.
        self.assertEqual(ET.tostring(result.collection_root, encoding="UTF-8"),
                         ET.tostring(cast(ET.Element, mock_xml_parse.return_value.getroot()), encoding="UTF-8"))
            
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_track_exists_update_metadata(self,
                                                  mock_path_exists: MagicMock,
                                                  mock_collect_paths: MagicMock,
                                                  mock_tags_load: MagicMock,
                                                  mock_xml_parse: MagicMock,
                                                  mock_xml_write: MagicMock) -> None:
        '''Tests that the tag metadata is updated for an existing track.'''
        # Setup mocks
        mock_file = 'mock_file.mp3'
        existing_track_xml = f'''
        <?xml version="1.0" encoding="UTF-8"?>

        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="1">
                <TRACK {constants.ATTR_TRACK_ID}="1"
                {constants.ATTR_TITLE}="{MOCK_TITLE}"
                {constants.ATTR_ARTIST}="{MOCK_ARTIST}"
                {constants.ATTR_ALBUM}="{MOCK_ALBUM}"
                {constants.ATTR_GENRE}="{MOCK_GENRE}"
                {constants.ATTR_KEY}="{MOCK_TONALITY}"
                {constants.ATTR_DATE_ADDED}="{MOCK_DATE_ADDED}"
                {constants.ATTR_PATH}="file://localhost{MOCK_INPUT_DIR}/{mock_file}" />
            </COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="2">
                    <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="1">
                        <TRACK Key="1" />
                    </NODE>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()
        
        mock_path_exists.return_value = True
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_file}"]
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(existing_track_xml))
        
        # Mock updated tag metadata
        mock_tags_load.side_effect = [Tags(f"{MOCK_ARTIST}_update",
                                           f"{MOCK_ALBUM}_update",
                                           f"{MOCK_TITLE}_update",
                                           f"{MOCK_GENRE}_update",
                                           f"{MOCK_TONALITY}_update")]
        
        # Call target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 1)
        dj_playlists = result.collection_root

        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        # Assert the expected XML contents
        # Check DJ_PLAYLISTS root node
        self.assertEqual(len(dj_playlists), 3)
        self.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
        self.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})
        
        # Check PRODUCT node
        product = dj_playlists[0]
        self.assertEqual(len(product), 0)
        expected_attrib = {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'}
        self.assertEqual(product.tag, 'PRODUCT')
        self.assertEqual(product.attrib, expected_attrib)
        
        # Check COLLECTION node
        collection = dj_playlists[1]
        self.assertEqual(collection.tag, 'COLLECTION')
        self.assertEqual(collection.attrib, {'Entries': '1'})
        self.assertEqual(len(collection), 1)
        
        # Check the TRACK node
        track = collection[0]
        
        # Check data that should not change
        self.assertEqual(track.get(constants.ATTR_TRACK_ID), '1')
        self.assertEqual(track.get(constants.ATTR_DATE_ADDED), MOCK_DATE_ADDED)
        self.assertEqual(track.get(constants.ATTR_PATH), f"file://localhost{MOCK_INPUT_DIR}/{mock_file}")
        
        # Check the expected new data
        self.assertEqual(track.get(constants.ATTR_ARTIST), f"{MOCK_ARTIST}_update")
        self.assertEqual(track.get(constants.ATTR_ALBUM), f"{MOCK_ALBUM}_update")
        self.assertEqual(track.get(constants.ATTR_TITLE), f"{MOCK_TITLE}_update")
        self.assertEqual(track.get(constants.ATTR_GENRE), f"{MOCK_GENRE}_update")
        self.assertEqual(track.get('Tonality'), f"{MOCK_TONALITY}_update")
        
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_missing_metadata(self,
                                      mock_path_exists: MagicMock,
                                      mock_collect_paths: MagicMock,
                                      mock_tags_load: MagicMock,
                                      mock_xml_parse: MagicMock,
                                      mock_xml_write: MagicMock) -> None:
        '''Tests that empty metadata values are written for a track without any Tags metadata.'''
        # Set up mocks
        mock_path_exists.side_effect = [False, True]
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}mock_file.aiff"]
        mock_tags_load.return_value = Tags() # mock empty tag data
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))
        
        # Call the target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 1)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root

        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_parse.assert_called_once_with(constants.COLLECTION_PATH_TEMPLATE)
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)

        # Assert that the function reads the file tags
        FILE_PATH_MUSIC = f"{MOCK_INPUT_DIR}{os.sep}"
        mock_tags_load.assert_has_calls([
            call(f"{FILE_PATH_MUSIC}mock_file.aiff"),
        ])

        # Assert that the XML contents are expected
        # Check DJ_PLAYLISTS root node
        self.assertEqual(len(dj_playlists), 3)
        self.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
        self.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})
        
        # Check PRODUCT node
        product = dj_playlists[0]
        self.assertEqual(len(product), 0)
        expected_attrib = {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'}
        self.assertEqual(product.tag, 'PRODUCT')
        self.assertEqual(product.attrib, expected_attrib)
        
        # Check COLLECTION node
        collection = dj_playlists[1]
        self.assertEqual(collection.tag, 'COLLECTION')
        self.assertEqual(collection.attrib, {'Entries': '1'})
        self.assertEqual(len(collection), 1)
        
        # Check TRACK node base attributes
        ## Expect empty string values for tag metadata
        track = collection[0]
        self.assertEqual(track.tag, 'TRACK')
        self.assertEqual(len(track), 0)
        
        self.assertIn(constants.ATTR_TRACK_ID, track.attrib)
        self.assertRegex(track.attrib[constants.ATTR_TRACK_ID], r'\d+')
        
        self.assertIn(constants.ATTR_TITLE, track.attrib)
        self.assertEqual(track.attrib[constants.ATTR_TITLE], '')
        
        self.assertIn(constants.ATTR_ARTIST, track.attrib)
        self.assertEqual(track.attrib[constants.ATTR_ARTIST], '')
        
        self.assertIn(constants.ATTR_ALBUM, track.attrib)
        self.assertEqual(track.attrib[constants.ATTR_ALBUM], '')
        
        self.assertIn(constants.ATTR_DATE_ADDED, track.attrib)
        self.assertRegex(track.attrib[constants.ATTR_DATE_ADDED], r"\d{4}-\d{2}-\d{2}")
        
        self.assertIn(constants.ATTR_PATH, track.attrib)
        self.assertEqual(track.attrib[constants.ATTR_PATH], f"file://localhost{MOCK_INPUT_DIR}/mock_file.aiff")
        
        self.assertIn(constants.ATTR_GENRE, track.attrib)
        self.assertEqual(track.attrib[constants.ATTR_GENRE], '')
        
        self.assertIn('Tonality', track.attrib)
        self.assertEqual(track.attrib['Tonality'], '')

    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_no_music_files(self,
                                    mock_path_exists: MagicMock,
                                    mock_collect_paths: MagicMock,
                                    mock_tags_load: MagicMock,
                                    mock_xml_parse: MagicMock,
                                    mock_xml_write: MagicMock) -> None:
        '''Tests that the XML collection contains no Tracks when no music files are in the input directory.'''
        # Setup mocks
        mock_path_exists.side_effect = [False, True]
        mock_collect_paths.return_value = ['mock_file.foo']
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))
        
        # Call target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root

        # Assert call expectations: all files should be skipped
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_not_called()
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)

        # Empty playlist still expected to be written
        # Check root 'DJ_PLAYLISTS' node
        self.assertEqual(len(dj_playlists), 3)
        self.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
        self.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})
        self.assertEqual(len(dj_playlists), 3)
        
        # Check 'PRODUCT' node: same as normal
        product = dj_playlists[0]
        expected_attrib = {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'}
        self.assertEqual(product.tag, 'PRODUCT')
        self.assertEqual(product.attrib, expected_attrib)
        
        # Check 'COLLECTION' node: expect empty entries
        collection = dj_playlists[1]
        self.assertEqual(collection.tag, 'COLLECTION')
        self.assertEqual(collection.attrib, {'Entries': '0'})
        self.assertEqual(len(collection), 0)
        
        # Check 'PLAYLISTS' node: same as normal
        playlists = dj_playlists[2]
        self.assertEqual(len(playlists), 1) # Expect 1 'ROOT' Node
        
        # Check ROOT node
        playlist_root = playlists[0]
        self.assertEqual(playlist_root.tag, 'NODE')
        expected_attrib = {
            'Type' : '0',
            'Name' : 'ROOT',
            'Count': '2'
        }
        self.assertEqual(playlist_root.attrib, expected_attrib)
        
        # Expect 'CUE Analysis Playlist' and '_pruned' Nodes
        self.assertEqual(len(playlist_root), 2)
        
        # Check 'CUE Analysis Playlist' node
        cue_analysis = playlist_root[0]
        self.assertEqual(cue_analysis.tag, 'NODE')
        expected_attrib = {
            'Name'    : "CUE Analysis Playlist",
            'Type'    : "1",
            'KeyType' : "0",
            'Entries' : "0"
        }
        self.assertEqual(cue_analysis.attrib, expected_attrib)
        self.assertEqual(len(cue_analysis), 0) # expect no child nodes
        
        # Check '_pruned' playlist_root Node
        pruned = playlist_root[1]
        self.assertEqual(pruned.tag, 'NODE')
        self.assertIsNotNone(pruned)
        self.assertIn(constants.ATTR_TITLE, pruned.attrib)
        self.assertEqual(pruned.attrib[constants.ATTR_TITLE], '_pruned')
        
        # Check that '_pruned' contains no tracks
        self.assertEqual(len(pruned), 0)
        
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_success_unreadable_tags(self,
                                     mock_path_exists: MagicMock,
                                     mock_collect_paths: MagicMock,
                                     mock_tags_load: MagicMock,
                                     mock_xml_parse: MagicMock,
                                     mock_xml_write: MagicMock) -> None:
        '''Tests that a track is not added to the collection XML if its tags are invalid.'''
        # Setup mocks
        mock_bad_file = 'mock_bad_file.mp3'
        existing_track_xml = f'''
        <?xml version="1.0" encoding="UTF-8"?>

        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="1">
                <TRACK TrackID="1"
                Name="{MOCK_TITLE}"
                Artist="{MOCK_ARTIST}"
                Album="{MOCK_ALBUM}"
                DateAdded="2025-06-19"
                Location="file://localhost{MOCK_INPUT_DIR}/mock_existing_file.mp3" />
            </COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="2">
                    <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="1">
                        <TRACK Key="1" />
                    </NODE>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()
        
        mock_path_exists.return_value = True
        mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_bad_file}"]
        mock_tags_load.return_value = None # Mock tag reading failure
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(existing_track_xml))
        
        # Call target function
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert return value is RecordResult
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 0)
        actual = result.collection_root

        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_bad_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        # Assert that the XML contents are the same as before attempting to add the track.
        self.assertEqual(ET.tostring(actual, encoding="UTF-8"),
                         ET.tostring(mock_xml_parse.return_value, encoding="UTF-8"))
    
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_collection_exists_invalid_content(self,
                                               mock_path_exists: MagicMock,
                                               mock_collect_paths: MagicMock,
                                               mock_tags_load: MagicMock,
                                               mock_xml_parse: MagicMock,
                                               mock_xml_write: MagicMock) -> None:
        '''Tests that the expected exception is raised when the collection file is invalid.'''
        # Setup mocks
        mock_path_exists.return_value = True
        mock_exception_message = 'mock_parse_error'
        mock_xml_parse.side_effect = Exception(mock_exception_message) # mock a parsing error
        
        # Call target function and assert expectations
        with self.assertRaisesRegex(Exception, mock_exception_message):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)
            
        # Assert expectations: Code should only check that path exists and attempt to parse
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)
        mock_xml_write.assert_not_called()
        
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('os.path.exists')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    def test_collection_exists_missing_collection_tag(self,
                                                      mock_collect_paths: MagicMock,
                                                      mock_tags_load: MagicMock,
                                                      mock_path_exists: MagicMock,
                                                      mock_xml_parse: MagicMock,
                                                      mock_xml_write: MagicMock) -> None:
        '''Tests that the expected exception is raised when the collection file is missing a COLLECTION tag.'''
        # Setup mocks
        mock_path_exists.return_value = True
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring('<MOCK_NO_COLLECTION></MOCK_NO_COLLECTION>'))
        
        # Call target function and assert expectations
        with self.assertRaises(ValueError):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)
            
        # Assert expectations: Code should only check that path exists and attempt to parse
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)
        mock_xml_write.assert_not_called()
        
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_template_file_invalid(self,
                                   mock_path_exists: MagicMock,
                                   mock_collect_paths: MagicMock,
                                   mock_tags_load: MagicMock,
                                   mock_xml_parse: MagicMock,
                                   mock_xml_write: MagicMock) -> None:
        '''Tests that an exception is raised when the template file is not present.'''
        # Setup mocks
        mock_path_exists.return_value = False
        mock_xml_parse.side_effect = Exception() # mock a parsing error due to missing file
        
        # Call target function and assert expectations
        with self.assertRaises(Exception):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)
            
        # Assert expectations: nothing should be called
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_write.assert_not_called()

    @patch('djmgmt.common.log_dry_run')
    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.ET.parse')
    @patch('djmgmt.tags.Tags.load')
    @patch('djmgmt.common.collect_paths')
    @patch('os.path.exists')
    def test_dry_run(self,
                     mock_path_exists: MagicMock,
                     mock_collect_paths: MagicMock,
                     mock_tags_load: MagicMock,
                     mock_xml_parse: MagicMock,
                     mock_xml_write: MagicMock,
                     mock_log_dry_run: MagicMock) -> None:
        '''Test that dry_run=True skips XML write and logs the operation.'''
        # Set up mocks
        MOCK_PARENT = f"{MOCK_INPUT_DIR}{os.sep}"
        mock_path_exists.side_effect = [False, True]
        mock_collect_paths.return_value = [f"{MOCK_PARENT}track1.aiff", f"{MOCK_PARENT}track2.mp3"]
        mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))

        # Call the target function with dry_run=True
        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH, dry_run=True)

        # Assert XML write was NOT called in dry-run mode
        mock_xml_write.assert_not_called()

        # Assert dry-run log was called
        mock_log_dry_run.assert_called_once_with('write collection', MOCK_XML_INPUT_PATH)

        # Assert return value is RecordResult dataclass
        self.assertIsInstance(result, library.RecordResult)
        self.assertIsNotNone(result.collection_root)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)

        # Verify collection_root contains expected data
        collection = result.collection_root.find('.//COLLECTION')
        assert collection is not None
        self.assertEqual(len(collection.findall('TRACK')), 2)


class TestExtractTrackMetadata(unittest.TestCase):
    '''Tests for library.extract_track_metadata.'''

    def test_success(self) -> None:
        '''Tests that track metadata is extracted correctly from collection.'''
        # Setup XML
        collection_xml = '''
            <COLLECTION Entries="1">
                <TRACK
                    TrackID="1"
                    Name="Test Track"
                    Artist="Test Artist"
                    Album="Test Album"
                    Location="file://localhost/Users/user/Music/DJ/test.aiff">
                </TRACK>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)
        source_path = '/Users/user/Music/DJ/test.aiff'

        # Call function
        result = library.extract_track_metadata(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, 'Test Track')
        self.assertEqual(result.artist, 'Test Artist')
        self.assertEqual(result.album, 'Test Album')
        self.assertEqual(result.path, source_path)

    def test_track_not_found(self) -> None:
        '''Tests that None is returned when track is not found in collection.'''
        # Setup empty collection
        collection_xml = '<COLLECTION Entries="0"></COLLECTION>'
        collection = ET.fromstring(collection_xml)
        source_path = '/nonexistent/path.aiff'

        # Call function
        result = library.extract_track_metadata(collection, source_path)

        # Assertions
        self.assertIsNone(result)

    def test_missing_metadata_fields(self) -> None:
        '''Tests that empty strings are returned for missing metadata fields.'''
        # Setup XML with minimal attributes
        collection_xml = '''
            <COLLECTION Entries="1">
                <TRACK
                    TrackID="1"
                    Location="file://localhost/Users/user/Music/DJ/test.aiff">
                </TRACK>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)
        source_path = '/Users/user/Music/DJ/test.aiff'

        # Call function
        result = library.extract_track_metadata(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, '')
        self.assertEqual(result.artist, '')
        self.assertEqual(result.album, '')
        self.assertEqual(result.path, source_path)

    def test_url_encoded_path(self) -> None:
        '''Tests that URL-encoded characters in path are handled correctly.'''
        # Setup XML with URL-encoded path
        collection_xml = '''
            <COLLECTION Entries="1">
                <TRACK
                    TrackID="1"
                    Name="Test Track"
                    Artist="Test Artist"
                    Album="Test Album"
                    Location="file://localhost/Users/user/Music%20Library/test%20(mix).aiff">
                </TRACK>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)
        source_path = '/Users/user/Music Library/test (mix).aiff'

        # Call function
        result = library.extract_track_metadata(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, 'Test Track')
        self.assertEqual(result.path, source_path)


class TestBuildTrackIndex(unittest.TestCase):
    '''Tests for library._build_track_index.'''

    def test_success_single_track(self) -> None:
        '''Tests that a single track is indexed by its Location attribute.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="1">
                <TRACK
                    TrackID="1"
                    Name="Test Track"
                    Location="file://localhost/path/to/track.aiff">
                </TRACK>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn('file://localhost/path/to/track.aiff', result)
        self.assertEqual(result['file://localhost/path/to/track.aiff'].get('TrackID'), '1')

    def test_success_multiple_tracks(self) -> None:
        '''Tests that multiple tracks are indexed correctly.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="3">
                <TRACK TrackID="1" Name="Track 1" Location="file://localhost/path/track1.aiff"/>
                <TRACK TrackID="2" Name="Track 2" Location="file://localhost/path/track2.aiff"/>
                <TRACK TrackID="3" Name="Track 3" Location="file://localhost/path/track3.aiff"/>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result['file://localhost/path/track1.aiff'].get('TrackID'), '1')
        self.assertEqual(result['file://localhost/path/track2.aiff'].get('TrackID'), '2')
        self.assertEqual(result['file://localhost/path/track3.aiff'].get('TrackID'), '3')

    def test_success_empty_collection(self) -> None:
        '''Tests that an empty collection returns an empty index.'''
        # Setup
        collection_xml = '<COLLECTION Entries="0"></COLLECTION>'
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertDictEqual(result, {})

    def test_success_track_without_location(self) -> None:
        '''Tests that tracks without Location attribute are skipped.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="2">
                <TRACK TrackID="1" Name="Track With Location" Location="file://localhost/path/track.aiff"/>
                <TRACK TrackID="2" Name="Track Without Location"/>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn('file://localhost/path/track.aiff', result)


class TestMergeCollections(unittest.TestCase):
    '''Tests for library.merge_collections.'''

    # XML templates for testing
    XML_PRIMARY = '''
    <?xml version="1.0" encoding="UTF-8"?>
    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        <COLLECTION Entries="2">
            <TRACK TrackID="1" Name="Track A" Artist="Artist A" Location="file://localhost/path/trackA.aiff"/>
            <TRACK TrackID="2" Name="Track B" Artist="Artist B" Location="file://localhost/path/trackB.aiff"/>
        </COLLECTION>
        <PLAYLISTS>
            <NODE Type="0" Name="ROOT" Count="1">
                <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
            </NODE>
        </PLAYLISTS>
    </DJ_PLAYLISTS>
    '''.strip()

    XML_SECONDARY = '''
    <?xml version="1.0" encoding="UTF-8"?>
    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        <COLLECTION Entries="2">
            <TRACK TrackID="3" Name="Track C" Artist="Artist C" Location="file://localhost/path/trackC.aiff"/>
            <TRACK TrackID="4" Name="Track D" Artist="Artist D" Location="file://localhost/path/trackD.aiff"/>
        </COLLECTION>
        <PLAYLISTS>
            <NODE Type="0" Name="ROOT" Count="1">
                <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
            </NODE>
        </PLAYLISTS>
    </DJ_PLAYLISTS>
    '''.strip()

    XML_OVERLAPPING = '''
    <?xml version="1.0" encoding="UTF-8"?>
    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        <COLLECTION Entries="2">
            <TRACK TrackID="5" Name="Track A Updated" Artist="Artist A Updated" Location="file://localhost/path/trackA.aiff"/>
            <TRACK TrackID="6" Name="Track E" Artist="Artist E" Location="file://localhost/path/trackE.aiff"/>
        </COLLECTION>
        <PLAYLISTS>
            <NODE Type="0" Name="ROOT" Count="1">
                <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
            </NODE>
        </PLAYLISTS>
    </DJ_PLAYLISTS>
    '''.strip()

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_disjoint_collections(self,
                                          mock_getmtime: MagicMock,
                                          mock_load_collection: MagicMock) -> None:
        '''Tests merging two collections with no overlapping tracks.'''
        # Setup mocks
        mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_SECONDARY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [1000.0, 500.0]  # primary is newer

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 4)
        self.assertEqual(collection.get('Entries'), '4')

        # Verify all tracks are present
        locations = {track.get('Location') for track in tracks}
        self.assertIn('file://localhost/path/trackA.aiff', locations)
        self.assertIn('file://localhost/path/trackB.aiff', locations)
        self.assertIn('file://localhost/path/trackC.aiff', locations)
        self.assertIn('file://localhost/path/trackD.aiff', locations)

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_overlapping_newer_primary(self,
                                               mock_getmtime: MagicMock,
                                               mock_load_collection: MagicMock) -> None:
        '''Tests that overlapping tracks use metadata from newer file (primary).'''
        # Setup mocks
        mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_OVERLAPPING),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [1000.0, 500.0]  # primary is newer

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 3)  # trackA, trackB from primary + trackE from secondary

        # Verify trackA uses primary metadata (newer)
        track_a = None
        for track in tracks:
            if track.get('Location') == 'file://localhost/path/trackA.aiff':
                track_a = track
                break
        assert track_a is not None
        self.assertEqual(track_a.get('Name'), 'Track A')  # from primary (newer)
        self.assertEqual(track_a.get('Artist'), 'Artist A')  # from primary (newer)

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_overlapping_newer_secondary(self,
                                                 mock_getmtime: MagicMock,
                                                 mock_load_collection: MagicMock) -> None:
        '''Tests that overlapping tracks use metadata from newer file (secondary).'''
        # Setup mocks
        mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_OVERLAPPING),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [500.0, 1000.0]  # secondary is newer

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 3)  # trackA (updated), trackB, trackE

        # Verify trackA uses secondary metadata (newer)
        track_a = None
        for track in tracks:
            if track.get('Location') == 'file://localhost/path/trackA.aiff':
                track_a = track
                break
        assert track_a is not None
        self.assertEqual(track_a.get('Name'), 'Track A Updated')  # from secondary (newer)
        self.assertEqual(track_a.get('Artist'), 'Artist A Updated')  # from secondary (newer)

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_empty_primary(self,
                                   mock_getmtime: MagicMock,
                                   mock_load_collection: MagicMock) -> None:
        '''Tests merging when primary collection is empty.'''
        # Setup
        empty_xml = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="0"></COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="1">
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()

        mock_load_collection.side_effect = [
            ET.fromstring(empty_xml),
            ET.fromstring(TestMergeCollections.XML_SECONDARY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [1000.0, 500.0]

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 2)  # only secondary tracks
        self.assertEqual(collection.get('Entries'), '2')

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_empty_secondary(self,
                                     mock_getmtime: MagicMock,
                                     mock_load_collection: MagicMock) -> None:
        '''Tests merging when secondary collection is empty.'''
        # Setup
        empty_xml = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="0"></COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="1">
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()

        mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(empty_xml),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [1000.0, 500.0]

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 2)  # only primary tracks
        self.assertEqual(collection.get('Entries'), '2')

    @patch('djmgmt.library.load_collection')
    @patch('os.path.getmtime')
    def test_success_both_empty(self,
                                mock_getmtime: MagicMock,
                                mock_load_collection: MagicMock) -> None:
        '''Tests merging when both collections are empty.'''
        # Setup
        empty_xml = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <DJ_PLAYLISTS Version="1.0.0">
            <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
            <COLLECTION Entries="0"></COLLECTION>
            <PLAYLISTS>
                <NODE Type="0" Name="ROOT" Count="1">
                    <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
                </NODE>
            </PLAYLISTS>
        </DJ_PLAYLISTS>
        '''.strip()

        mock_load_collection.side_effect = [
            ET.fromstring(empty_xml),
            ET.fromstring(empty_xml),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        mock_getmtime.side_effect = [1000.0, 500.0]

        # Call function
        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        # Assertions
        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 0)
        self.assertEqual(collection.get('Entries'), '0')


class TestBuildTrackIdToLocation(unittest.TestCase):
    '''Tests for library._build_track_id_to_location.'''

    def test_success_single_track(self) -> None:
        '''Tests that a single track is mapped from TrackID to Location.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="1">
                <TRACK TrackID="123" Name="Test Track" Location="file://localhost/path/to/track.aiff"/>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result['123'], 'file://localhost/path/to/track.aiff')

    def test_success_multiple_tracks(self) -> None:
        '''Tests that multiple tracks are mapped correctly.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="3">
                <TRACK TrackID="1" Location="file://localhost/path/track1.aiff"/>
                <TRACK TrackID="2" Location="file://localhost/path/track2.aiff"/>
                <TRACK TrackID="3" Location="file://localhost/path/track3.aiff"/>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result['1'], 'file://localhost/path/track1.aiff')
        self.assertEqual(result['2'], 'file://localhost/path/track2.aiff')
        self.assertEqual(result['3'], 'file://localhost/path/track3.aiff')

    def test_success_empty_collection(self) -> None:
        '''Tests that an empty collection returns an empty mapping.'''
        # Setup
        collection_xml = '<COLLECTION Entries="0"></COLLECTION>'
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertDictEqual(result, {})

    def test_success_track_missing_id_or_location(self) -> None:
        '''Tests that tracks missing TrackID or Location are skipped.'''
        # Setup
        collection_xml = '''
            <COLLECTION Entries="3">
                <TRACK TrackID="1" Location="file://localhost/path/track1.aiff"/>
                <TRACK TrackID="2"/>
                <TRACK Location="file://localhost/path/track3.aiff"/>
            </COLLECTION>
        '''.strip()
        collection = ET.fromstring(collection_xml)

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result['1'], 'file://localhost/path/track1.aiff')


class TestGetPlaylistTrackKeys(unittest.TestCase):
    '''Tests for library._get_playlist_track_keys.'''

    def test_success_with_tracks(self) -> None:
        '''Tests extracting track keys from a playlist with tracks.'''
        # Setup
        root_xml = '''
            <DJ_PLAYLISTS>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="3">
                            <TRACK Key="1"/>
                            <TRACK Key="2"/>
                            <TRACK Key="3"/>
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()
        root = ET.fromstring(root_xml)

        # Call function
        result = library._get_playlist_track_keys(root, constants.XPATH_PRUNED)

        # Assertions
        self.assertSetEqual(result, {'1', '2', '3'})

    def test_success_empty_playlist(self) -> None:
        '''Tests extracting keys from an empty playlist.'''
        # Setup
        root_xml = '''
            <DJ_PLAYLISTS>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="0"/>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()
        root = ET.fromstring(root_xml)

        # Call function
        result = library._get_playlist_track_keys(root, constants.XPATH_PRUNED)

        # Assertions
        self.assertSetEqual(result, set())

    def test_success_playlist_not_found(self) -> None:
        '''Tests that missing playlist returns empty set.'''
        # Setup
        root_xml = '''
            <DJ_PLAYLISTS>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT"/>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()
        root = ET.fromstring(root_xml)

        # Call function
        result = library._get_playlist_track_keys(root, constants.XPATH_PRUNED)

        # Assertions
        self.assertSetEqual(result, set())


class TestMergePlaylistReferences(unittest.TestCase):
    '''Tests for library._merge_playlist_references.'''

    def test_success_disjoint_playlists(self) -> None:
        '''Tests merging playlists with no overlapping tracks.'''
        # Setup - primary has tracks 1,2; secondary has tracks 3,4
        primary_root_xml = '''
            <DJ_PLAYLISTS>
                <COLLECTION Entries="2">
                    <TRACK TrackID="1" Location="file://localhost/path/trackA.aiff"/>
                    <TRACK TrackID="2" Location="file://localhost/path/trackB.aiff"/>
                </COLLECTION>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="2">
                            <TRACK Key="1"/>
                            <TRACK Key="2"/>
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()
        secondary_root_xml = '''
            <DJ_PLAYLISTS>
                <COLLECTION Entries="2">
                    <TRACK TrackID="3" Location="file://localhost/path/trackC.aiff"/>
                    <TRACK TrackID="4" Location="file://localhost/path/trackD.aiff"/>
                </COLLECTION>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="2">
                            <TRACK Key="3"/>
                            <TRACK Key="4"/>
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()

        primary_root = ET.fromstring(primary_root_xml)
        secondary_root = ET.fromstring(secondary_root_xml)
        primary_collection = primary_root.find(constants.XPATH_COLLECTION)
        secondary_collection = secondary_root.find(constants.XPATH_COLLECTION)
        assert primary_collection is not None
        assert secondary_collection is not None

        # Build merged track index (simulating merge result)
        merged_track_index = {
            'file://localhost/path/trackA.aiff': ET.fromstring('<TRACK TrackID="1"/>'),
            'file://localhost/path/trackB.aiff': ET.fromstring('<TRACK TrackID="2"/>'),
            'file://localhost/path/trackC.aiff': ET.fromstring('<TRACK TrackID="3"/>'),
            'file://localhost/path/trackD.aiff': ET.fromstring('<TRACK TrackID="4"/>'),
        }

        # Call function
        result = library._merge_playlist_references(
            primary_root, secondary_root,
            primary_collection, secondary_collection,
            merged_track_index, constants.XPATH_PRUNED
        )

        # Assertions
        self.assertSetEqual(result, {'1', '2', '3', '4'})

    def test_success_overlapping_by_location(self) -> None:
        '''Tests that overlapping tracks (same location) are deduplicated.'''
        # Setup - both playlists reference trackA at same location but different IDs
        primary_root_xml = '''
            <DJ_PLAYLISTS>
                <COLLECTION Entries="1">
                    <TRACK TrackID="1" Location="file://localhost/path/trackA.aiff"/>
                </COLLECTION>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="1">
                            <TRACK Key="1"/>
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()
        secondary_root_xml = '''
            <DJ_PLAYLISTS>
                <COLLECTION Entries="1">
                    <TRACK TrackID="99" Location="file://localhost/path/trackA.aiff"/>
                </COLLECTION>
                <PLAYLISTS>
                    <NODE Type="0" Name="ROOT">
                        <NODE Name="_pruned" Type="1" Entries="1">
                            <TRACK Key="99"/>
                        </NODE>
                    </NODE>
                </PLAYLISTS>
            </DJ_PLAYLISTS>
        '''.strip()

        primary_root = ET.fromstring(primary_root_xml)
        secondary_root = ET.fromstring(secondary_root_xml)
        primary_collection = primary_root.find(constants.XPATH_COLLECTION)
        secondary_collection = secondary_root.find(constants.XPATH_COLLECTION)
        assert primary_collection is not None
        assert secondary_collection is not None

        # Merged track index has the winning track (e.g., from newer file)
        merged_track_index = {
            'file://localhost/path/trackA.aiff': ET.fromstring('<TRACK TrackID="99"/>'),
        }

        # Call function
        result = library._merge_playlist_references(
            primary_root, secondary_root,
            primary_collection, secondary_collection,
            merged_track_index, constants.XPATH_PRUNED
        )

        # Assertions - should have single track with merged ID
        self.assertSetEqual(result, {'99'})
