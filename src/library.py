'''
# Summary
Given a Rekordbox music collection, moves each file to a directory path that corresponds to the date it was added.

For example, if the music library file 'TrackA.aiff' has a corresponding 'DateAdded'
attribute of '01/02/23 (Jan 2, 2023)', the new path will be
    '/library_root/2023/01 january/02/Artist/Album/TrackA.aiff'

## Assumptions
* The music library source files are in a flat directory structure. Any tracks in subfolders will be ignored.
* The XML collection file paths point to this flat music library.
'''

import sys
import os
import shutil
import xml.etree.ElementTree as ET
import argparse
import logging
from urllib.parse import unquote

from . import constants
from . import common

# TODO: breakdown of tracks included in recorded sets
# TODO: breakdown of tracks excluded from recorded sets

# command support
class Namespace(argparse.Namespace):
    # required
    function: str
    xml_collection_path: str
    
    # optional
    output_path: str
    root_path: str
    metadata_path: bool
    interactive: bool
    force: bool
    
    # Script functions
    FUNCTION_DATE_PATHS = 'date_paths'
    FUNCTION_IDENTIFIERS = 'identifiers'
    FUNCTION_FILENAMES = 'filenames'
    FUNCTIONS = {FUNCTION_DATE_PATHS, FUNCTION_IDENTIFIERS, FUNCTION_FILENAMES}

def parse_args(valid_functions: set[str]) -> type[Namespace]:
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str, help=f"The script function to run. One of: {valid_functions}.")
    parser.add_argument('xml_collection_path', type=str, help='The rekordbox library path containing the DateAdded history.')
    
    parser.add_argument('--output-path', '-o', type=str, help='Write to this file path.')
    parser.add_argument('--root-path', '-p', type=str, help='The path to use in place of the root path defined in the rekordbox xml.')
    parser.add_argument('--metadata-path', '-m', action='store_true', help='Include artist and album in path.')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run script in interactive mode.')
    parser.add_argument('--force', action='store_true', help='Skip all interaction safeguards and run the script.')

    args = parser.parse_args(namespace=Namespace)

    if args.function not in valid_functions:
        parser.error(f"invalid parameter '{args.function}'")

    return args

# helper functions
def date_path(date: str, mapping: dict[int, str]) -> str:
    '''Returns a date-formatted directory path string. e.g:
        YYYY/MM MONTH_NAME / DD
        2024/ 01 january / 02
    
    Arguments:
        date -- The YYYY-MM-DD date string to transform
        mapping -- The human-readable definitions for the months
    '''
    year, month, day = date.split('-')

    return f"{year}/{month} {mapping[int(month)]}/{day}"

def full_path(node: ET.Element, library_root: str, mapping: dict[int, str], include_metadata: bool=False) -> str:
    '''Returns a formatted directory path based on the node's DateAdded field.

    Arguments:
        node    -- The XML collection track data
        pivot   -- The substring between the collection root and the rest of the track directory path
        mapping -- The human-readable months
        include_metadata -- Whether the path should include album and artist metadata
    '''
    # path components
    date = node.attrib[constants.ATTR_DATE_ADDED]
    path_components = os.path.split(node.attrib[constants.ATTR_PATH].lstrip(library_root))
    subpath_date = date_path(date, mapping)
    
    # construct the path
    path = os.path.join('/', path_components[0], subpath_date)
    if include_metadata:
        artist = node.attrib[constants.ATTR_ARTIST]
        album = node.attrib[constants.ATTR_ALBUM]
        if not artist:
            artist = constants.UNKNOWN_ARTIST
        if not album:
            album = constants.UNKNOWN_ALBUM
        path = os.path.join(path, artist, album)   # append metadata
    path = os.path.join(path, path_components[-1]) # append file name
    return path

def collection_path_to_syspath(path: str) -> str:
    '''Transforms the given XML collection path to a directory path.

    Arguments:
        path -- The URL-like collection path
    '''
    syspath = unquote(path).lstrip(constants.REKORDBOX_ROOT)
    if not syspath.startswith(os.path.sep):
        syspath = os.path.sep + syspath
    return syspath

def swap_root(path: str, old_root: str, root: str) -> str:
    '''Returns the given path with its root replaced.

    Arguments:
        path -- The directory path
        root -- The new root to use
    '''
    if not root.endswith(os.path.sep):
        root += os.path.sep

    root = path.replace(old_root, root)

    return root

