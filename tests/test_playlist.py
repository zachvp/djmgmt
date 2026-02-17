import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch, mock_open
from dataclasses import dataclass

from djmgmt import playlist
from djmgmt.library import TrackMetadata

class TestFindColumn(unittest.TestCase):
    def setUp(self) -> None:
        '''Set up test fixtures.'''
        self.mock_path = '/mock/playlist.txt'

    @staticmethod
    def _format_columns(data: list[str]) -> str:
        '''Formats a list of column names into a tab-separated header line.

        Args:
            data: List of column names.

        Returns:
            A tab-separated string with a trailing newline.
        '''
        return '\t'.join(data) + '\n'

    @patch('builtins.open', new_callable=mock_open, read_data=_format_columns(['#', 'Artist', 'Genre', 'BPM']))
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_find_column_single_word_header(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests finding a single-word column header.'''

        self.assertEqual(playlist.find_column(self.mock_path, '#'), 0)
        self.assertEqual(playlist.find_column(self.mock_path, 'Artist'), 1)
        self.assertEqual(playlist.find_column(self.mock_path, 'Genre'), 2)
        self.assertEqual(playlist.find_column(self.mock_path, 'BPM'), 3)

    @patch('builtins.open', new_callable=mock_open, read_data=_format_columns(['#', 'Track Title', 'Date Added', 'DJ Play Count']))
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_find_column_multi_word_header(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests finding a multi-word column header.'''
        
        self.assertEqual(playlist.find_column(self.mock_path, '#'), 0)
        self.assertEqual(playlist.find_column(self.mock_path, 'Track Title'), 1)
        self.assertEqual(playlist.find_column(self.mock_path, 'Date Added'), 2)
        self.assertEqual(playlist.find_column(self.mock_path, 'DJ Play Count'), 3)

    @patch('builtins.open', new_callable=mock_open, read_data=_format_columns(['#', 'Track Title', 'BPM', 'Artist', 'Genre', 'Date Added', 'Time', 'Key', 'DJ Play Count']))
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_find_column_mixed_headers(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests finding columns with both single and multi-word headers.'''
        
        self.assertEqual(playlist.find_column(self.mock_path, '#'), 0)
        self.assertEqual(playlist.find_column(self.mock_path, 'Track Title'), 1)
        self.assertEqual(playlist.find_column(self.mock_path, 'BPM'), 2)
        self.assertEqual(playlist.find_column(self.mock_path, 'Artist'), 3)
        self.assertEqual(playlist.find_column(self.mock_path, 'Genre'), 4)
        self.assertEqual(playlist.find_column(self.mock_path, 'Date Added'), 5)
        self.assertEqual(playlist.find_column(self.mock_path, 'Time'), 6)
        self.assertEqual(playlist.find_column(self.mock_path, 'Key'), 7)
        self.assertEqual(playlist.find_column(self.mock_path, 'DJ Play Count'), 8)

    @patch('builtins.print')
    @patch('builtins.open', new_callable=mock_open, read_data=_format_columns(['#', 'Artist', 'Genre']))
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_find_column_not_found(self, mock_encoding: MagicMock, mock_file_open: MagicMock, mock_print: MagicMock) -> None:
        '''Tests that an error is returned and printed when column is not found.'''

        self.assertEqual(playlist.find_column(self.mock_path, 'NonExistent'), -1)
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn('error', call_args.lower())
        self.assertIn('NonExistent', call_args)

class TestExtract(unittest.TestCase):
    ALL_FIELDS = ['1\tTest Track\tTest Artist\tHouse']
    ALL_COLUMNS = [0, 1, 2, 3]  # number, title, artist, genre
    
    def setUp(self) -> None:
        '''Set up test fixtures.'''
        self.mock_path_tsv = '/mock/playlist.tsv'
        self.mock_path_txt = '/mock/playlist.txt'
        self.mock_path_csv = '/mock/playlist.csv'

    @patch('djmgmt.playlist.extract_tsv')
    @patch('djmgmt.playlist.find_column')
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_tsv_all_fields_explicit(self, mock_encoding: MagicMock, mock_find_column: MagicMock, mock_extract_tsv: MagicMock) -> None:
        '''Tests extracting all fields from a TSV file with explicit arguments.'''
        # set up mocks
        mock_find_column.side_effect = TestExtract.ALL_COLUMNS
        mock_extract_tsv.return_value = TestExtract.ALL_FIELDS

        # call test target
        result = playlist.extract(self.mock_path_tsv, True, True, True, True)

        # assert expectations
        self.assertListEqual(result, TestExtract.ALL_FIELDS)
        mock_extract_tsv.assert_called_once_with(self.mock_path_tsv, TestExtract.ALL_COLUMNS)

    @patch('djmgmt.playlist.extract_tsv')
    @patch('djmgmt.playlist.find_column')
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_txt_all_fields_explicit(self, mock_encoding: MagicMock, mock_find_column: MagicMock, mock_extract_tsv: MagicMock) -> None:
        '''Tests extracting all fields from a TXT file with explicit arguments.'''
        # set up mocks
        mock_find_column.side_effect = TestExtract.ALL_COLUMNS
        mock_extract_tsv.return_value = TestExtract.ALL_FIELDS

        # call test target
        result = playlist.extract(self.mock_path_txt, True, True, True, True)

        # assert expectations
        self.assertListEqual(result, TestExtract.ALL_FIELDS)
        mock_extract_tsv.assert_called_once_with(self.mock_path_txt, TestExtract.ALL_COLUMNS)

    @patch('djmgmt.playlist.extract_csv')
    @patch('djmgmt.playlist.find_column')
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_csv_all_fields_explicit(self, mock_encoding: MagicMock, mock_find_column: MagicMock, mock_extract_csv: MagicMock) -> None:
        '''Tests extracting specific fields from a CSV file.'''
        # set up mocks
        mock_find_column.side_effect = TestExtract.ALL_COLUMNS
        mock_extract_csv.return_value = TestExtract.ALL_FIELDS

        # call test target
        result = playlist.extract(self.mock_path_csv, True, True, True, True)

        # assert expectations
        self.assertListEqual(result, TestExtract.ALL_FIELDS)
        mock_extract_csv.assert_called_once_with(self.mock_path_csv, TestExtract.ALL_COLUMNS)

    @patch('djmgmt.playlist.extract_tsv')
    @patch('djmgmt.playlist.find_column')
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_all_fields_implicit(self, mock_encoding: MagicMock, mock_find_column: MagicMock, mock_extract_tsv: MagicMock) -> None:
        '''Tests that all fields are extracted when no options are specified.'''
        # set up mocks
        mock_find_column.side_effect = TestExtract.ALL_COLUMNS
        mock_extract_tsv.return_value = TestExtract.ALL_FIELDS

        # call test target
        result = playlist.extract(self.mock_path_tsv, False, False, False, False)

        # assert expectations
        self.assertListEqual(result, TestExtract.ALL_FIELDS)
        mock_extract_tsv.assert_called_once_with(self.mock_path_tsv, TestExtract.ALL_COLUMNS)

    @patch('builtins.print')
    @patch('sys.exit')
    @patch('djmgmt.playlist.find_column')
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_unsupported_extension(self, mock_encoding: MagicMock, mock_find_column: MagicMock, mock_exit: MagicMock, mock_print: MagicMock) -> None:
        '''Tests that an error is raised for unsupported file extensions.'''
        # set up mocks
        mock_find_column.side_effect = TestExtract.ALL_COLUMNS
        mock_path_invalid = '/mock/playlist.xyz'

        # call test target
        with self.assertRaisesRegex(ValueError, 'Unsupported extension: .xyz'):
            playlist.extract(mock_path_invalid, True, True, True, True)

class TestExtractTSV(unittest.TestCase):
    @dataclass(frozen=True)
    class MockTSV:
        headers : list[str]
        rows    : list[list[str]]
        
        def format(self) -> str:
            '''Formats headers and rows into a tab-separated playlist file format.

            Returns:
                A tab-separated string with headers and rows, each ending with newline.
            '''
            lines = ['\t'.join(self.headers)]
            for row in self.rows:
                lines.append('\t'.join(row))
            return '\n'.join(lines) + '\n'
        
        def get_lines(self) -> list[str]:
            '''Corresponds to file content of a TSV accessed via readlines().'''
            return self.format().splitlines(keepends=True)
    
    def create_mock_data(self) -> MockTSV:
        '''Creates an in-memory representation of a playlist TSV file.'''
        headers = ['#', 'Track Title', 'Artist', 'BPM', 'Genre', 'Key']
        rows = [
            ['1', 'Test Track 1', 'Artist A', '120.00', 'House', '5A'],
            ['2', 'Test Track 2', 'Artist B', '128.00', 'Techno', '3A']
        ]
        return TestExtractTSV.MockTSV(headers, rows)
    
    def setUp(self) -> None:
        '''Set up test fixtures.'''
        self.mock_path = '/mock/playlist.tsv'
        self.mock_data = self.create_mock_data()

    @patch('builtins.open', new_callable=mock_open)
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_tsv_all_columns(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests extracting all columns from a TSV file.'''
        # set up mock data
        mock_file_open.return_value.readlines.return_value = self.mock_data.get_lines()

        # call test target
        result = playlist.extract_tsv(self.mock_path, [0, 1, 2, 3, 4, 5])

        # assert expectations
        
        expected = ['\t'.join(self.mock_data.headers)] + ['\t'.join(row) for row in self.mock_data.rows]
        self.assertListEqual(result, expected)

    @patch('builtins.open', new_callable=mock_open)
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_tsv_specific_columns(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests extracting specific columns from a TSV file.'''
        # set up mock data
        mock_file_open.return_value.readlines.return_value = self.mock_data.get_lines()

        # call test target - extract only track title and artist (columns 1, 2)
        result = playlist.extract_tsv(self.mock_path, [1, 2])

        # assert expectations
        expected = [
            'Track Title\tArtist',
            'Test Track 1\tArtist A',
            'Test Track 2\tArtist B'
        ]
        self.assertListEqual(result, expected)

    @patch('builtins.open', new_callable=mock_open)
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_tsv_single_column(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests extracting a single column from a TSV file.'''
        # set up mock data
        mock_file_open.return_value.readlines.return_value = self.mock_data.get_lines()

        # call test target - extract only artist (column 2)
        result = playlist.extract_tsv(self.mock_path, [2])

        # assert expectations
        expected = [
            'Artist',
            'Artist A',
            'Artist B'
        ]
        self.assertListEqual(result, expected)

    @patch('builtins.open', new_callable=mock_open)
    @patch('djmgmt.common.get_encoding', return_value='utf-8')
    def test_extract_tsv_empty_lines_filtered(self, mock_encoding: MagicMock, mock_file_open: MagicMock) -> None:
        '''Tests that empty lines are filtered out from the output.'''
        # set up mock data with empty lines
        # set up mock data
        headers = ['#', 'Track Title', 'Artist', 'BPM', 'Genre', 'Key']
        rows = [
            ['1', 'Test Track 1', 'Artist A'],
            ['', '', ''],
            ['2', 'Test Track 2', 'Artist B']
        ]
        mock_data = TestExtractTSV.MockTSV(headers, rows)
        mock_file_open.return_value.readlines.return_value = mock_data.get_lines()

        # call test target
        result = playlist.extract_tsv(self.mock_path, [0, 1, 2])

        # assert expectations - empty line should be filtered
        expected = [
            '#\tTrack Title\tArtist',
            '1\tTest Track 1\tArtist A',
            '2\tTest Track 2\tArtist B'
        ]
        self.assertListEqual(result, expected)

# XML fixtures for M3U8 and playlist node tests
COLLECTION_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="2">
        <TRACK TrackID="1" Name="Track One" Artist="Artist A" Album="Album A"
               Location="file://localhost/music/track1.aiff" DateAdded="2025-05-20" TotalTime="300"/>
        <TRACK TrackID="2" Name="Track Two" Artist="Artist B" Album="Album B"
               Location="file://localhost/music/track2.aiff" DateAdded="2025-05-21" TotalTime="240"/>
    </COLLECTION>
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
    '''Tests for playlist._find_playlist_node.'''

    def setUp(self) -> None:
        self.root = ET.fromstring(COLLECTION_XML)

    def test_nested_path(self) -> None:
        '''Tests finding a nested playlist node via dot-separated path.'''
        node = playlist._find_playlist_node(self.root, 'dynamic.unplayed')

        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.get('Name'), 'unplayed')
        self.assertEqual(len(node.findall('TRACK')), 2)

    def test_flat_path(self) -> None:
        '''Tests finding a top-level playlist node.'''
        node = playlist._find_playlist_node(self.root, 'flat_playlist')

        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.get('Name'), 'flat_playlist')

    def test_not_found(self) -> None:
        '''Tests that None is returned for a nonexistent playlist path.'''
        node = playlist._find_playlist_node(self.root, 'nonexistent.path')

        self.assertIsNone(node)

    def test_partial_path_not_found(self) -> None:
        '''Tests that None is returned when first segment matches but second does not.'''
        node = playlist._find_playlist_node(self.root, 'dynamic.nonexistent')

        self.assertIsNone(node)

    def test_no_playlists_root(self) -> None:
        '''Tests that None is returned when PLAYLISTS/ROOT is missing.'''
        root = ET.fromstring('<DJ_PLAYLISTS><COLLECTION/></DJ_PLAYLISTS>')

        node = playlist._find_playlist_node(root, 'dynamic.unplayed')

        self.assertIsNone(node)


class TestBuildNavidromePath(unittest.TestCase):
    '''Tests for playlist._build_navidrome_path.'''

    def test_success(self) -> None:
        '''Tests building a valid Navidrome path from track metadata.'''
        metadata = TrackMetadata(
            title='Track One', artist='Artist A', album='Album A',
            path='/music/track1.aiff', date_added='2025-05-20', total_time='300'
        )

        result = playlist._build_navidrome_path(metadata, '/media/SOL/music')

        self.assertEqual(result, '/media/SOL/music/2025/05 may/20/track1.mp3')

    def test_missing_date_added(self) -> None:
        '''Tests that None is returned when date_added is empty.'''
        metadata = TrackMetadata(
            title='Track One', artist='Artist A', album='Album A',
            path='/music/track1.aiff', date_added='', total_time='300'
        )

        result = playlist._build_navidrome_path(metadata, '/media/SOL/music')

        self.assertIsNone(result)

    def test_strips_question_marks(self) -> None:
        '''Tests that question marks are stripped from filenames for exFAT compatibility.'''
        metadata = TrackMetadata(
            title='Track?', artist='Artist A', album='Album A',
            path='/music/track?.aiff', date_added='2025-05-20', total_time='300'
        )

        result = playlist._build_navidrome_path(metadata, '/media/SOL/music')

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result, '/media/SOL/music/2025/05 may/20/track.mp3')

    def test_extension_changed_to_mp3(self) -> None:
        '''Tests that the file extension is always changed to .mp3.'''
        metadata = TrackMetadata(
            title='Track', artist='Artist', album='Album',
            path='/music/track.flac', date_added='2025-01-15', total_time='200'
        )

        result = playlist._build_navidrome_path(metadata, '/media/SOL/music')

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.endswith('.mp3'))


