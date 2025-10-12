'''
# Summary
* Standardizes all music files in a given directory to an artist/album or year/month/day/artist/album directory structure
    according to music file metadata and today's date.
* Validates a given directory to match the expected directory structure.

# Example
For a directory 'top/':
    top/parent/audio.file -> top/parent/artist/album/audio.file
                            or
    top/parent/audio.file -> top/parent/year/month/day/artist/album/audio.file
'''

from datetime import datetime
import argparse
import os
import shutil
import logging

from .tags import Tags
from . import music
from . import constants

# Constants
FUNCTION_VALIDATE = 'validate'
FUNCTION_SORT = 'sort'
EXPECTED_DEPTH = 6

# Helper functions
def clean_dirname(dirname: str, replacements: dict[str, str]) -> str:
    '''Cleans any dirty substrings in `dirname`.

    Arguments
    dirname -- the directory string to clean
    replacements -- key: dirty string, value: clean string
    '''
    output = dirname

    for key, value in replacements.items():
        if key in output:
            output = output.replace(key, value)

    return output.strip()

def clean_dirname_fat32(dirname: str) -> str:
    '''cleans according to Fat32 specs
    source: https://stackoverflow.com/questions/4814040/allowed-characters-in-filename
    '''
    replacements: dict[str,str] = {
        '\\' : '()',
        '/'  : '&',
        ':'  : '-',
        '*'  : '()',
        '?'  : '()',
        '"'  : '()',
        '<'  : '(',
        '>'  : ')',
        '|'  : '()',
    }

    return clean_dirname(dirname, replacements)

def clean_dirname_simple(dirname: str) -> str:
    '''Cleans reserved directory characters'''
    replacements: dict[str,str] = {
        '/'  : '&',
        ':'  : '-',
    }

    return clean_dirname(dirname, replacements)

def date_path(date: datetime, months: dict[int, str]) -> str:
    '''Returns a directory path that corresponds to today's date. 'YYYY-MM-DD' returns 'YYYY/MM/DD'.
    Example: '2024-01-02' returns 2024/01/02
    '''

    month_index = str(date.month).zfill(2)
    month_name = months[date.month]
    month = f"{month_index} {month_name}"
    day = str(date.day).zfill(2)
    return f"{date.year}/{month}/{day}"

# Primary functions
def sort_hierarchy(source: str, compatibility: bool, date: bool, interactive: bool, months: dict[int, str]) -> None:
    ''' One of the main script functions. Performs an in-place sort of all music files in the args.input directory
    into a standardized 'Artist/Album/Track_File' directory format.

    If the args.date option is passed, today's date is used to construct the start of the modified path.
    So the full path would be 'Year/Month/Day/Artist/Album/Track_File'
    '''
    # scan the input directory
    for working_dir, _, filenames in os.walk(source):
        music.prune(working_dir, [], filenames)

        # scan all filenames
        for filename in filenames:
            filepath = os.path.join(working_dir, filename)

            # filter for music files
            if os.path.splitext(filename)[1] in {'.aiff', '.aif', '.mp3', '.wav'}:
                # read the artist and album
                tags = Tags.load(filepath)
                if tags:
                    # extract and clean up the artist string
                    artist = tags.artist if tags.artist else constants.UNKNOWN_ARTIST
                    artist_raw = artist
                    artist = clean_dirname_simple(artist)
                    if compatibility:
                        artist = clean_dirname_fat32(artist)
                    if artist != artist_raw:
                        logging.info(f"artist '{artist_raw}' contains at least one illegal character, replacing with '{artist}'")

                    # extract and clean up the album string
                    album = tags.album if tags.album else constants.UNKNOWN_ALBUM
                    album_raw = album
                    album = clean_dirname_simple(album)
                    if compatibility:
                        album = clean_dirname_fat32(album)
                    if album != album_raw:
                        logging.info(f"album '{album_raw}' contains at least one illegal character, replacing with '{album}'")

                    # build the output path
                    output_path = working_dir

                    # apply the date option if present
                    if date:
                        logging.info("apply date folder structure")
                        output_path = os.path.join(output_path, date_path(datetime.now(), months))

                    # define the parent path for the music filename and the full output file path
                    parent_path = os.path.join(output_path, artist, album)
                    output_path = os.path.join(parent_path, filename)

                    # skip files that are already in the right place
                    if os.path.exists(output_path):
                        logging.info(f"skip: output path exists: '{output_path}'")
                        continue

                    # check for the interactive option
                    if interactive:
                        choice = input(f"move {filepath} -> {output_path}? [y/N/q]")
                        if choice == 'q':
                            logging.info("user quit")
                            return
                        if choice != 'y':
                            logging.info("skip: user skipped")
                            continue

                    # create the music file's parent directory if needed
                    if not os.path.exists(parent_path):
                        logging.info(f"os.makedirs({parent_path})")
                        os.makedirs(parent_path)

                    # move the current file to the structured path
                    logging.info(f"shutil.move{(filepath, output_path)}")
                    shutil.move(filepath, output_path)
            else:
                # skip non-music files
                logging.info(f"skip: unsupported file: '{filepath}'")