def load_collection(path: str) -> ET.Element:
    '''Returns the root node of the XML collection at `path`.'''
    message = f"unable to parse collection at '{path}'"
    try:
        collection = ET.parse(path)
    except ET.ParseError as e:
        logging.error(f"{message}:\n{e}")
        raise
    assert collection is not None, message
    return collection.getroot()

def find_collection_backup(backup_dir: str) -> str:
    '''Finds the path for the most recently modified collection.xml file.'''
    paths = common.collect_paths(backup_dir, filter={'.xml'})
    return max(paths, key=os.path.getmtime) if paths else ''
    
def find_node(root: ET.Element, xpath: str) -> ET.Element:
    '''Arguments:
        collection -- The XML collection root.
        xpath      -- The XPath of the node to find.
    Returns:
        The XML node according to the given arguments.
    '''
    node = root.find(xpath)
    if node is None:
        raise ValueError(f"Unable to find node for XPath '{xpath}' in '{root.tag}'")
    return node

def filter_path_mappings(mappings: list[tuple[str, str]], collection: ET.Element, playlist_xpath: str) -> list[tuple[str, str]]:
    # output data
    filtered = []
    
    # find the collection node
    collection_node = collection.find(constants.XPATH_COLLECTION)
    if collection_node is None:
        return filtered
    
    # find the playlist node
    playlist = collection.find(playlist_xpath)
    if playlist is None:
        return filtered
    
    # extract track keys from the playlist
    track_keys = set()
    for track in playlist:
        key = track.get(constants.ATTR_TRACK_KEY)
        if key:
            track_keys.add(key)
    
    # extract playlist track system paths from the collection
    track_paths = set()
    for track in collection_node:
        track_id = track.get(constants.ATTR_TRACK_ID)
        path = track.get(constants.ATTR_PATH)
        if track_id and path and track_id in track_keys:
            track_paths.add(collection_path_to_syspath(path))
    
    # filter the mappings according to the track paths
    filtered = [mapping for mapping in mappings if mapping[0] in track_paths]
    return filtered

# Dev functions
def dev_debug():
    test_str =\
    '''
        <TRACK TrackID="109970693" Name="花と鳥と山" Artist="haircuts for men" Composer="" Album="京都コネクション" Grouping="" Genre="Lounge/Ambient" Kind="AIFF File" Size="84226278" TotalTime="476" DiscNumber="0" TrackNumber="5" Year="2023" AverageBpm="134.00" DateAdded="2023-04-27" BitRate="1411" SampleRate="44100" Comments="8A - 1" PlayCount="1" Rating="0" Location="file://localhost/Volumes/USR-MUSIC/DJing/haircuts%20for%20men%20-%20%e8%8a%b1%e3%81%a8%e9%b3%a5%e3%81%a8%e5%b1%b1.aiff" Remixer="" Tonality="8A" Label="" Mix="">
          <TEMPO Inizio="0.126" Bpm="134.00" Metro="4/4" Battito="1" />
        </TRACK>'''
    t = ET.fromstring(test_str)
    logging.debug(t.tag)

    u = full_path(t, '/USR-MUSIC/DJing/', constants.MAPPING_MONTH)
    logging.debug(u)

# Primary functions
def generate_date_paths_cli(args: type[Namespace]) -> list[tuple[str, str]]:
    collection = load_collection(args.xml_collection_path)
    collection = find_node(collection, constants.XPATH_COLLECTION)
    return generate_date_paths(collection, args.root_path, metadata_path=args.metadata_path)