class TestGenerateM3U8(unittest.TestCase):
    '''Tests for playlist.generate_m3u8.'''

    @patch('djmgmt.playlist._build_navidrome_path')
    @patch('djmgmt.library.extract_track_metadata_by_id')
    @patch('xml.etree.ElementTree.parse')
    def test_success(self,
                     mock_parse: MagicMock,
                     mock_extract: MagicMock,
                     mock_build_path: MagicMock) -> None:
        '''Tests successful M3U8 generation with mocked helpers.'''
        # Setup XML parse mock
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring(COLLECTION_XML)
        mock_parse.return_value = mock_tree

        # Setup metadata extraction
        mock_extract.side_effect = [
            TrackMetadata('Track One', 'Artist A', 'Album A', '/music/track1.aiff', '2025-05-20', '300'),
            TrackMetadata('Track Two', 'Artist B', 'Album B', '/music/track2.aiff', '2025-05-21', '240'),
        ]
        mock_build_path.side_effect = [
            '/media/SOL/music/2025/05 may/20/track1.mp3',
            '/media/SOL/music/2025/05 may/21/track2.mp3',
        ]

        # Call with dry_run to avoid file writes
        result = playlist.generate_m3u8('/mock/collection.xml', 'dynamic.unplayed', '/mock/output.m3u8', dry_run=True)

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], '/media/SOL/music/2025/05 may/20/track1.mp3')
        self.assertEqual(result[1], '/media/SOL/music/2025/05 may/21/track2.mp3')
        self.assertEqual(mock_extract.call_count, 2)
        self.assertEqual(mock_build_path.call_count, 2)

    @patch('xml.etree.ElementTree.parse')
    def test_error_no_collection_node(self, mock_parse: MagicMock) -> None:
        '''Tests that empty list is returned when COLLECTION node is missing.'''
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring('<DJ_PLAYLISTS></DJ_PLAYLISTS>')
        mock_parse.return_value = mock_tree

        result = playlist.generate_m3u8('/mock/collection.xml', 'dynamic.unplayed', '/mock/output.m3u8')

        self.assertListEqual(result, [])

    @patch('xml.etree.ElementTree.parse')
    def test_error_playlist_not_found(self, mock_parse: MagicMock) -> None:
        '''Tests that empty list is returned when playlist path is not found.'''
        xml = '''<DJ_PLAYLISTS>
            <COLLECTION Entries="0"/>
            <PLAYLISTS><NODE Type="0" Name="ROOT" Count="0"/></PLAYLISTS>
        </DJ_PLAYLISTS>'''
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring(xml)
        mock_parse.return_value = mock_tree

        result = playlist.generate_m3u8('/mock/collection.xml', 'nonexistent', '/mock/output.m3u8')

        self.assertListEqual(result, [])

    @patch('djmgmt.playlist._build_navidrome_path')
    @patch('djmgmt.library.extract_track_metadata_by_id')
    @patch('xml.etree.ElementTree.parse')
    def test_skips_tracks_with_no_metadata(self,
                                            mock_parse: MagicMock,
                                            mock_extract: MagicMock,
                                            mock_build_path: MagicMock) -> None:
        '''Tests that tracks with missing metadata are skipped.'''
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring(COLLECTION_XML)
        mock_parse.return_value = mock_tree

        # First track returns None metadata, second succeeds
        mock_extract.side_effect = [
            None,
            TrackMetadata('Track Two', 'Artist B', 'Album B', '/music/track2.aiff', '2025-05-21', '240'),
        ]
        mock_build_path.return_value = '/media/SOL/music/2025/05 may/21/track2.mp3'

        result = playlist.generate_m3u8('/mock/collection.xml', 'dynamic.unplayed', '/mock/output.m3u8', dry_run=True)

        self.assertEqual(len(result), 1)
        # _build_navidrome_path should only be called for the track with metadata
        mock_build_path.assert_called_once()

    @patch('djmgmt.playlist._build_navidrome_path')
    @patch('djmgmt.library.extract_track_metadata_by_id')
    @patch('xml.etree.ElementTree.parse')
    def test_skips_tracks_with_no_navidrome_path(self,
                                                  mock_parse: MagicMock,
                                                  mock_extract: MagicMock,
                                                  mock_build_path: MagicMock) -> None:
        '''Tests that tracks with no Navidrome path are skipped.'''
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring(COLLECTION_XML)
        mock_parse.return_value = mock_tree

        mock_extract.side_effect = [
            TrackMetadata('Track One', 'Artist A', 'Album A', '/music/track1.aiff', '2025-05-20', '300'),
            TrackMetadata('Track Two', 'Artist B', 'Album B', '/music/track2.aiff', '2025-05-21', '240'),
        ]
        # First returns None path, second succeeds
        mock_build_path.side_effect = [None, '/media/SOL/music/2025/05 may/21/track2.mp3']

        result = playlist.generate_m3u8('/mock/collection.xml', 'dynamic.unplayed', '/mock/output.m3u8', dry_run=True)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], '/media/SOL/music/2025/05 may/21/track2.mp3')

    @patch('builtins.open', new_callable=mock_open)
    @patch('djmgmt.playlist._build_navidrome_path')
    @patch('djmgmt.library.extract_track_metadata_by_id')
    @patch('xml.etree.ElementTree.parse')
    def test_writes_m3u8_file(self,
                               mock_parse: MagicMock,
                               mock_extract: MagicMock,
                               mock_build_path: MagicMock,
                               mock_file_open: MagicMock) -> None:
        '''Tests that M3U8 content is written to file when not in dry_run mode.'''
        mock_tree = MagicMock()
        mock_tree.getroot.return_value = ET.fromstring(COLLECTION_XML)
        mock_parse.return_value = mock_tree

        mock_extract.side_effect = [
            TrackMetadata('Track One', 'Artist A', 'Album A', '/music/track1.aiff', '2025-05-20', '300'),
            TrackMetadata('Track Two', 'Artist B', 'Album B', '/music/track2.aiff', '2025-05-21', '240'),
        ]
        mock_build_path.side_effect = [
            '/media/SOL/music/2025/05 may/20/track1.mp3',
            '/media/SOL/music/2025/05 may/21/track2.mp3',
        ]

        result = playlist.generate_m3u8('/mock/collection.xml', 'dynamic.unplayed', '/mock/output.m3u8', dry_run=False)

        self.assertEqual(len(result), 2)
        mock_file_open.assert_called_once_with('/mock/output.m3u8', 'w', encoding='utf-8')

        # Verify written content includes M3U8 header and tracks
        written_content = mock_file_open().write.call_args[0][0]
        self.assertIn('#EXTM3U', written_content)
        self.assertIn('#PLAYLIST:dynamic_unplayed', written_content)
        self.assertIn('/media/SOL/music/2025/05 may/20/track1.mp3', written_content)
        self.assertIn('#EXTINF:300,Artist A - Track One', written_content)

    @patch('xml.etree.ElementTree.parse')
    def test_error_parse_exception(self, mock_parse: MagicMock) -> None:
        '''Tests that empty list is returned on XML parse error.'''
        mock_parse.side_effect = ET.ParseError('bad xml')

        result = playlist.generate_m3u8('/mock/bad.xml', 'dynamic.unplayed', '/mock/output.m3u8')

        self.assertListEqual(result, [])
