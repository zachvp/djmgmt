import unittest
import os
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call
from typing import cast

from djmgmt import library
from djmgmt import constants
from djmgmt.tags import Tags
from tests.fixtures import (
    MOCK_INPUT_DIR, MOCK_OUTPUT_DIR,
    TRACK_XML, COLLECTION_XML, XML_BASE,
    COLLECTION_XML_EMPTY,
    _create_track_xml,
    _build_collection_xml,
    _build_dj_playlists_xml,
)

# Constants specific to library tests
MOCK_XML_INPUT_PATH  = '/mock/xml/file.xml'
MOCK_XML_OUTPUT_PATH = '/mock/xml/out.xml'
MOCK_ARTIST          = 'mock_artist'
MOCK_ALBUM           = 'mock_album'
MOCK_TITLE           = 'mock_title'
MOCK_GENRE           = 'mock_genre'
MOCK_TONALITY        = 'mock_tonality'
MOCK_DATE_ADDED      = 'mock_date_added'


# Builder functions
def _build_single_track_collection_xml(mock_file: str) -> str:
    '''Builds a DJ_PLAYLISTS XML string with one existing track in COLLECTION and _pruned.
    Used by TestRecordCollection tests that need a pre-populated collection as mock input.
    '''
    track_xml = (f'<TRACK {constants.ATTR_TRACK_ID}="1"'
                 f' {constants.ATTR_TITLE}="{MOCK_TITLE}"'
                 f' {constants.ATTR_ARTIST}="{MOCK_ARTIST}"'
                 f' {constants.ATTR_ALBUM}="{MOCK_ALBUM}"'
                 f' {constants.ATTR_GENRE}="{MOCK_GENRE}"'
                 f' {constants.ATTR_KEY}="{MOCK_TONALITY}"'
                 f' {constants.ATTR_DATE_ADDED}="{MOCK_DATE_ADDED}"'
                 f' {constants.ATTR_LOCATION}="file://localhost{MOCK_INPUT_DIR}/{mock_file}" />')
    return _build_dj_playlists_xml([track_xml], ['1'])


# Assertion helpers
def _assert_dj_playlists_structure(test_case: unittest.TestCase,
                                    dj_playlists: ET.Element,
                                    expected_track_count: int) -> None:
    '''Asserts the standard DJ_PLAYLISTS wrapper structure produced by record_collection:
    PRODUCT node, COLLECTION with correct count, PLAYLISTS/ROOT/_pruned structure.
    '''
    test_case.assertEqual(len(dj_playlists), 3)
    test_case.assertEqual(dj_playlists.tag, 'DJ_PLAYLISTS')
    test_case.assertEqual(dj_playlists.attrib, {'Version': '1.0.0'})

    # Check PRODUCT node
    product = dj_playlists[0]
    test_case.assertEqual(product.tag, 'PRODUCT')
    test_case.assertEqual(product.attrib, {'Name': 'rekordbox', 'Version': '6.8.5', 'Company': 'AlphaTheta'})

    # Check COLLECTION node
    collection = dj_playlists[1]
    test_case.assertEqual(collection.tag, 'COLLECTION')
    test_case.assertEqual(collection.attrib, {'Entries': str(expected_track_count)})
    test_case.assertEqual(len(collection), expected_track_count)

    # Check PLAYLISTS/ROOT structure
    playlists = dj_playlists[2]
    test_case.assertEqual(len(playlists), 1)
    playlist_root = playlists[0]
    test_case.assertEqual(playlist_root.tag, 'NODE')
    test_case.assertEqual(playlist_root.attrib, {'Type': '0', 'Name': 'ROOT', 'Count': '2'})
    test_case.assertEqual(len(playlist_root), 2)

    cue_analysis = playlist_root[0]
    test_case.assertEqual(cue_analysis.tag, 'NODE')
    test_case.assertEqual(cue_analysis.attrib, {'Name': 'CUE Analysis Playlist', 'Type': '1', 'KeyType': '0', 'Entries': '0'})
    test_case.assertEqual(len(cue_analysis), 0)

    pruned = playlist_root[1]
    test_case.assertEqual(pruned.tag, 'NODE')
    test_case.assertIn(constants.ATTR_TITLE, pruned.attrib)
    test_case.assertEqual(pruned.attrib[constants.ATTR_TITLE], '_pruned')


def _assert_track_attrs_from_tags(test_case: unittest.TestCase, track: ET.Element) -> None:
    '''Asserts that a TRACK element has attributes matching the standard mock Tags values.'''
    test_case.assertEqual(track.tag, 'TRACK')
    test_case.assertEqual(len(track), 0)

    test_case.assertIn(constants.ATTR_TRACK_ID, track.attrib)
    test_case.assertRegex(track.attrib[constants.ATTR_TRACK_ID], r'\d+')

    test_case.assertIn(constants.ATTR_TITLE, track.attrib)
    test_case.assertEqual(track.attrib[constants.ATTR_TITLE], MOCK_TITLE)

    test_case.assertIn(constants.ATTR_ARTIST, track.attrib)
    test_case.assertEqual(track.attrib[constants.ATTR_ARTIST], MOCK_ARTIST)

    test_case.assertIn(constants.ATTR_ALBUM, track.attrib)
    test_case.assertEqual(track.attrib[constants.ATTR_ALBUM], MOCK_ALBUM)

    test_case.assertIn(constants.ATTR_DATE_ADDED, track.attrib)
    test_case.assertRegex(track.attrib[constants.ATTR_DATE_ADDED], r'\d{4}-\d{2}-\d{2}')

    test_case.assertIn(constants.ATTR_GENRE, track.attrib)
    test_case.assertEqual(track.attrib[constants.ATTR_GENRE], MOCK_GENRE)

    test_case.assertIn('Tonality', track.attrib)
    test_case.assertEqual(track.attrib['Tonality'], MOCK_TONALITY)

    test_case.assertIn(constants.ATTR_LOCATION, track.attrib)

