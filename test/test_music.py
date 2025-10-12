import unittest
import os
import zipfile
from typing import cast, Callable
from argparse import Namespace
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, call
from zipfile import ZipInfo

from src import music
from src import constants
from src.tags import Tags

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

# Constants
MOCK_INPUT_DIR = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'
MOCK_XML_FILE_PATH = '/mock/xml/file.xml'
MOCK_ARTIST = 'mock_artist'
MOCK_ALBUM = 'mock_album'
MOCK_TITLE = 'mock_title'
MOCK_GENRE = 'mock_genre'
MOCK_TONALITY = 'mock_tonality'
MOCK_DATE_ADDED = 'mock_date_added'

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

# Primary test classes
class TestExtractAllNormalizedEncodings(unittest.TestCase):
    @patch('zipfile.ZipFile')
    def test_success_fix_filename_encoding(self,
                                           mock_zipfile: MagicMock) -> None:
        '''Tests that all contents of a zip archive are extracted and their filenames normalized.'''
        # Set up mocks
        mock_archive_path = f"{MOCK_INPUT_DIR}/file.zip"
        
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
        mock_archive_path = f"{MOCK_INPUT_DIR}/file.zip"
        
        mock_archive = MagicMock()
        mock_archive.infolist.return_value = []
        
        mock_zipfile.return_value.__enter__.return_value = mock_archive
        
        # Call target function
        actual = music.extract_all_normalized_encodings(mock_archive_path, MOCK_OUTPUT_DIR)
        
        # Assert expectations
        ## Dependent functions called
        mock_zipfile.assert_called_once_with(mock_archive_path, 'r')
        
        self.assertEqual(actual, (mock_archive_path, []))

class TestCompressDir(unittest.TestCase):
    @patch('src.common.collect_paths')
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
    @patch('src.common.collect_paths')
    @patch('src.music.extract_all_normalized_encodings')
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
    @patch('src.music.sweep')
    @patch('os.remove')
    @patch('src.encode.encode_lossless')
    @patch('tempfile.TemporaryDirectory')
    def test_success(self,
                     mock_temp_dir: MagicMock,
                     mock_encode: MagicMock,
                     mock_remove: MagicMock,
                     mmock_sweep: MagicMock) -> None:
        '''Tests that the encoding function is run and all encoded files are removed.'''
        # Set up mocks
        mock_temp_path = 'mock_temp_path'
        mock_input_file = 'mock_input_file'
        mock_temp_dir.return_value.__enter__.return_value = mock_temp_path
        mock_encode.return_value = [(mock_input_file, 'mock_output_file')]
        
        # Call target function
        mock_extensions = {'a'}
        mock_hints = {'b'}
        mock_interactive = False
        actual = music.standardize_lossless(MOCK_INPUT_DIR, mock_extensions, mock_hints, mock_interactive)
        
        # Assert expectations
        ## Check calls
        mock_temp_dir.assert_called_once()
        mock_encode.assert_called_once_with(MOCK_INPUT_DIR, mock_temp_path, '.aiff', interactive=mock_interactive)
        mock_remove.assert_called_once_with(mock_input_file)
        mmock_sweep.assert_called_once_with(mock_temp_path, MOCK_INPUT_DIR, mock_interactive, mock_extensions, mock_hints)        
        
        ## Check output
        self.assertEqual(actual, mock_encode.return_value)

