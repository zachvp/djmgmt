import unittest
from unittest.mock import MagicMock, patch, mock_open
from dataclasses import dataclass

from djmgmt import playlist

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
