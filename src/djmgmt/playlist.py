# extract info from rekordbox playlist export

'''
Format
    Tab-separated
    Fields depend on rekordbox view settings, here is an example line format
        "#   Track Title BPM Artist  Genre   Date Added  Time    Key DJ Play Count"
'''

import argparse
import os
import csv
from typing import Callable

from . import common

# command support
class Namespace(argparse.Namespace):
    # required
    input: str

    # optional
    number: bool
    title: bool
    artist: bool
    genre: bool

def extract_tsv(path: str, fields: list[int]) -> list[str]:
    output = []

    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        rows = file.readlines()
        for row in rows:
            line = row.split('\t')
            output_line = ''
            for f in fields:
                output_line += f"{line[f]}\t"
            output_line = output_line.strip()
            if len(output_line) > 0:
                output.append(output_line)
    return output

def extract_csv(path: str, fields: list[int]) -> list[str]:
    output = []

    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        rows = csv.reader(file)
        for row in rows:
            output_line = ''
            for f in fields:
                output_line += f"{row[f]}\t"
            output_line = output_line.strip()
            if len(output_line) > 0:
                output.append(output_line)
    return output

def parse_args() -> type[Namespace]:
    parser = argparse.ArgumentParser(description="Output each track from a rekordbox-exported playlist.\
        If no options are provided, all fields will exist in the ouptut.")
    parser.add_argument('input', type=str, help='The playlist path.')
    parser.add_argument('--number', '-n', action='store_true', help='Include the track number in the output.')
    parser.add_argument('--title', '-t', action='store_true', help='Include the title in the output.')
    parser.add_argument('--artist', '-a', action='store_true', help='Include the artist in the output.')
    parser.add_argument('--genre', '-g', action='store_true', help='Include the genre in the output.')

    args = parser.parse_args(namespace=Namespace)
    args.input = os.path.normpath(args.input)

    return args

def find_column(path: str, name: str) -> int:
    '''Locate the index of a column by name in a file's header row.

    Args:
        path: Path to the file to read.
        name: Name of the column to find.
    '''
    # Helper functionality and data
    normalize: Callable[[str], str] = lambda s: s.replace(' ', '_')
    headers = {
        '#',
        'Track Title',
        'Genre',
        'Artist',
        'Key',
        'BPM',
        'Time',
        'Date Added',
        'DJ Play Count'
    }
    options = { header : normalize(header) for header in headers }
    columns_processed = []
    
    # Primary search loop
    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        # Core mutable data
        columns = file.readline().split()
        multiword = ''
        
        # Process columns to handle multi-word header names
        for c in columns:
            if c in options:
                columns_processed.append(options[c])
                multiword = ''
            else: 
                multiword += f"{c} "
                if multiword.strip() in options:
                    columns_processed.append(options[multiword.strip()])
                    multiword = ''
    
    # Check for the search column
    search_column = normalize(name)
    try:
        return columns_processed.index(search_column)
    except ValueError:
        print(f"error: unable to find name: '{name}' in path '{path}'")
    return -1

def extract(input_path: str,
            include_number: bool,
            include_title: bool,
            include_artist: bool,
            include_genre: bool) -> list[str]:
    '''Extract and format track information from a rekordbox playlist export file.

    Args:
        input_path: Path to the playlist file (TSV, TXT, or CSV format).
        include_number: Include track number in output.
        include_title: Include track title in output.
        include_artist: Include artist in output.
        include_genre: Include genre in output.
    '''
    number = find_column(input_path, '#')
    title  = find_column(input_path, 'Track Title')
    artist = find_column(input_path, 'Artist')
    genre  = find_column(input_path, 'Genre')

    fields: list[int] = []
    if include_number:
        fields.append(number)
    if include_title:
        fields.append(title)
    if include_artist:
        fields.append(artist)
    if include_genre:
        fields.append(genre)

    # if no options are provided, assume all fields for output
    if len(fields) < 1:
        fields = [number, title, artist, genre]

    extension = os.path.splitext(input_path)[1]

    if extension in {'.tsv', '.txt'}:
        extracted = extract_tsv(input_path, fields)
    elif extension == '.csv':
        extracted = extract_csv(input_path, fields)
    else:
        raise ValueError(f"Unsupported extension: {extension}")

    return extracted

# main
if __name__ == '__main__':
    args = parse_args()
    result = extract(args.input, args.number, args.title, args.artist, args.genre)
    print('\n'.join(result))