def sort_hierarchy_cli(args: argparse.Namespace, months: dict[int, str]) -> None:
    sort_hierarchy(args.input, args.compatibility, args.date, args.interactive, months)

def validate_hierarchy(source: str, expected_depth: int, months: set[str]) -> list[str]:
    '''One of the main script functions. Validates that all files in the args.input directory
    conform to the expected format.

    Valid path format (relative to music root): '/Year/Month_Index Month_Name/Day/Artist/Album/Music_File'
    '''

    # define the output
    invalid_paths: list[str] = []

    # scan all files in the input directory
    for working_dir, dirs, filenames in os.walk(source):
        if len(filenames) < 1 and len(dirs) < 1:
            # empty directories are invalid
            invalid_paths.append(working_dir)
            logging.info(f"invalid: empty directory: {working_dir}")

        # scan all files
        for filename in filenames:
            # define full path
            filepath = os.path.join(working_dir, filename)

            # check for invalid hidden files
            if filename.startswith('.'):
                logging.info(f"invalid: illegal prefix: '{filename}'")
                invalid_paths.append(filepath)
                continue

            # validate file path depth
            relpath = os.path.relpath(filepath, start=source)
            relpath_split = relpath.split('/')
            if len(relpath_split) != expected_depth:
                logging.info(f"invalid: relative filepath depth: {relpath}; relative depth is: {len(relpath.split('/'))}")
                invalid_paths.append(filepath)
                continue

            # validate the path's year format
            index = 0
            if not relpath_split[index].isdecimal() or len(relpath_split[index]) != 4:
                logging.info(f"invalid: year path component: '{relpath_split[index]}': expect '4-digit year' format")
                invalid_paths.append(filepath)
                continue
            index = 1

            # validate the path's month format
            parts = relpath_split[index].split()
            if len(parts) != 2 or not parts[0].isdecimal() or parts[1] not in months:
                logging.info(f"invalid: month path component: '{relpath_split[index]}': expect '<month_index> <month_name>' format")
                invalid_paths.append(filepath)
                continue
            index = 2

            # validate the path's day format
            if len(relpath_split[index]) != 2 or not relpath_split[index].isdecimal():
                logging.info(f"invalid: day path component: '{relpath_split[index]}': expect '2-digit day' format")
                invalid_paths.append(filepath)
                continue

    return invalid_paths

def validate_hierarchy_cli(args: argparse.Namespace, expected_depth: int, months: set[str]) -> list[str]:
    return validate_hierarchy(args.input, expected_depth, months)

def parse_args(valid_functions: set[str]) -> argparse.Namespace:
    '''Returns the parsed command-line arguments.

    valid_functions -- defines the supported script functions
    

    Required command-line arguments:
    function -- the function to run
    input -- the input path context

    Optional command-line arguments:
    interactive -- run the script interactively, requiring user input to execute each operation
    compatibility -- Run the script for FAT32 compatibility mode
    '''

    # define the supported arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str, help=f"The script function to run. One of: {valid_functions}")
    parser.add_argument('input', type=str, help='The top/root path to scan and organize.')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run the script in interactive mode')
    parser.add_argument('--compatibility', '-c', action='store_true', help='Run the script in compatibility mode -\
        Directory names will be cleaned according to permitted FAT32 path characters.')
    parser.add_argument('--date', '-d', action='store_true', help='Place all files in a date-oriented directory structure.')

    # parse the arguments and clean input
    args = parser.parse_args()
    args.input = os.path.normpath(args.input)

    # check for errors
    if args.function not in valid_functions:
        parser.error(f"invalid function: '{args.function}'")

    return args

# Main
if __name__ == '__main__':
    # script arguments
    script_functions = {FUNCTION_VALIDATE, FUNCTION_SORT}
    script_args = parse_args(script_functions)

    logging.info(f"running function '{script_args.function}'")

    # run the given script function
    if script_args.function == FUNCTION_VALIDATE:
        validate_hierarchy_cli(script_args, EXPECTED_DEPTH, set(constants.MAPPING_MONTH.values()))
    elif script_args.function == FUNCTION_SORT:
        sort_hierarchy_cli(script_args, constants.MAPPING_MONTH)