# TODO: update to handle '/' character in metadata path (e.g. a/jus/ted)
# TODO: add test coverage for URL-encoded paths (i.e. Rekordbox file location)
def generate_date_paths(collection: ET.Element,
                        root_path: str,
                        playlist_ids: set[str] = set(),
                        metadata_path: bool = False) -> list[tuple[str, str]]:
    '''Generates a list of path mappings for a flat source structure.
    Each item maps from the original source path to a new date-structured path.
    The new path combines the root_path with the date context (year/month/day), optional metadata, and filename.
    '''
    paths: list[tuple[str, str]] = []

    for node in collection:
        # check if track file is in expected library folder
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_PATH])
        if constants.REKORDBOX_ROOT not in node.attrib[constants.ATTR_PATH]:
            logging.warning(f"unexpected path {node_syspath}, will skip")
            continue
        
        # check if a playlist is provided
        if playlist_ids and node.attrib[constants.ATTR_TRACK_ID] not in playlist_ids:
            logging.debug(f"skip non-playlist track: '{node_syspath}'")
            continue
        
        # build each entry for the old and new path
        track_path_old = node_syspath
        track_path_new = full_path(node, constants.REKORDBOX_ROOT, constants.MAPPING_MONTH, include_metadata=metadata_path)
        track_path_new = collection_path_to_syspath(track_path_new)
        
        context = common.find_date_context(track_path_new)
        if context:
            # remove path before the date context and replace with the root path
            track_path_new = common.remove_subpath(track_path_new, root_path, context[1])
        
        paths.append((track_path_old, track_path_new))
    
    return paths

def get_pipe_output(structure: list[tuple[str, str]]) -> str:
    output = ''
    for item in structure:
        output += f"{item[0].strip()}{constants.FILE_OPERATION_DELIMITER}{item[1].strip()}\n"
    return output.strip()

def move_files(args: type[Namespace], path_mappings: list[str]) -> None:
    '''Moves files according to the paths input mapping.'''
    for mapping in path_mappings:
        source, dest = mapping.split(constants.FILE_OPERATION_DELIMITER)

        # interactive session
        if args.interactive:
            choice = input(f"info: will move file from '{source}' to '{dest}', continue? [Y/n]")
            if len(choice) > 0 and choice not in 'Yy':
                logging.info("exit: user quit")
                sys.exit()

        # get the destination file's directory
        dest_dir =  '/'.join(dest.split('/')[:-1])

        # validate
        if not os.path.exists(source):
            logging.info(f"skip: source path '{source}' does not exist")
            continue
        if os.path.exists(dest):
            logging.info(f"skip: destination path '{dest}' exists")
            continue

        # create dir if it doesn't exist
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        shutil.move(source, dest)

def collect_identifiers(collection: ET.Element, playlist_ids: set[str] = set()) -> list[str]:
    from .tags import Tags
    
    identifiers: list[str] = []
    
    for node in collection:
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_PATH])
        # check if a playlist is provided
        if playlist_ids and node.attrib[constants.ATTR_TRACK_ID] not in playlist_ids:
            logging.debug(f"skip non-playlist track: '{node_syspath}'")
            continue
        # load track tags, check for errors
        tags = Tags.load(node_syspath)
        if not tags or not tags.artist or not tags.title:
            logging.error(f"incomplete tags: {tags}")
            continue
        
        identifiers.append(tags.basic_identifier())
    
    return identifiers

def collect_filenames(collection: ET.Element, playlist_ids: set[str] = set()) -> list[str]:
    names: list[str] = []
    for node in collection:
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_PATH])
        # check if a playlist is provided
        if playlist_ids and node.attrib[constants.ATTR_TRACK_ID] not in playlist_ids:
            logging.debug(f"skip non-playlist track: '{node_syspath}'")
            continue
        name = os.path.basename(node_syspath)
        name = os.path.splitext(name)[0]
        names.append(name)
    return names

# Main
if __name__ == '__main__':
    # setup
    common.configure_log(level=logging.DEBUG, path=__file__)
    script_args = parse_args(Namespace.FUNCTIONS)

    if script_args.root_path:
        logging.info(f"args root path: '{script_args.root_path}'")

    if script_args.function == Namespace.FUNCTION_DATE_PATHS:
        print(get_pipe_output(generate_date_paths_cli(script_args)))
    elif script_args.function == Namespace.FUNCTION_IDENTIFIERS or script_args.function == Namespace.FUNCTION_FILENAMES:
        tree = load_collection(script_args.xml_collection_path)
        pruned = find_node(tree, constants.XPATH_PRUNED)
        collection = find_node(tree, constants.XPATH_COLLECTION)
        
        # collect the playlist IDs
        playlist_ids: set[str] = set()
        for track in pruned:
            playlist_ids.add(track.attrib[constants.ATTR_TRACK_KEY])
        if script_args.function == Namespace.FUNCTION_IDENTIFIERS:
            items = collect_identifiers(collection, playlist_ids)
        else:
            items = collect_filenames(collection, playlist_ids)
        
        items.sort()
        lines = [f"{id}\n" for id in items]
        with open(script_args.output_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