# Test classes
class TestGenerateDatePaths(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_col_path   = patch('djmgmt.library.collection_path_to_syspath').start()
        self.mock_full_path  = patch('djmgmt.library.full_path').start()
        self.mock_date_ctx   = patch('djmgmt.common.find_date_context').start()
        self.mock_remove_sub = patch('djmgmt.common.remove_subpath').start()
        self.addCleanup(patch.stopall)

        # Shared defaults used by most tests
        self.mock_col_path.return_value   = '/Users/user/Music/DJ/MOCK_FILE.aiff'
        self.mock_date_ctx.return_value   = ('2020/02 february/03', 5)
        self.mock_remove_sub.return_value = '/mock/root/2020/02 february/03/MOCK_FILE.aiff'

    def test_success_default_parameters(self) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when called with only the required positional arguments.
        '''
        self.mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'

        actual = library.generate_date_paths(ET.fromstring(COLLECTION_XML), '/mock/root/')

        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        self.mock_col_path.assert_called()
        self.mock_full_path.assert_called_once()
        self.mock_date_ctx.assert_called_once()
        self.mock_remove_sub.assert_called_once()

    def test_success_metadata_path(self) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when called with the include metadata in path parameter.
        '''
        self.mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'
        self.mock_remove_sub.return_value = '/mock/root/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff'

        actual = library.generate_date_paths(ET.fromstring(COLLECTION_XML), '/mock/root/', metadata_path=True)

        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_ARTIST/MOCK_ALBUM/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        self.mock_col_path.assert_called()
        self.mock_full_path.assert_called_once()
        self.mock_date_ctx.assert_called_once()
        self.mock_remove_sub.assert_called_once()

    def test_success_playlist_ids_include(self) -> None:
        '''Tests that a collection with a single track yields the expected input/output path mapping
        when the collection includes the playlist ID in the given set.
        '''
        self.mock_full_path.return_value = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE.aiff'

        actual = library.generate_date_paths(ET.fromstring(COLLECTION_XML), '/mock/root/', playlist_ids={'1'})

        expected = [('/Users/user/Music/DJ/MOCK_FILE.aiff',
                     '/mock/root/2020/02 february/03/MOCK_FILE.aiff')]
        self.assertEqual(actual, expected)
        self.mock_col_path.assert_called()
        self.mock_full_path.assert_called_once()
        self.mock_date_ctx.assert_called_once()
        self.mock_remove_sub.assert_called_once()

    def test_success_playlist_ids_exclude(self) -> None:
        '''Tests that a collection with a single track yields an empty path mapping
        when the collection does NOT include the playlist ID in the given set.
        '''
        actual = library.generate_date_paths(ET.fromstring(COLLECTION_XML), '/mock/root/', playlist_ids={'MOCK_ID_TO_SKIP'})

        self.assertEqual(actual, [])
        # Only syspath conversion is called; path-building helpers are skipped
        self.mock_col_path.assert_called_once()
        self.mock_full_path.assert_not_called()
        self.mock_date_ctx.assert_not_called()
        self.mock_remove_sub.assert_not_called()

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
        expected = '/Users/user/Music/DJ/2020/02 february/03/MOCK_FILE_1.aiff'
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
        expected = '/Users/user/Music/DJ/2020/02 february/03/MOCK_ARTIST_1/MOCK_ALBUM_1/MOCK_FILE_1.aiff'
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
TRACK_XML_PLAYLIST_SIMPLE  = _create_track_xml(1)  # TrackID=1, in _pruned
TRACK_XML_COLLECTION       = _create_track_xml(3)  # TrackID=3, collection-only

# collection XML that contains 2 tracks present in the '_pruned' playlist, and 1 track that only exists in the collection
DJ_PLAYLISTS_XML = _build_dj_playlists_xml(
    [TRACK_XML_COLLECTION, TRACK_XML_PLAYLIST_SIMPLE],
    ['1', '2']
)

class TestFilterPathMappings(unittest.TestCase):
    # _pruned playlist is present but empty (no TRACK children)
    XML_EMPTY_PLAYLIST = _build_dj_playlists_xml(
        [TRACK_XML_COLLECTION, TRACK_XML_PLAYLIST_SIMPLE],
        []
    )

    def test_success_mappings_simple(self) -> None:
        '''Tests that the given simple mapping passes through the filter.'''
        
        # Call target function
        mappings = [
            # playlist file: simple
            ('/Users/user/Music/DJ/MOCK_FILE_1.aiff', '/mock/output/MOCK_FILE_1.mp3'),
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
            ('/Users/user/Music/DJ/MOCK_FILE_3.aiff', '/mock/output/MOCK_FILE_3.mp3'),
        ]
        collection = ET.fromstring(DJ_PLAYLISTS_XML)
        actual = library.filter_path_mappings(mappings, collection, constants.XPATH_PRUNED)
        
        # Assert expectations
        self.assertEqual(len(actual), 0)
    
    def test_success_empty_playlist(self) -> None:
        '''Tests that no mappings are filtered for a collection with an empty playlist.'''
        mappings = [
            # playlist file: simple
            ('/Users/user/Music/DJ/MOCK_FILE.aiff', '/mock/output/MOCK_FILE.mp3'),
            
            # non-playlist collection file
            ('/Users/user/Music/DJ/MOCK_COLLECTION_FILE.aiff', '/mock/output/MOCK_COLLECTION_FILE.mp3'),
        ]
        collection = ET.fromstring(TestFilterPathMappings.XML_EMPTY_PLAYLIST)
        
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

    def setUp(self) -> None:
        self.mock_to_syspath = patch('djmgmt.library.collection_path_to_syspath').start()
        self.mock_tags_load  = patch('djmgmt.tags.Tags.load').start()
        self.addCleanup(patch.stopall)

        mock_tags = MagicMock()
        mock_tags.basic_identifier.return_value = 'mock_identifier'
        self.mock_tags_load.return_value = mock_tags

    def test_success_no_filter(self) -> None:
        '''Tests that the identifiers are loaded from the given collection XML with no playlist filter.'''
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection)

        self.assertEqual(actual, ['mock_identifier'])
        self.mock_to_syspath.assert_called_once()

    def test_success_filter_included(self) -> None:
        '''Tests that the identifiers are loaded from the given collection XML with a matching playlist filter.'''
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection, {'1'})

        self.assertEqual(actual, ['mock_identifier'])
        self.mock_to_syspath.assert_called_once()

    def test_success_filter_excluded(self) -> None:
        '''Tests that no identifiers are loaded from the given collection XML with a non-matching playlist filter.'''
        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection, {'mock_exclude_id'})

        self.assertEqual(len(actual), 0)
        self.mock_to_syspath.assert_called_once()

    @patch('logging.error')
    def test_error_tags_load(self, mock_log_error: MagicMock) -> None:
        '''Tests that the identifiers are not loaded from the given collection XML when the track tags can't load.'''
        self.mock_tags_load.return_value = None

        collection = ET.fromstring(COLLECTION_XML)
        actual = library.collect_identifiers(collection)

        self.assertEqual(len(actual), 0)
        self.mock_to_syspath.assert_called_once()
        mock_log_error.assert_called_once()