class TestGetPlayedTracks(unittest.TestCase):
    XML_ARCHIVE = f'''
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
        actual = music.get_played_tracks(root)
        
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
        actual = music.get_played_tracks(root)
        
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
    
    @patch('src.music.get_played_tracks')
    def test_success(self,
                     mock_get_played: MagicMock) -> None:
        '''Tests that the function returns all unplayed tracks.'''
        # Set up mocks
        mock_root = ET.fromstring(TestGetUnplayedTracks.XML_PRUNED)
        mock_get_played.return_value = ['0', '2']
        
        actual = music.get_unplayed_tracks(mock_root)
        
        # Assert expectations
        self.assertEqual(actual, ['1'])

class TestRecordUnplayedTracks(unittest.TestCase):
    def test_success(self) -> None:
        # TODO: implement after refactor
        pass

class TestRecordCollection(unittest.TestCase):
    '''Tests for music.record_collection.'''
    
    @patch.object(ET.ElementTree, 'write')
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        dj_playlists = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations
        mock_xml_parse.assert_called_once_with(music.COLLECTION_TEMPLATE_PATH)
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        
        # Assert that the function reads the file tags
        mock_tags_load.assert_has_calls([
            call(mock_collect_paths.return_value[0]),
            call(mock_collect_paths.return_value[1])
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
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        first_call = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
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
        mock_xml_parse.return_value = ET.ElementTree(first_call)
        
        # Call the target function to check that 'mock_file_1' was inserted
        dj_playlists = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
            
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_parse.assert_called_with(MOCK_XML_FILE_PATH)
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        
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
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        actual = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_FILE_PATH)
        
        # Assert that the XML contents are the same as before attempting to add the track.
        self.assertEqual(ET.tostring(actual, encoding="UTF-8"),
                         ET.tostring(cast(ET.Element, mock_xml_parse.return_value.getroot()), encoding="UTF-8"))
            
    @patch.object(ET.ElementTree, 'write')
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        dj_playlists = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_FILE_PATH)
        
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
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        dj_playlists = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_xml_parse.assert_called_once_with(music.COLLECTION_TEMPLATE_PATH)
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        
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
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        dj_playlists = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations: all files should be skipped
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_not_called()
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        
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
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
        actual = music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
        
        # Assert call expectations
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_tags_load.assert_called_once_with(f"{MOCK_INPUT_DIR}{os.sep}{mock_bad_file}")
        mock_xml_write.assert_called_once_with(MOCK_XML_FILE_PATH, encoding='UTF-8', xml_declaration=True)
        mock_xml_parse.assert_called_once_with(MOCK_XML_FILE_PATH)
        
        # Assert that the XML contents are the same as before attempting to add the track.
        self.assertEqual(ET.tostring(actual, encoding="UTF-8"),
                         ET.tostring(mock_xml_parse.return_value, encoding="UTF-8"))
    
    @patch.object(ET.ElementTree, 'write')
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
            music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
            
        # Assert expectations: Code should only check that path exists and attempt to parse
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_parse.assert_called_once_with(MOCK_XML_FILE_PATH)
        mock_xml_write.assert_not_called()
        
    @patch.object(ET.ElementTree, 'write')
    @patch('src.music.ET.parse')
    @patch('os.path.exists')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
            music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
            
        # Assert expectations: Code should only check that path exists and attempt to parse
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_parse.assert_called_once_with(MOCK_XML_FILE_PATH)
        mock_xml_write.assert_not_called()
        
    @patch.object(ET.ElementTree, 'write')
    @patch('src.music.ET.parse')
    @patch('src.tags.Tags.load')
    @patch('src.common.collect_paths')
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
            music.record_collection(MOCK_INPUT_DIR, MOCK_XML_FILE_PATH)
            
        # Assert expectations: nothing should be called
        mock_collect_paths.assert_not_called()
        mock_tags_load.assert_not_called()
        mock_xml_write.assert_not_called()

class TestSweep(unittest.TestCase):
    @patch('shutil.move')
    @patch('zipfile.ZipFile')
    @patch('src.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
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
                             False,
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
    @patch('src.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
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
                             False,
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
    @patch('src.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
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
                             False,
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
    @patch('src.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
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
                             False,
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
    @patch('src.music.is_prefix_match')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
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
                             False,
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

class TestFlattenHierarchy(unittest.TestCase):
    @patch('shutil.move')
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_output_path_not_exists(self,
                                            mock_collect_paths: MagicMock,
                                            mock_path_exists: MagicMock,
                                            mock_input: MagicMock,
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
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, False)
        
        # Assert expectations
        expected = [
            (f"{MOCK_INPUT_DIR}/{mock_filenames[i]}",
             f"{MOCK_OUTPUT_DIR}/{mock_filenames[i]}")
            for i in range(len(mock_filenames))
        ]
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_not_called()
        mock_move.assert_has_calls([
            call(input_path, output_path)
            for input_path, output_path in expected
        ])
        
        ## Check output
        self.assertEqual(actual, expected)
        
    @patch('shutil.move')
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_output_path_exists(self,
                                        mock_collect_paths: MagicMock,
                                        mock_path_exists: MagicMock,
                                        mock_input: MagicMock,
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
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, False)
        
        # Assert expectations
        expected_input, expected_output = f"{MOCK_INPUT_DIR}/{mock_filenames[0]}", f"{MOCK_OUTPUT_DIR}/{mock_filenames[0]}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_not_called()
        mock_move.assert_called_once_with(expected_input, expected_output)
        
        ## Check output
        self.assertEqual(actual, [(expected_input, expected_output)])
        
    @patch('shutil.move')
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_interactive_confirm(self,
                                         mock_collect_paths: MagicMock,
                                         mock_path_exists: MagicMock,
                                         mock_input: MagicMock,
                                         mock_move: MagicMock) -> None:
        '''Tests that a user is prompted to confirm a path move when in interactive mode.'''
        # Set up mocks
        mock_filename = f"file.foo"
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_input.return_value = 'y'
        
        # Call target function
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, True)
        
        # Assert expectations
        expected_output = f"{MOCK_OUTPUT_DIR}/{mock_filename}"
        
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_called_once()
        mock_move.assert_called_once_with(mock_input_path, expected_output)
        
        ## Check output
        self.assertEqual(actual, [(mock_input_path, expected_output)])
        
    @patch('shutil.move')
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_interactive_decline(self,
                                         mock_collect_paths: MagicMock,
                                         mock_path_exists: MagicMock,
                                         mock_input: MagicMock,
                                         mock_move: MagicMock) -> None:
        '''Tests that a user is prompted to confirm a path move when in interactive mode.'''
        # Set up mocks
        mock_filename = f"file.foo"
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_input.return_value = 'n'
        
        # Call target function
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, True)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_called_once()
        mock_move.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])
        
    @patch('shutil.move')
    @patch('builtins.input')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_interactive_quit(self,
                                      mock_collect_paths: MagicMock,
                                      mock_path_exists: MagicMock,
                                      mock_input: MagicMock,
                                      mock_move: MagicMock) -> None:
        '''Tests that a user is prompted to confirm a path move when in interactive mode.'''
        # Set up mocks
        mock_filename = f"file.foo"
        mock_input_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_input_path]
        mock_path_exists.return_value = False
        mock_input.return_value = 'q'
        
        # Call target function
        actual = music.flatten_hierarchy(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, True)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_called_once()
        mock_move.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])

class TestExtract(unittest.TestCase):
    @patch('src.music.extract_all_normalized_encodings')
    @patch('builtins.input')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_interactive_false(self,
                                       mock_collect_paths: MagicMock,
                                       mock_path_exists: MagicMock,
                                       mock_isdir: MagicMock,
                                       mock_input: MagicMock,
                                       mock_extract_all: MagicMock) -> None:
        '''Tests that all zip archives are extracted without requesting user input.'''
        # Set up mocks
        mock_filename = 'mock_archive.zip'
        mock_file_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_file_path]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        mock_extract_all.return_value = (mock_filename, ['mock_file_0', 'mock_file_1'])
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, False)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_not_called()
        mock_extract_all.assert_called_once_with(mock_file_path, MOCK_OUTPUT_DIR)
        
        # Check output
        self.assertEqual(actual, [mock_extract_all.return_value])
        
    @patch('src.music.extract_all_normalized_encodings')
    @patch('builtins.input')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_no_zip_present(self,
                                    mock_collect_paths: MagicMock,
                                    mock_path_exists: MagicMock,
                                    mock_isdir: MagicMock,
                                    mock_input: MagicMock,
                                    mock_extract_all: MagicMock) -> None:
        '''Tests that nothing is extracted if there are no zip archives present in the input directory.'''
        # Set up mocks
        mock_file_path = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        mock_collect_paths.return_value = [mock_file_path]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, False)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_not_called()
        mock_extract_all.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])
        
    @patch('src.music.extract_all_normalized_encodings')
    @patch('builtins.input')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_output_exists(self,
                                   mock_collect_paths: MagicMock,
                                   mock_path_exists: MagicMock,
                                   mock_isdir: MagicMock,
                                   mock_input: MagicMock,
                                   mock_extract_all: MagicMock) -> None:
        '''Tests that nothing is extracted if the output directory exists.'''
        # Set up mocks
        mock_filename = f"{MOCK_INPUT_DIR}/mock_non_zip.foo"
        mock_collect_paths.return_value = [mock_filename]
        mock_path_exists.return_value = True
        mock_isdir.return_value = True
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, False)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_not_called()
        mock_extract_all.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])

    @patch('src.music.extract_all_normalized_encodings')
    @patch('builtins.input')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_interactive_true_confirm(self,
                                              mock_collect_paths: MagicMock,
                                              mock_path_exists: MagicMock,
                                              mock_isdir: MagicMock,
                                              mock_input: MagicMock,
                                              mock_extract_all: MagicMock) -> None:
        '''Tests that all zip archives are extracted after user confirms.'''
        # Set up mocks
        mock_filename = 'mock_archive.zip'
        mock_file_path = f"{MOCK_INPUT_DIR}/{mock_filename}"
        mock_collect_paths.return_value = [mock_file_path]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        mock_input.return_value = 'y'
        mock_extract_all.return_value = (mock_filename, ['mock_file_0', 'mock_file_1'])
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, True)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_called_once()
        mock_extract_all.assert_called_once_with(mock_file_path, MOCK_OUTPUT_DIR)
        
        # Check output
        self.assertEqual(actual, [mock_extract_all.return_value])
        
    @patch('src.music.extract_all_normalized_encodings')
    @patch('builtins.input')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('src.common.collect_paths')
    def test_success_zip_interactive_true_decline(self,
                                                  mock_collect_paths: MagicMock,
                                                  mock_path_exists: MagicMock,
                                                  mock_isdir: MagicMock,
                                                  mock_input: MagicMock,
                                                  mock_extract_all: MagicMock) -> None:
        '''Tests that no zip archives are extracted after user declines.'''
        # Set up mocks
        mock_filename = f"{MOCK_INPUT_DIR}/mock_archive.zip"
        mock_collect_paths.return_value = [mock_filename]
        mock_path_exists.return_value = False
        mock_isdir.return_value = False
        mock_input.return_value = 'n'
        
        # Call target function
        actual = music.extract(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, True)
        
        # Assert expectations
        ## Check calls
        mock_collect_paths.assert_called_once_with(MOCK_INPUT_DIR)
        mock_input.assert_called_once()
        mock_extract_all.assert_not_called()
        
        ## Check output
        self.assertEqual(actual, [])

class TestCompressAllCLI(unittest.TestCase):
    '''Even though this function calls os.walk, it's not a good use case for common.collect_paths,
    because that collects all absolute filepaths. The music.compress_all_cli function needs all directories, not file paths.'''
    
    @patch('src.music.compress_dir')
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
    @patch('src.music.has_no_user_files')
    @patch('src.music.get_dirs')
    def test_success_remove_empty_dir(self,
                                      mock_get_dirs: MagicMock,
                                      mock_is_empty_dir: MagicMock,
                                      mock_rmtree: MagicMock) -> None:
        '''Test that prune removes an empty directory.'''
        # Setup mocks
        mock_get_dirs.return_value = ['mock_empty_dir']
        
        # Call target function
        actual = music.prune_non_user_dirs('/mock/source/', False)
        
        ## Assert expectations
        ## Check calls
        expected_path = '/mock/source/mock_empty_dir'
        mock_get_dirs.assert_called()
        mock_is_empty_dir.assert_called()
        mock_rmtree.assert_called_once_with(expected_path)
        
        ## Check output
        self.assertListEqual(actual, [expected_path])
        
    @patch('shutil.rmtree')
    @patch('src.music.has_no_user_files')
    @patch('src.music.get_dirs')
    def test_success_skip_non_empty_dir(self,
                                        mock_get_dirs: MagicMock,
                                        mock_is_empty_dir: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Test that prune does not remove a non-empty directory.'''
        # Setup mocks
        mock_get_dirs.side_effect = [['mock_non_empty_dir'], []]
        mock_is_empty_dir.return_value = False
        
        # Call target function
        actual = music.prune_non_user_dirs('/mock/source/', False)
        
        ## Assert expectations
        ## Check calls
        mock_get_dirs.assert_called()
        mock_is_empty_dir.assert_called()
        mock_rmtree.assert_not_called()
        
        ## Check output
        self.assertListEqual(actual, [])
        
    @patch('src.music.prune_non_user_dirs')
    def test_success_cli(self, mock_prune_empty: MagicMock) -> None:
        '''Tests that the CLI wrapper calls the correct function.'''
        args = Namespace(input=MOCK_INPUT_DIR, interactive=False)
        music.prune_non_user_dirs_cli(args) # type: ignore
        
        mock_prune_empty.assert_called_once_with(MOCK_INPUT_DIR, False)

