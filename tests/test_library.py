import unittest
import os
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

from djmgmt import library
from djmgmt import constants

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

MOCK_INPUT_DIR  = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'

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
        self.assertTrue(os.path.exists(constants.COLLECTION_TEMPLATE_PATH),
                       f"Template file not found at {constants.COLLECTION_TEMPLATE_PATH}")

    def test_template_structure_valid(self) -> None:
        '''Tests that the template file has the expected structure for dynamic playlists.'''
        # Load the template file
        tree = ET.parse(constants.COLLECTION_TEMPLATE_PATH)
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
        template_tree = ET.parse(constants.COLLECTION_TEMPLATE_PATH)
        base_root = template_tree.getroot()

        # Call target function
        track_ids = ['0', '2']
        result = library.record_tracks(base_root, track_ids, constants.XPATH_UNPLAYED)

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
        template_tree = ET.parse(constants.COLLECTION_TEMPLATE_PATH)
        base_root = template_tree.getroot()

        # Call target function
        track_ids = ['1']
        result = library.record_tracks(base_root, track_ids, constants.XPATH_PLAYED)

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

    @patch('djmgmt.library.record_tracks')
    @patch('djmgmt.library.get_unplayed_tracks')
    def test_success(self,
                     mock_get_unplayed: MagicMock,
                     mock_record_tracks: MagicMock) -> None:
        '''Tests that record_unplayed_tracks correctly delegates to record_tracks.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_get_unplayed.return_value = ['1', '3', '5']
        mock_record_tracks.return_value = MagicMock()

        # Call target function
        result = library.record_unplayed_tracks(mock_collection_root, mock_base_root)

        # Assert expectations
        mock_get_unplayed.assert_called_once_with(mock_collection_root)
        mock_record_tracks.assert_called_once_with(
            mock_base_root,
            ['1', '3', '5'],
            constants.XPATH_UNPLAYED
        )
        self.assertEqual(result, mock_record_tracks.return_value)

class TestRecordPlayedTracks(unittest.TestCase):
    '''Tests for library.record_played_tracks.'''

    @patch('djmgmt.library.record_tracks')
    @patch('djmgmt.library.get_played_tracks')
    def test_success(self,
                     mock_get_played: MagicMock,
                     mock_record_tracks: MagicMock) -> None:
        '''Tests that record_played_tracks correctly delegates to record_tracks.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_get_played.return_value = ['2', '4', '6']
        mock_record_tracks.return_value = MagicMock()

        # Call target function
        result = library.record_played_tracks(mock_collection_root, mock_base_root)

        # Assert expectations
        mock_get_played.assert_called_once_with(mock_collection_root)
        mock_record_tracks.assert_called_once_with(
            mock_base_root,
            ['2', '4', '6'],
            constants.XPATH_PLAYED
        )
        self.assertEqual(result, mock_record_tracks.return_value)

class TestRecordDynamicTracks(unittest.TestCase):
    '''Tests for library.record_dynamic_tracks.'''

    @patch.object(ET.ElementTree, 'write')
    @patch('djmgmt.library.record_unplayed_tracks')
    @patch('djmgmt.library.record_played_tracks')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.library.load_collection')
    def test_success(self,
                     mock_load_collection: MagicMock,
                     mock_find_node: MagicMock,
                     mock_record_played: MagicMock,
                     mock_record_unplayed: MagicMock,
                     mock_xml_write: MagicMock) -> None:
        '''Tests that record_dynamic_tracks loads roots, copies collection, calls both functions, and writes output.'''
        # Set up mocks
        mock_collection_root = MagicMock()
        mock_base_root = MagicMock()
        mock_collection = MagicMock()
        mock_base_collection = MagicMock()

        mock_load_collection.side_effect = [mock_collection_root, mock_base_root]
        mock_find_node.side_effect = [mock_base_collection, mock_collection]
        mock_record_played.return_value = mock_base_root
        mock_record_unplayed.return_value = mock_base_root

        # Call target function
        result = library.record_dynamic_tracks(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        mock_load_collection.assert_any_call(MOCK_INPUT_DIR)
        mock_load_collection.assert_any_call(constants.COLLECTION_TEMPLATE_PATH)

        # Verify collection was copied
        mock_base_collection.clear.assert_called_once()

        mock_record_played.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_record_unplayed.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_xml_write.assert_called_once_with(MOCK_OUTPUT_DIR, encoding='UTF-8', xml_declaration=True)
        self.assertEqual(result, mock_base_root)