class TestGetPlayedTracks(unittest.TestCase):
    XML_DUPLICATES = f'''
    <?xml version="1.0" encoding="UTF-8"?>

    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        {_build_collection_xml([_create_track_xml(0), _create_track_xml(1)])}
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

    XML_ARCHIVE = f'''
    <?xml version="1.0" encoding="UTF-8"?>

    <DJ_PLAYLISTS Version="1.0.0">
        <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
        {_build_collection_xml([_create_track_xml(0), _create_track_xml(1)])}
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
        root = ET.fromstring(TestGetPlayedTracks.XML_DUPLICATES)
        actual = library.get_played_tracks(root)
        
        # Assert expectations
        self.assertEqual(actual, ['0', '1'])

class TestGetUnplayedTracks(unittest.TestCase):
    XML_PRUNED = _build_dj_playlists_xml([], ['0', '1'])
    
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
    @patch('djmgmt.library.add_pruned_tracks')
    @patch('djmgmt.library.find_node')
    @patch('djmgmt.library.load_collection')
    def test_success(self,
                     mock_load_collection: MagicMock,
                     mock_find_node: MagicMock,
                     mock_add_pruned: MagicMock,
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
        mock_add_pruned.return_value = mock_base_root
        mock_add_played.return_value = mock_base_root
        mock_add_unplayed.return_value = mock_base_root

        # Call target function
        result = library.record_dynamic_tracks(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR)

        # Assert expectations
        mock_load_collection.assert_any_call(MOCK_INPUT_DIR)
        mock_load_collection.assert_any_call(constants.COLLECTION_PATH_TEMPLATE)

        # Verify collection was copied
        mock_base_collection.clear.assert_called_once()

        mock_add_pruned.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_add_played.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_add_unplayed.assert_called_once_with(mock_collection_root, mock_base_root)
        mock_xml_write.assert_called_once_with(MOCK_OUTPUT_DIR, encoding='UTF-8', xml_declaration=True)
        self.assertEqual(result, mock_base_root)

class TestAddPrunedTracks(unittest.TestCase):
    '''Tests for library.add_pruned_tracks.'''

    def test_success(self) -> None:
        '''Tests that _pruned playlist is populated from input collection.'''
        input_xml = _build_dj_playlists_xml(
            [_create_track_xml(1), _create_track_xml(2)],
            ['1', '2']
        )
        collection_root = ET.fromstring(input_xml)
        template_tree = ET.parse(constants.COLLECTION_PATH_TEMPLATE)
        base_root = template_tree.getroot()

        result = library.add_pruned_tracks(collection_root, base_root)

        pruned_node = result.find(constants.XPATH_PRUNED)
        self.assertIsNotNone(pruned_node)
        assert pruned_node is not None
        self.assertEqual(pruned_node.get('Entries'), '2')
        tracks = pruned_node.findall(constants.TAG_TRACK)
        self.assertListEqual([t.get('Key') for t in tracks], ['1', '2'])

class TestRecordCollection(unittest.TestCase):
    '''Tests for library.record_collection.'''

    def setUp(self) -> None:
        self.mock_path_exists   = patch('os.path.exists').start()
        self.mock_collect_paths = patch('djmgmt.common.collect_paths').start()
        self.mock_tags_load     = patch('djmgmt.tags.Tags.load').start()
        self.mock_xml_parse     = patch('djmgmt.library.ET.parse').start()
        self.mock_xml_write     = patch.object(ET.ElementTree, 'write').start()
        self.mock_log_dry_run   = patch('djmgmt.common.log_dry_run').start()
        self.addCleanup(patch.stopall)

    def test_success_new_collection_file(self) -> None:
        '''Tests that a single music file is correctly written to a newly created XML collection.'''
        MOCK_PARENT = f"{MOCK_INPUT_DIR}{os.sep}"
        self.mock_path_exists.side_effect = [False, True]
        self.mock_collect_paths.return_value = [f"{MOCK_PARENT}mock_file.aiff", f"{MOCK_PARENT}03 - 暴風一族 (Remix).mp3"]
        self.mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Assert call expectations
        self.mock_xml_parse.assert_called_once_with(constants.COLLECTION_PATH_TEMPLATE)
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_tags_load.assert_has_calls([
            call(self.mock_collect_paths.return_value[0]),
            call(self.mock_collect_paths.return_value[1])
        ])

        # Assert return value
        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root

        # Assert invariant DJ_PLAYLISTS structure
        _assert_dj_playlists_structure(self, dj_playlists, expected_track_count=2)

        # Assert all track attributes match the mock Tags
        collection = dj_playlists[1]
        for track in collection:
            _assert_track_attrs_from_tags(self, track)

        # Assert URL-encoded paths (unique to this test)
        track_0 = collection[0]
        self.assertEqual(track_0.attrib[constants.ATTR_LOCATION], f"file://localhost{MOCK_INPUT_DIR}/mock_file.aiff")

        track_1 = collection[1]
        self.assertEqual(track_1.attrib[constants.ATTR_LOCATION].lower(),
                         f"file://localhost{MOCK_INPUT_DIR}/03%20-%20%E6%9A%B4%E9%A2%A8%E4%B8%80%E6%97%8F%20(Remix).mp3".lower())

        # Assert _pruned playlist has entries
        pruned = dj_playlists[2][0][1]
        self.assertEqual(len(pruned), 2)
        track = pruned[0]
        self.assertEqual(track.tag, 'TRACK')
        self.assertIn(constants.ATTR_TRACK_KEY, track.attrib)
        self.assertRegex(track.attrib[constants.ATTR_TRACK_KEY], r'\d+')

    def test_success_collection_file_exists(self) -> None:
        '''Tests that a single music file is correctly added to an existing XML collection that contains an entry.'''
        FILE_PATH_MUSIC = f"{MOCK_INPUT_DIR}{os.sep}"

        # First call: insert initial track
        self.mock_path_exists.return_value = True
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}mock_file_0.aiff"]
        self.mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))
        first_result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        # Reset mocks and set up for second call
        self.mock_path_exists.reset_mock()
        self.mock_collect_paths.reset_mock()
        self.mock_tags_load.reset_mock()
        self.mock_xml_parse.reset_mock()
        self.mock_xml_write.reset_mock()

        self.mock_path_exists.return_value = True
        self.mock_collect_paths.return_value = [f"{FILE_PATH_MUSIC}mock_file_1.aiff", f"{FILE_PATH_MUSIC}03 - 暴風一族 (Remix).mp3"]
        self.mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        self.mock_xml_parse.return_value = ET.ElementTree(first_result.collection_root)

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)
        dj_playlists = result.collection_root

        # Assert call expectations for the second call
        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_xml_parse.assert_called_with(MOCK_XML_INPUT_PATH)
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_tags_load.assert_has_calls([
            call(f"{FILE_PATH_MUSIC}mock_file_1.aiff"),
            call(f"{FILE_PATH_MUSIC}03 - 暴風一族 (Remix).mp3")
        ])

        # Assert invariant DJ_PLAYLISTS structure (3 total tracks: 1 from first call + 2 new)
        _assert_dj_playlists_structure(self, dj_playlists, expected_track_count=3)

        # Assert all track attributes match the mock Tags
        collection = dj_playlists[1]
        for track in collection:
            _assert_track_attrs_from_tags(self, track)

        # Assert URL-encoded paths for the two new tracks (track 0 is from first call)
        track_1 = collection[1]
        self.assertEqual(track_1.attrib[constants.ATTR_LOCATION], f"file://localhost{MOCK_INPUT_DIR}/mock_file_1.aiff")

        track_2 = collection[2]
        self.assertEqual(track_2.attrib[constants.ATTR_LOCATION].lower(),
                         f"file://localhost{MOCK_INPUT_DIR}/03%20-%20%E6%9A%B4%E9%A2%A8%E4%B8%80%E6%97%8F%20(Remix).mp3".lower())

        # Assert _pruned has 3 tracks
        pruned = dj_playlists[2][0][1]
        self.assertEqual(len(pruned), 3)
        for track in pruned:
            self.assertEqual(track.tag, 'TRACK')
            self.assertIn(constants.ATTR_TRACK_KEY, track.attrib)
            self.assertRegex(track.attrib[constants.ATTR_TRACK_KEY], r'\d+')

    def test_success_track_exists_same_metadata(self) -> None:
        '''Tests that a track is not added to the collection XML if it already exists and the metadata is the same.'''
        mock_file = 'mock_file.mp3'
        self.mock_path_exists.return_value = True
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_file}"]
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(_build_single_track_collection_xml(mock_file)))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 1)

        # XML should be unchanged (result.collection_root is the same object as the parsed root)
        self.assertEqual(ET.tostring(result.collection_root, encoding='UTF-8'),
                         ET.tostring(cast(ET.Element, self.mock_xml_parse.return_value.getroot()), encoding='UTF-8'))

    def test_success_track_exists_update_metadata(self) -> None:
        '''Tests that the tag metadata is updated for an existing track.'''
        mock_file = 'mock_file.mp3'
        self.mock_path_exists.return_value = True
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_file}"]
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(_build_single_track_collection_xml(mock_file)))
        self.mock_tags_load.side_effect = [Tags(f"{MOCK_ARTIST}_update",
                                                f"{MOCK_ALBUM}_update",
                                                f"{MOCK_TITLE}_update",
                                                f"{MOCK_GENRE}_update",
                                                f"{MOCK_TONALITY}_update")]

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 1)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        dj_playlists = result.collection_root
        _assert_dj_playlists_structure(self, dj_playlists, expected_track_count=1)

        # Assert immutable fields are unchanged
        track = dj_playlists[1][0]
        self.assertEqual(track.get(constants.ATTR_TRACK_ID), '1')
        self.assertEqual(track.get(constants.ATTR_DATE_ADDED), MOCK_DATE_ADDED)
        self.assertEqual(track.get(constants.ATTR_LOCATION), f"file://localhost{MOCK_INPUT_DIR}/{mock_file}")

        # Assert updated fields
        self.assertEqual(track.get(constants.ATTR_ARTIST), f"{MOCK_ARTIST}_update")
        self.assertEqual(track.get(constants.ATTR_ALBUM), f"{MOCK_ALBUM}_update")
        self.assertEqual(track.get(constants.ATTR_TITLE), f"{MOCK_TITLE}_update")
        self.assertEqual(track.get(constants.ATTR_GENRE), f"{MOCK_GENRE}_update")
        self.assertEqual(track.get('Tonality'), f"{MOCK_TONALITY}_update")

    def test_success_missing_metadata(self) -> None:
        '''Tests that empty metadata values are written for a track without any Tags metadata.'''
        self.mock_path_exists.side_effect = [False, True]
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}mock_file.aiff"]
        self.mock_tags_load.return_value = Tags()  # mock empty tag data
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 1)
        self.assertEqual(result.tracks_updated, 0)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_xml_parse.assert_called_once_with(constants.COLLECTION_PATH_TEMPLATE)
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_tags_load.assert_has_calls([call(f"{MOCK_INPUT_DIR}{os.sep}mock_file.aiff")])

        dj_playlists = result.collection_root
        _assert_dj_playlists_structure(self, dj_playlists, expected_track_count=1)

        # Assert empty-string metadata for all tag fields
        track = dj_playlists[1][0]
        self.assertEqual(track.tag, 'TRACK')
        self.assertIn(constants.ATTR_TRACK_ID, track.attrib)
        self.assertRegex(track.attrib[constants.ATTR_TRACK_ID], r'\d+')
        self.assertEqual(track.attrib[constants.ATTR_TITLE], '')
        self.assertEqual(track.attrib[constants.ATTR_ARTIST], '')
        self.assertEqual(track.attrib[constants.ATTR_ALBUM], '')
        self.assertRegex(track.attrib[constants.ATTR_DATE_ADDED], r'\d{4}-\d{2}-\d{2}')
        self.assertEqual(track.attrib[constants.ATTR_LOCATION], f"file://localhost{MOCK_INPUT_DIR}/mock_file.aiff")
        self.assertEqual(track.attrib[constants.ATTR_GENRE], '')
        self.assertEqual(track.attrib['Tonality'], '')

    def test_success_no_music_files(self) -> None:
        '''Tests that the XML collection contains no Tracks when no music files are in the input directory.'''
        self.mock_path_exists.side_effect = [False, True]
        self.mock_collect_paths.return_value = ['mock_file.foo']
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 0)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_tags_load.assert_not_called()
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)

        # Empty collection still writes a valid DJ_PLAYLISTS structure
        _assert_dj_playlists_structure(self, result.collection_root, expected_track_count=0)

        # _pruned should have no tracks
        pruned = result.collection_root[2][0][1]
        self.assertEqual(len(pruned), 0)

    def test_success_unreadable_tags(self) -> None:
        '''Tests that a track is not added to the collection XML if its tags are invalid.'''
        mock_bad_file = 'mock_bad_file.mp3'
        self.mock_path_exists.return_value = True
        self.mock_collect_paths.return_value = [f"{MOCK_INPUT_DIR}{os.sep}{mock_bad_file}"]
        self.mock_tags_load.return_value = None  # mock tag reading failure
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(_build_single_track_collection_xml('mock_existing_file.mp3')))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertEqual(result.tracks_added, 0)
        self.assertEqual(result.tracks_updated, 0)

        self.mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        self.mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_bad_file}")
        self.mock_xml_write.assert_called_once_with(MOCK_XML_OUTPUT_PATH, encoding='UTF-8', xml_declaration=True)
        self.mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)

        # XML should be unchanged after failed tag load
        expected_root = self.mock_xml_parse.return_value.getroot()
        self.assertIsNotNone(expected_root)
        assert expected_root is not None
        self.assertEqual(ET.tostring(result.collection_root, encoding='UTF-8'),
                         ET.tostring(expected_root, encoding='UTF-8'))

    def test_collection_exists_invalid_content(self) -> None:
        '''Tests that the expected exception is raised when the collection file is invalid.'''
        self.mock_path_exists.return_value = True
        mock_exception_message = 'mock_parse_error'
        self.mock_xml_parse.side_effect = Exception(mock_exception_message)

        with self.assertRaisesRegex(Exception, mock_exception_message):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.mock_collect_paths.assert_not_called()
        self.mock_tags_load.assert_not_called()
        self.mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)
        self.mock_xml_write.assert_not_called()

    def test_collection_exists_missing_collection_tag(self) -> None:
        '''Tests that the expected exception is raised when the collection file is missing a COLLECTION tag.'''
        self.mock_path_exists.return_value = True
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring('<MOCK_NO_COLLECTION></MOCK_NO_COLLECTION>'))

        with self.assertRaises(ValueError):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.mock_collect_paths.assert_not_called()
        self.mock_tags_load.assert_not_called()
        self.mock_xml_parse.assert_called_once_with(MOCK_XML_INPUT_PATH)
        self.mock_xml_write.assert_not_called()

    def test_template_file_invalid(self) -> None:
        '''Tests that an exception is raised when the template file is not present.'''
        self.mock_path_exists.return_value = False
        self.mock_xml_parse.side_effect = Exception()  # mock a parsing error due to missing file

        with self.assertRaises(Exception):
            library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH)

        self.mock_collect_paths.assert_not_called()
        self.mock_tags_load.assert_not_called()
        self.mock_xml_write.assert_not_called()

    def test_dry_run(self) -> None:
        '''Test that dry_run=True skips XML write and logs the operation.'''
        MOCK_PARENT = f"{MOCK_INPUT_DIR}{os.sep}"
        self.mock_path_exists.side_effect = [False, True]
        self.mock_collect_paths.return_value = [f"{MOCK_PARENT}track1.aiff", f"{MOCK_PARENT}track2.mp3"]
        self.mock_tags_load.return_value = Tags(MOCK_ARTIST, MOCK_ALBUM, MOCK_TITLE, MOCK_GENRE, MOCK_TONALITY)
        self.mock_xml_parse.return_value = ET.ElementTree(ET.fromstring(XML_BASE))

        result = library.record_collection(MOCK_INPUT_DIR, MOCK_XML_INPUT_PATH, MOCK_XML_OUTPUT_PATH, dry_run=True)

        self.mock_xml_write.assert_not_called()
        self.mock_log_dry_run.assert_called_once_with('write collection', MOCK_XML_INPUT_PATH)

        self.assertIsInstance(result, library.RecordResult)
        self.assertIsNotNone(result.collection_root)
        self.assertEqual(result.tracks_added, 2)
        self.assertEqual(result.tracks_updated, 0)

        collection = result.collection_root.find('.//COLLECTION')
        assert collection is not None
        self.assertEqual(len(collection.findall('TRACK')), 2)