class TestPruneNonMusicFiles(unittest.TestCase):
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_remove_non_music(self,
                                      mock_collect_paths: MagicMock,
                                      mock_os_remove: MagicMock,
                                      mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock_file.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_skip_music(self,
                                mock_collect_paths: MagicMock,
                                mock_os_remove: MagicMock,
                                mock_rmtree: MagicMock) -> None:
        '''Tests that top-level music files are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_skip_music_subdirectory(self,
                                             mock_collect_paths: MagicMock,
                                             mock_os_remove: MagicMock,
                                             mock_rmtree: MagicMock) -> None:
        '''Tests that nested music files are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_remove_non_music_subdirectory(self,
                                                   mock_collect_paths: MagicMock,
                                                   mock_os_remove: MagicMock,
                                                   mock_rmtree: MagicMock) -> None:
        '''Tests that nested non-music files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock/dir/0/mock_file.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock/dir/0/mock_file.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_remove_hidden_file(self,
                                        mock_collect_paths: MagicMock,
                                        mock_os_remove: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Tests that hidden files are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_remove_zip_archive(self,
                                        mock_collect_paths: MagicMock,
                                        mock_os_remove: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Tests that zip archives are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock.zip']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/mock.zip')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('os.path.isdir')
    @patch('src.common.collect_paths')
    def test_success_remove_dir(self,
                                mock_collect_paths: MagicMock,
                                mock_isdir: MagicMock,
                                mock_os_remove: MagicMock,
                                mock_rmtree: MagicMock) -> None:
        '''Tests that .app archives are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock.app']
        mock_isdir.return_value = True
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_called_once_with('/mock/source/mock.app')
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_skip_music_hidden_dir(self,
                                           mock_collect_paths: MagicMock,
                                           mock_os_remove: MagicMock,
                                           mock_rmtree: MagicMock) -> None:
        '''Tests that music files in a hidden directory are not removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock_music.mp3']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
    
    @patch('shutil.rmtree')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_remove_non_music_hidden_dir(self,
                                                 mock_collect_paths: MagicMock,
                                                 mock_os_remove: MagicMock,
                                                 mock_rmtree: MagicMock) -> None:
        '''Tests that non-music files in a hidden directory are removed.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/.mock_hidden_dir/mock.foo']
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, False)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_os_remove.assert_called_once_with('/mock/source/.mock_hidden_dir/mock.foo')
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
    
    @patch('shutil.rmtree')
    @patch('builtins.input')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_interactive_skip(self,
                                      mock_collect_paths: MagicMock,
                                      mock_os_remove: MagicMock,
                                      mock_input: MagicMock,
                                      mock_rmtree: MagicMock) -> None:
        '''Tests that an interactive prune prompts the user to remove the non-music file and skips removal.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        mock_input.return_value = 'N'
        
        # Call target function and assert expectations
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, True)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_input.assert_called()
        mock_os_remove.assert_not_called()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, [])
        
    @patch('shutil.rmtree')
    @patch('builtins.input')
    @patch('os.remove')
    @patch('src.common.collect_paths')
    def test_success_interactive_remove(self,
                                        mock_collect_paths: MagicMock,
                                        mock_os_remove: MagicMock,
                                        mock_input: MagicMock,
                                        mock_rmtree: MagicMock) -> None:
        '''Tests that an interactive prune prompts the user to remove the non-music file and performs removal.'''
        # Setup mocks
        mock_collect_paths.return_value = ['/mock/source/mock_file.foo']
        mock_input.return_value = 'y'
        
        # Call target function and assert expectations        
        actual = music.prune_non_music('/mock/source/', constants.EXTENSIONS, True)
        
        mock_collect_paths.assert_called_once_with('/mock/source/')
        mock_input.assert_called()
        mock_os_remove.assert_called_once()
        mock_rmtree.assert_not_called()
        
        self.assertListEqual(actual, mock_collect_paths.return_value)
        
    @patch('src.music.prune_non_music')
    def test_success_cli(self, mock_prune_non_music: MagicMock) -> None:
        '''Tests that the CLI wrapper function exists and is called properly.'''
        # Call target function and assert expectations
        mock_namespace = Namespace(input='/mock/input/', output='/mock/output/', interactive=False)
        music.prune_non_music_cli(mock_namespace, set())  # type: ignore
        mock_prune_non_music.assert_called_once_with(mock_namespace.input, set(), mock_namespace.interactive)

class TestProcess(unittest.TestCase):
    @patch('src.common.write_paths')
    @patch('src.encode.find_missing_art_os')
    @patch('src.music.standardize_lossless')
    @patch('src.music.prune_non_music')
    @patch('src.music.prune_non_user_dirs')
    @patch('src.music.flatten_hierarchy')
    @patch('src.music.extract')
    @patch('src.music.sweep')
    def test_success(self,
                     mock_sweep: MagicMock,
                     mock_extract: MagicMock,
                     mock_flatten: MagicMock,
                     mock_prune_empty: MagicMock,
                     mock_prune_non_music: MagicMock,
                     mock_standardize_lossless: MagicMock,
                     mock_find_missing_art_os: MagicMock,
                     mock_write_paths: MagicMock) -> None:
        '''Tests that the process function calls the expected functions in the the correct order.'''
        # Set up mocks
        mock_call_container = MagicMock()
        mock_sweep.side_effect = lambda *_, **__: mock_call_container.sweep()
        mock_extract.side_effect = lambda *_, **__: mock_call_container.extract()
        mock_flatten.side_effect = lambda *_, **__: mock_call_container.flatten()
        mock_prune_empty.side_effect = lambda *_, **__: mock_call_container.prune_non_user_dirs()
        mock_prune_non_music.side_effect = lambda *_, **__: mock_call_container.prune_non_music()
        mock_standardize_lossless.side_effect = lambda *_, **__: mock_call_container.standardize_lossless()
        mock_find_missing_art_os.side_effect = lambda *_, **__: mock_call_container.find_missing_art_os()
        mock_write_paths.side_effect = lambda *_, **__: mock_call_container.write_paths()
        
        # Mock the result of the lossless function
        mock_standardize_lossless.return_value = [
            ('/mock/input/file_0.aif', '/mock/output/file_0.aiff'),
            ('/mock/input/file_1.wav', '/mock/output/file_1.aiff')
        ]
        
        # Call target function
        mock_interactive = False
        mock_valid_extensions = {'a'}
        mock_prefix_hints = {'b'}
        music.process(MOCK_INPUT_DIR, MOCK_OUTPUT_DIR, mock_interactive, mock_valid_extensions, mock_prefix_hints)
        
        # Assert that the primary dependent functions are called in the correct order
        self.assertEqual(mock_call_container.mock_calls[0], call.sweep())
        self.assertEqual(mock_call_container.mock_calls[1], call.extract())
        self.assertEqual(mock_call_container.mock_calls[2], call.flatten())
        self.assertEqual(mock_call_container.mock_calls[3], call.standardize_lossless())
        self.assertEqual(mock_call_container.mock_calls[4], call.prune_non_music())
        self.assertEqual(mock_call_container.mock_calls[5], call.prune_non_user_dirs())
        self.assertEqual(mock_call_container.mock_calls[6], call.find_missing_art_os())
        self.assertEqual(mock_call_container.mock_calls[7], call.write_paths())
        
        # Assert call counts and parameters
        mock_sweep.assert_called_once()
        mock_extract.assert_called_once()
        mock_flatten.assert_called_once()
        mock_standardize_lossless.assert_called_once_with(MOCK_OUTPUT_DIR, mock_valid_extensions, mock_prefix_hints, mock_interactive)
        self.assertEqual(MOCK_OUTPUT_DIR, mock_find_missing_art_os.call_args.args[0])
        self.assertEqual(mock_call_container.find_missing_art_os(), mock_write_paths.call_args.args[0])

class TestProcessCLI(unittest.TestCase):
    @patch('src.music.process')
    def test_success(self, mock_process: MagicMock) -> None:
        '''Tests that the process function is called with the expected arguments.'''
        # Call target function
        mock_interactive = False
        mock_valid_extensions = {'a'}
        mock_prefix_hints = {'b'}
        args = Namespace(input=MOCK_INPUT_DIR, output=MOCK_OUTPUT_DIR, interactive=mock_interactive)
        music.process_cli(args, mock_valid_extensions, mock_prefix_hints) # type: ignore
        
        # Assert expectations
        mock_process.assert_called_once_with(MOCK_INPUT_DIR,
                                             MOCK_OUTPUT_DIR,
                                             mock_interactive,
                                             mock_valid_extensions,
                                             mock_prefix_hints)

class TestUpdateLibrary(unittest.TestCase):
    @patch('src.sync.run_sync_mappings')
    @patch('src.library.filter_path_mappings')
    @patch('src.sync.create_sync_mappings')
    @patch('src.tags_info.compare_tags')
    @patch('src.music.record_collection')
    @patch('src.music.sweep')
    @patch('src.music.process')
    @patch('tempfile.TemporaryDirectory')
    def test_success(self,
                     mock_temp_dir: MagicMock,
                     mock_process: MagicMock,
                     mock_sweep: MagicMock,
                     mock_record_collection: MagicMock,
                     mock_compare_tags: MagicMock,
                     mock_create_sync_mappings: MagicMock,
                     mock_filter_mappings: MagicMock,
                     mock_run_sync_mappings: MagicMock) -> None:
        '''Tests that dependent functions are called with expected parameters.'''
        # Set up mocks
        mock_temp_dir_path = '/mock/temp/dir'
        mock_collection = MagicMock()
        mock_mappings_changed = [self.create_mock_file_mapping(0), self.create_mock_file_mapping(1)]
        mock_mappings_created = [self.create_mock_file_mapping(2)]
        mock_mappings_filtered = [self.create_mock_file_mapping(0)]
        
        mock_temp_dir.return_value.__enter__.return_value = mock_temp_dir_path
        mock_record_collection.return_value = mock_collection
        mock_compare_tags.return_value = mock_mappings_changed.copy()
        mock_create_sync_mappings.return_value = mock_mappings_created.copy()
        mock_filter_mappings.return_value = mock_mappings_filtered.copy()
        
        # Call target function
        mock_library = '/mock/library'
        mock_client_mirror = '/mock/client/mirror'
        mock_collection_backup_dir = 'mock/collection/backup'
        mock_interactive = False
        mock_extensions = {'.mock_ext'}
        mock_hints = {'mock_hint'}
        music.update_library(MOCK_INPUT_DIR,
                             mock_library,
                             mock_client_mirror,
                             mock_collection_backup_dir,
                             mock_interactive,
                             mock_extensions,
                             mock_hints)
        
        # Assert expectations
        ## Call parameters: process
        mock_process.assert_called_once_with(MOCK_INPUT_DIR, mock_temp_dir_path, mock_interactive, mock_extensions, mock_hints)
        
        ## Call parameters: sweep
        mock_sweep.assert_called_once_with(mock_temp_dir_path, mock_library, mock_interactive, mock_extensions, mock_hints)
        
        ## Call parameters: record_collection
        mock_record_collection.assert_called_once_with(mock_library, music.COLLECTION_PATH)
        
        ## Call parameters: compare_tags
        mock_compare_tags.assert_called_once_with(mock_library, mock_client_mirror)
        
        ## Call parameters: create_sync_mappings
        mock_create_sync_mappings.assert_called_once_with(mock_collection, mock_client_mirror)
        
        ## Call: filter_path_mappings
        mock_filter_mappings.assert_called_once_with(mock_mappings_changed, mock_collection, constants.XPATH_PRUNED)
        
        ## Call parameters: run_sync_mappings
        expected_mappings = mock_mappings_created + mock_mappings_filtered
        mock_run_sync_mappings.assert_called_once_with(expected_mappings)
        
    @patch('src.sync.run_sync_mappings')
    @patch('src.library.filter_path_mappings')
    @patch('src.tags_info.compare_tags')
    @patch('src.sync.create_sync_mappings')
    @patch('src.music.record_collection')
    @patch('src.music.sweep')
    @patch('src.music.process')
    def test_error_sync(self,
                        mock_process: MagicMock,
                        mock_sweep: MagicMock,
                        mock_record_collection: MagicMock,
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
        mock_collection_backup = 'mock/collection/backup'
        mock_interactive = False
        mock_extensions = {'.mock_ext'}
        mock_hints = {'mock_hint'}
        
        # Assert expectations
        with self.assertRaisesRegex(Exception, mock_error):
            music.update_library(MOCK_INPUT_DIR,
                                 mock_library,
                                 mock_client_mirror,
                                 mock_collection_backup,
                                 mock_interactive,
                                 mock_extensions,
                                 mock_hints)
        
        # Functions should be called before exception
        mock_process.assert_called_once()
        mock_sweep.assert_called_once()
        mock_record_collection.assert_called_once()
        mock_create_sync_mappings.assert_called_once()
        mock_compare_tags.assert_called_once()
        mock_filter_path_mappings.assert_called_once()
        mock_run_sync_mappings.assert_called_once()
        
    def create_mock_file_mapping(self, index: int) -> tuple[str, str]:
        create_mock_path: Callable[[str, int], str] = lambda p, n: os.path.join(p, f"mock_file_{n}")
        return (create_mock_path(MOCK_INPUT_DIR, index), create_mock_path(MOCK_OUTPUT_DIR, index))