class TestExtractTrackMetadata(unittest.TestCase):
    '''Tests for library.extract_track_metadata.'''

    def test_success(self) -> None:
        '''Tests that track metadata is extracted correctly from collection.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Name="Test Track" Artist="Test Artist"'
            ' Album="Test Album" Location="file://localhost/Users/user/Music/DJ/test.aiff"/>',
        ]))
        source_path = '/Users/user/Music/DJ/test.aiff'

        # Call function
        result = library.extract_track_metadata_by_path(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, 'Test Track')
        self.assertEqual(result.artist, 'Test Artist')
        self.assertEqual(result.album, 'Test Album')
        self.assertEqual(result.path, source_path)

    def test_track_not_found(self) -> None:
        '''Tests that None is returned when track is not found in collection.'''
        collection = ET.fromstring(COLLECTION_XML_EMPTY)
        source_path = '/nonexistent/path.aiff'

        # Call function
        result = library.extract_track_metadata_by_path(collection, source_path)

        # Assertions
        self.assertIsNone(result)

    def test_missing_metadata_fields(self) -> None:
        '''Tests that empty strings are returned for missing metadata fields.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Location="file://localhost/Users/user/Music/DJ/test.aiff"/>',
        ]))
        source_path = '/Users/user/Music/DJ/test.aiff'

        # Call function
        result = library.extract_track_metadata_by_path(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, '')
        self.assertEqual(result.artist, '')
        self.assertEqual(result.album, '')
        self.assertEqual(result.path, source_path)

    def test_url_encoded_path(self) -> None:
        '''Tests that URL-encoded characters in path are handled correctly.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Name="Test Track" Artist="Test Artist"'
            ' Album="Test Album" Location="file://localhost/Users/user/Music%20Library/test%20(mix).aiff"/>',
        ]))
        source_path = '/Users/user/Music Library/test (mix).aiff'

        # Call function
        result = library.extract_track_metadata_by_path(collection, source_path)

        # Assertions
        self.assertIsNotNone(result)
        assert result
        self.assertEqual(result.title, 'Test Track')
        self.assertEqual(result.path, source_path)


class TestBuildTrackIndex(unittest.TestCase):
    '''Tests for library._build_track_index.'''

    def test_success_single_track(self) -> None:
        '''Tests that a single track is indexed by its Location attribute.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Name="Test Track" Location="file://localhost/path/to/track.aiff"/>',
        ]))

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn('file://localhost/path/to/track.aiff', result)
        self.assertEqual(result['file://localhost/path/to/track.aiff'].get('TrackID'), '1')

    def test_success_multiple_tracks(self) -> None:
        '''Tests that multiple tracks are indexed correctly.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Name="Track 1" Location="file://localhost/path/track1.aiff"/>',
            '<TRACK TrackID="2" Name="Track 2" Location="file://localhost/path/track2.aiff"/>',
            '<TRACK TrackID="3" Name="Track 3" Location="file://localhost/path/track3.aiff"/>',
        ]))

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result['file://localhost/path/track1.aiff'].get('TrackID'), '1')
        self.assertEqual(result['file://localhost/path/track2.aiff'].get('TrackID'), '2')
        self.assertEqual(result['file://localhost/path/track3.aiff'].get('TrackID'), '3')

    def test_success_empty_collection(self) -> None:
        '''Tests that an empty collection returns an empty index.'''
        collection = ET.fromstring(COLLECTION_XML_EMPTY)

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertDictEqual(result, {})

    def test_success_track_without_location(self) -> None:
        '''Tests that tracks without Location attribute are skipped.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Name="Track With Location" Location="file://localhost/path/track.aiff"/>',
            '<TRACK TrackID="2" Name="Track Without Location"/>',
        ]))

        # Call function
        result = library._build_track_index(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn('file://localhost/path/track.aiff', result)


class TestMergeCollections(unittest.TestCase):
    '''Tests for library.merge_collections.'''

    # XML templates for testing
    XML_PRIMARY = _build_dj_playlists_xml(
        ['<TRACK TrackID="1" Name="Track A" Artist="Artist A" Location="file://localhost/path/trackA.aiff"/>',
         '<TRACK TrackID="2" Name="Track B" Artist="Artist B" Location="file://localhost/path/trackB.aiff"/>'],
        []
    )
    XML_SECONDARY = _build_dj_playlists_xml(
        ['<TRACK TrackID="3" Name="Track C" Artist="Artist C" Location="file://localhost/path/trackC.aiff"/>',
         '<TRACK TrackID="4" Name="Track D" Artist="Artist D" Location="file://localhost/path/trackD.aiff"/>'],
        []
    )
    XML_OVERLAPPING = _build_dj_playlists_xml(
        ['<TRACK TrackID="5" Name="Track A Updated" Artist="Artist A Updated" Location="file://localhost/path/trackA.aiff"/>',
         '<TRACK TrackID="6" Name="Track E" Artist="Artist E" Location="file://localhost/path/trackE.aiff"/>'],
        []
    )
    XML_EMPTY = _build_dj_playlists_xml([], [])

    def setUp(self) -> None:
        self.mock_load_collection = patch('djmgmt.library.load_collection').start()
        self.mock_getmtime        = patch('os.path.getmtime').start()
        self.addCleanup(patch.stopall)

    def test_success_disjoint_collections(self) -> None:
        '''Tests merging two collections with no overlapping tracks.'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_SECONDARY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [1000.0, 500.0]  # primary is newer

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 4)
        self.assertEqual(collection.get('Entries'), '4')

        locations = {track.get('Location') for track in tracks}
        self.assertIn('file://localhost/path/trackA.aiff', locations)
        self.assertIn('file://localhost/path/trackB.aiff', locations)
        self.assertIn('file://localhost/path/trackC.aiff', locations)
        self.assertIn('file://localhost/path/trackD.aiff', locations)

    def test_success_overlapping_newer_primary(self) -> None:
        '''Tests that overlapping tracks use metadata from newer file (primary).'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_OVERLAPPING),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [1000.0, 500.0]  # primary is newer

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 3)  # trackA, trackB from primary + trackE from secondary

        track_a = next((t for t in tracks if t.get('Location') == 'file://localhost/path/trackA.aiff'), None)
        assert track_a is not None
        self.assertEqual(track_a.get('Name'), 'Track A')  # from primary (newer)
        self.assertEqual(track_a.get('Artist'), 'Artist A')  # from primary (newer)

    def test_success_overlapping_newer_secondary(self) -> None:
        '''Tests that overlapping tracks use metadata from newer file (secondary).'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_OVERLAPPING),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [500.0, 1000.0]  # secondary is newer

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 3)  # trackA (updated), trackB, trackE

        track_a = next((t for t in tracks if t.get('Location') == 'file://localhost/path/trackA.aiff'), None)
        assert track_a is not None
        self.assertEqual(track_a.get('Name'), 'Track A Updated')  # from secondary (newer)
        self.assertEqual(track_a.get('Artist'), 'Artist A Updated')  # from secondary (newer)

    def test_success_empty_primary(self) -> None:
        '''Tests merging when primary collection is empty.'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_EMPTY),
            ET.fromstring(TestMergeCollections.XML_SECONDARY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [1000.0, 500.0]

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 2)  # only secondary tracks
        self.assertEqual(collection.get('Entries'), '2')

    def test_success_empty_secondary(self) -> None:
        '''Tests merging when secondary collection is empty.'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_PRIMARY),
            ET.fromstring(TestMergeCollections.XML_EMPTY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [1000.0, 500.0]

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 2)  # only primary tracks
        self.assertEqual(collection.get('Entries'), '2')

    def test_success_both_empty(self) -> None:
        '''Tests merging when both collections are empty.'''
        self.mock_load_collection.side_effect = [
            ET.fromstring(TestMergeCollections.XML_EMPTY),
            ET.fromstring(TestMergeCollections.XML_EMPTY),
            ET.parse(constants.COLLECTION_PATH_TEMPLATE).getroot()
        ]
        self.mock_getmtime.side_effect = [1000.0, 500.0]

        result = library.merge_collections('/mock/primary.xml', '/mock/secondary.xml')

        collection = result.find(constants.XPATH_COLLECTION)
        assert collection is not None
        tracks = collection.findall('TRACK')
        self.assertEqual(len(tracks), 0)
        self.assertEqual(collection.get('Entries'), '0')


class TestBuildTrackIdToLocation(unittest.TestCase):
    '''Tests for library._build_track_id_to_location.'''

    def test_success_single_track(self) -> None:
        '''Tests that a single track is mapped from TrackID to Location.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="123" Name="Test Track" Location="file://localhost/path/to/track.aiff"/>',
        ]))

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result['123'], 'file://localhost/path/to/track.aiff')

    def test_success_multiple_tracks(self) -> None:
        '''Tests that multiple tracks are mapped correctly.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Location="file://localhost/path/track1.aiff"/>',
            '<TRACK TrackID="2" Location="file://localhost/path/track2.aiff"/>',
            '<TRACK TrackID="3" Location="file://localhost/path/track3.aiff"/>',
        ]))

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 3)
        self.assertEqual(result['1'], 'file://localhost/path/track1.aiff')
        self.assertEqual(result['2'], 'file://localhost/path/track2.aiff')
        self.assertEqual(result['3'], 'file://localhost/path/track3.aiff')

    def test_success_empty_collection(self) -> None:
        '''Tests that an empty collection returns an empty mapping.'''
        collection = ET.fromstring(COLLECTION_XML_EMPTY)

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertDictEqual(result, {})

    def test_success_track_missing_id_or_location(self) -> None:
        '''Tests that tracks missing TrackID or Location are skipped.'''
        collection = ET.fromstring(_build_collection_xml([
            '<TRACK TrackID="1" Location="file://localhost/path/track1.aiff"/>',
            '<TRACK TrackID="2"/>',
            '<TRACK Location="file://localhost/path/track3.aiff"/>',
        ]))

        # Call function
        result = library._build_track_id_to_location(collection)

        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result['1'], 'file://localhost/path/track1.aiff')


class TestGetPlaylistTrackKeys(unittest.TestCase):
    '''Tests for library._get_playlist_track_keys.'''

    def test_success_with_tracks(self) -> None:
        '''Tests extracting track keys from a playlist with tracks.'''
        root = ET.fromstring(_build_dj_playlists_xml([], ['1', '2', '3']))

        # Call function
        result = library._get_playlist_track_keys(root, constants.XPATH_PRUNED)

        # Assertions
        self.assertSetEqual(result, {'1', '2', '3'})

    def test_success_empty_playlist(self) -> None:
        '''Tests extracting keys from an empty playlist.'''
        root = ET.fromstring(_build_dj_playlists_xml([], []))

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
        primary_root = ET.fromstring(_build_dj_playlists_xml(
            ['<TRACK TrackID="1" Location="file://localhost/path/trackA.aiff"/>',
             '<TRACK TrackID="2" Location="file://localhost/path/trackB.aiff"/>'],
            ['1', '2']
        ))
        secondary_root = ET.fromstring(_build_dj_playlists_xml(
            ['<TRACK TrackID="3" Location="file://localhost/path/trackC.aiff"/>',
             '<TRACK TrackID="4" Location="file://localhost/path/trackD.aiff"/>'],
            ['3', '4']
        ))
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
        primary_root = ET.fromstring(_build_dj_playlists_xml(
            ['<TRACK TrackID="1" Location="file://localhost/path/trackA.aiff"/>'],
            ['1']
        ))
        secondary_root = ET.fromstring(_build_dj_playlists_xml(
            ['<TRACK TrackID="99" Location="file://localhost/path/trackA.aiff"/>'],
            ['99']
        ))
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


# XML fixture for playlist node tests
PLAYLIST_XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
    {_build_collection_xml([_create_track_xml(1), _create_track_xml(2)])}
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="2">
            <NODE Name="dynamic" Type="0" Count="1">
                <NODE Name="unplayed" Type="1" KeyType="0" Entries="2">
                    <TRACK Key="1"/>
                    <TRACK Key="2"/>
                </NODE>
            </NODE>
            <NODE Name="flat_playlist" Type="1" KeyType="0" Entries="1">
                <TRACK Key="1"/>
            </NODE>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>'''.strip()


class TestFindPlaylistNode(unittest.TestCase):
    '''Tests for library.find_playlist_node.'''

    def setUp(self) -> None:
        self.root = ET.fromstring(PLAYLIST_XML)

    def test_nested_path(self) -> None:
        '''Tests finding a nested playlist node via dot-separated path.'''
        node = library.find_playlist_node(self.root, 'dynamic.unplayed')

        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.get('Name'), 'unplayed')
        self.assertEqual(len(node.findall('TRACK')), 2)

    def test_flat_path(self) -> None:
        '''Tests finding a top-level playlist node.'''
        node = library.find_playlist_node(self.root, 'flat_playlist')

        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.get('Name'), 'flat_playlist')

    def test_not_found(self) -> None:
        '''Tests that None is returned for a nonexistent playlist path.'''
        node = library.find_playlist_node(self.root, 'nonexistent.path')

        self.assertIsNone(node)

    def test_partial_path_not_found(self) -> None:
        '''Tests that None is returned when first segment matches but second does not.'''
        node = library.find_playlist_node(self.root, 'dynamic.nonexistent')

        self.assertIsNone(node)

    def test_no_playlists_root(self) -> None:
        '''Tests that None is returned when PLAYLISTS/ROOT is missing.'''
        root = ET.fromstring('<DJ_PLAYLISTS><COLLECTION/></DJ_PLAYLISTS>')

        node = library.find_playlist_node(root, 'dynamic.unplayed')

        self.assertIsNone(node)


class TestGetPlaylistTrackIds(unittest.TestCase):
    '''Tests for library.get_playlist_track_ids.'''

    def setUp(self) -> None:
        self.root = ET.fromstring(PLAYLIST_XML)

    def test_returns_ordered_ids(self) -> None:
        '''Tests that track IDs are returned in order.'''
        node = library.find_playlist_node(self.root, 'dynamic.unplayed')
        assert node is not None

        result = library.get_playlist_track_ids(node)

        self.assertListEqual(result, ['1', '2'])

    def test_single_track(self) -> None:
        '''Tests extraction from a playlist with one track.'''
        node = library.find_playlist_node(self.root, 'flat_playlist')
        assert node is not None

        result = library.get_playlist_track_ids(node)

        self.assertListEqual(result, ['1'])

    def test_empty_playlist(self) -> None:
        '''Tests extraction from a playlist with no tracks.'''
        node = ET.fromstring('<NODE Name="empty" Type="1" KeyType="0" Entries="0"/>')

        result = library.get_playlist_track_ids(node)

        self.assertListEqual(result, [])
