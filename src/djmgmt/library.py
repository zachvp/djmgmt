'''
# Summary
Given a Rekordbox music collection, moves each file to a directory path that corresponds to the date it was added.

For example, if the music library file 'TrackA.aiff' has a corresponding 'DateAdded'
attribute of '01/02/23 (Jan 2, 2023)', the new path will be
    '/library_root/2023/01 january/02/Artist/Album/TrackA.aiff'

# Assumptions
* The music library source files are in a flat directory structure. Any tracks in subfolders will be ignored.
* The XML collection file paths point to this flat music library.
'''

import sys
import os
import shutil
import xml.etree.ElementTree as ET
import argparse
import logging
import uuid
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import quote, unquote

from . import constants
from . import common
from .common import FileMapping
from .tags import Tags

# CLI support
class Namespace(argparse.Namespace):
    '''Command-line arguments for library module.'''

    # Required
    function: str

    # Optional (alphabetical)
    collection: str
    force: bool
    interactive: bool
    metadata_path: bool
    output: str
    root_path: str

    # Function constants
    FUNCTION_DATE_PATHS = 'date_paths'
    FUNCTION_IDENTIFIERS = 'identifiers'
    FUNCTION_FILENAMES = 'filenames'
    FUNCTION_RECORD_DYNAMIC = 'record_dynamic'

    FUNCTIONS = {FUNCTION_DATE_PATHS, FUNCTION_IDENTIFIERS, FUNCTION_FILENAMES, FUNCTION_RECORD_DYNAMIC}

@dataclass
class TrackMetadata:
    '''Represents metadata for a track from the XML collection.'''
    title: str
    artist: str
    album: str
    path: str

@dataclass
class RecordResult:
    '''Results from recording tracks to XML collection.'''
    # TODO: include XML collection path, remove collection_root
    collection_root: ET.Element
    tracks_added: int
    tracks_updated: int

def parse_args(valid_functions: set[str], argv: list[str]) -> Namespace:
    '''Parse command line arguments.

    Args:
        valid_functions: Set of valid function names
        argv: Optional argument list for testing (defaults to sys.argv)
    '''
    parser = argparse.ArgumentParser()

    # Required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(valid_functions))}")

    # Optional: all function parameters (alphabetical)
    parser.add_argument('--collection', '-c', type=str,
                       help='Rekordbox XML collection file path')
    parser.add_argument('--force', action='store_true',
                       help='Skip interaction safeguards and run the script')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Run script in interactive mode')
    parser.add_argument('--metadata-path', '-m', action='store_true',
                       help='Include artist and album in path')
    parser.add_argument('--output', '-o', type=str,
                       help='Output file path')
    parser.add_argument('--root-path', '-p', type=str,
                       help='Path to use in place of root path from XML')

    # Parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # Normalize paths (only if not None)
    common.normalize_arg_paths(args, ['collection', 'output', 'root_path'])

    # Validate function
    if args.function not in valid_functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(valid_functions))}")

    # Function-specific validation
    _validate_function_args(parser, args)

    return args


def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''

    # All functions require --collection
    if not args.collection:
        parser.error(f"'{args.function}' requires --collection")

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
        artist = node.get(constants.ATTR_ARTIST, constants.UNKNOWN_ARTIST)
        album = node.get(constants.ATTR_ALBUM, constants.UNKNOWN_ALBUM)

        # sanitize artist and album for filesystem compatibility
        artist = common.clean_dirname_fat32(artist)
        album = common.clean_dirname_fat32(album)
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

def filter_path_mappings(mappings: list[FileMapping], collection: ET.Element, playlist_xpath: str) -> list[FileMapping]:
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

def extract_track_metadata(collection: ET.Element, source_path: str) -> TrackMetadata | None:
    '''Extracts track metadata from XML collection by file path.

    Args:
        collection: The COLLECTION node element
        source_path: System file path to look up

    Returns:
        TrackMetadata with title, artist, album, path, or None if not found
    '''
    from urllib.parse import quote

    # Convert system path to URL format for XML lookup (pattern from music.py:254)
    file_url = f'{constants.REKORDBOX_ROOT}{quote(source_path, safe="()/")}'

    # Find track in collection
    track_node = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_PATH}="{file_url}"]')

    if track_node is None:
        logging.warning(f'Track not found in collection: {source_path}')
        return None

    return TrackMetadata(
        title=track_node.get(constants.ATTR_TITLE, ''),
        artist=track_node.get(constants.ATTR_ARTIST, ''),
        album=track_node.get(constants.ATTR_ALBUM, ''),
        path=source_path
    )

def get_played_tracks(root: ET.Element) -> list[str]:
    '''Returns a list of TRACK.Key/ID strings for all playlist tracks in the 'mixtapes' folder.'''
    # load XML references
    mixtapes = find_node(root, constants.XPATH_MIXTAPES)
    
    # search for and collect tracks in archive
    played_tracks = []
    existing = set()
    track_nodes = mixtapes.findall(f'.//{constants.TAG_TRACK}')
    for track in track_nodes:
        track_id = track.get(constants.ATTR_TRACK_KEY)
        if track_id not in existing:
            played_tracks.append(track_id)
            existing.add(track_id)
    return played_tracks

def get_unplayed_tracks(root: ET.Element) -> list[str]:
    '''Returns a list of TRACK.Key/ID strings for all pruned tracks NOT in the 'mixtapes' folder.'''
    # load XML references
    pruned = find_node(root, constants.XPATH_PRUNED)
    
    # determine unplayed tracks depending on the played tracks
    unplayed_tracks = []
    played_tracks = set(get_played_tracks(root))
    for track in pruned:
        track_id = track.get(constants.ATTR_TRACK_KEY)
        if not track_id:
            raise ValueError(f"Malformed collection XML: no track ID found for track in '{pruned.tag}'")
        if track_id not in played_tracks:
            unplayed_tracks.append(track_id)
    return unplayed_tracks

def add_played_tracks(collection_root: ET.Element, base_root: ET.Element) -> ET.Element:
    '''Updates the 'dynamic.played' playlist in the base XML root.

    Args:
        collection_root: The input XML root containing the source collection
        base_root: The XML root element to modify

    Returns:
        The modified root element
    '''
    played = get_played_tracks(collection_root)
    return add_playlist_tracks(base_root, played, constants.XPATH_PLAYED)

def add_unplayed_tracks(collection_root: ET.Element, base_root: ET.Element) -> ET.Element:
    '''Updates the 'dynamic.unplayed' playlist in the base XML root.

    Args:
        collection_root: The input XML root containing the source collection
        base_root: The XML root element to modify

    Returns:
        The modified root element
    '''
    unplayed = get_unplayed_tracks(collection_root)
    return add_playlist_tracks(base_root, unplayed, constants.XPATH_UNPLAYED)

def add_playlist_tracks(base_root: ET.Element, tracks: list[str], playlist_xpath: str) -> ET.Element:
    '''Updates a playlist in the given XML root with the specified tracks.

    Args:
        base_root: The XML root element to modify (can be called multiple times on same instance)
        tracks: List of track IDs (TRACK.Key values) to add to playlist
        playlist_xpath: XPath expression to locate target playlist node

    Returns:
        The modified root element
    '''
    # populate the target playlist
    playlist_node = find_node(base_root, playlist_xpath)
    for track_id in tracks:
        ET.SubElement(playlist_node, constants.TAG_TRACK, {constants.ATTR_TRACK_KEY : track_id})
    playlist_node.set('Entries', str(len(tracks)))

    return base_root

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
def generate_date_paths_cli(args: Namespace) -> list[FileMapping]:
    collection = load_collection(args.collection)
    collection = find_node(collection, constants.XPATH_COLLECTION)
    return generate_date_paths(collection, args.root_path, metadata_path=args.metadata_path)

# TODO: update to handle '/' character in metadata path (e.g. a/jus/ted)
# TODO: add test coverage for URL-encoded paths (i.e. Rekordbox file location)
def generate_date_paths(collection: ET.Element,
                        root_path: str,
                        playlist_ids: set[str] = set(),
                        metadata_path: bool = False) -> list[FileMapping]:
    '''Generates a list of path mappings for a flat source structure.
    Each item maps from the original source path to a new date-structured path.
    The new path combines the root_path with the date context (year/month/day), optional metadata, and filename.
    '''
    paths: list[FileMapping] = []

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

def get_pipe_output(structure: list[FileMapping]) -> str:
    output = []
    for item in structure:
        output.append(f"{item[0].strip()}{constants.FILE_OPERATION_DELIMITER}{item[1].strip()}\n")
    return ''.join(output).strip()

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

# TODO: move to library module
# TODO: extend to save backup of previous X versions
# TODO: implement merge XML function
'''
# Determine which file has the more recent modify time

# Create merged tree

# Merge collection tracks
    Collect all track nodes from A
    Collect all track nodes from B
    For each track node in A
        Create merged node as copy of node
        If node.path exists in B
            Use node attributes from more recently modified file for merged node
        If merged node ID exists in merged tree collection
            Generate new ID for merged node
            Update entry in _pruned with new ID
        Add merged node to merged tree collection
    For each track node in B
        Create merged node as copy of node
        If node.path exists in A
            Skip
        If merged node ID exists in merged tree collection
            Generate new ID for merged node
            Update entry in _pruned with new ID
        Add merged node to merged tree collection

# Merge playlists
    Exclude the 'dynamic' folder
    Create merged _pruned node
    Collect all _pruned track IDs from A into merged _pruned
    For each track in B
        If track.id does not exist in merged _pruned
            Add track.id to merged _pruned

# Write the merged tree to the dynamic collection file
'''
def record_collection(source: str, collection_path: str, dry_run: bool = False) -> RecordResult:
    '''Updates the tracks for the 'COLLECTION' and '_pruned' playlist in the given XML `collection_path`
    with all music files in the `source` directory.
    Returns RecordResult with collection root, tracks added count, and tracks updated count.'''
    # load XML references
    xml_path      = collection_path if os.path.exists(collection_path) else constants.COLLECTION_PATH_TEMPLATE
    root          = load_collection(xml_path)
    collection    = find_node(root, constants.XPATH_COLLECTION)
    playlist_root = find_node(root, constants.XPATH_PLAYLISTS)
    pruned        = find_node(root, constants.XPATH_PRUNED)
    
    # count existing tracks
    existing_tracks = len(collection.findall(constants.TAG_TRACK))
    new_tracks = 0
    updated_tracks = 0
    
    # process all music files in the source directory
    paths = common.collect_paths(source)
    for file_path in paths:
        extension = os.path.splitext(file_path)[1]
        
        # only process music files
        if extension and extension in constants.EXTENSIONS:
            file_url = f"{constants.REKORDBOX_ROOT}{quote(file_path, safe='()/')}"
            
            # check if track already exists
            existing_track = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_PATH}="{file_url}"]')
            
            # load metadata Tags
            tags = Tags.load(file_path)
            if not tags:
                continue
            
            # map the XML attributes to the file metadata
            today = datetime.now().strftime('%Y-%m-%d')
            fallback_value = ''
            track_attrs = {
                constants.ATTR_TITLE  : tags.title or fallback_value,
                constants.ATTR_ARTIST : tags.artist or fallback_value,
                constants.ATTR_ALBUM  : tags.album or fallback_value,
                constants.ATTR_GENRE  : tags.genre or fallback_value,
                constants.ATTR_KEY    : tags.key or fallback_value,
                constants.ATTR_PATH   : file_url
            }
            
            # check for existing track
            if existing_track is not None:
                # keep original date added if it exists
                original_date = existing_track.get(constants.ATTR_DATE_ADDED)
                if original_date:
                    track_attrs[constants.ATTR_DATE_ADDED] = original_date
                else:
                    track_attrs[constants.ATTR_DATE_ADDED] = today
                    logging.warning(f"No date present for existing track: '{file_path}', using '{today}'")
                
                # update all track attributes
                for attr_name, attr_value in track_attrs.items():
                    existing_track.set(attr_name, attr_value)
                updated_tracks += 1
                logging.debug(f"Updated existing track: '{file_path}'")
            else:
                # create new track
                track_id = str(uuid.uuid4().int)[:9]
                track_attrs[constants.ATTR_TRACK_ID] = track_id
                track_attrs[constants.ATTR_DATE_ADDED] = today
                
                ET.SubElement(collection, constants.TAG_TRACK, track_attrs)
                new_tracks += 1
                logging.debug(f"Added new track: '{file_path}'")
                
                # add to pruned playlist
                ET.SubElement(pruned, constants.TAG_TRACK, {constants.ATTR_TRACK_KEY : track_id})
    
    # update the 'Entries' attributes
    collection.set('Entries', str(existing_tracks + new_tracks))
    pruned.set('Entries', str(len(pruned.findall(constants.TAG_TRACK))))
    
    # update ROOT node's Count based on its child nodes
    root_node_children = len(playlist_root.findall(constants.TAG_NODE))
    playlist_root.set('Count', str(root_node_children))
    
    # write the tree to the XML file
    if dry_run:
        common.log_dry_run('write collection', collection_path)
    else:
        tree = ET.ElementTree(root)
        tree.write(collection_path, encoding='UTF-8', xml_declaration=True)

    logging.info(f"Collection updated: {new_tracks} new tracks, {updated_tracks} updated tracks at {collection_path}")

    return RecordResult(
        collection_root=root,
        tracks_added=new_tracks,
        tracks_updated=updated_tracks
    )


# TODO: update to use latest collection at known path if no input path provided
# TODO: update to write to dynamic path defined as constant if output path not provided
# TODO: ^ requires arg parsing refactor.
def record_dynamic_tracks(input_collection_path: str, output_collection_path: str) -> ET.Element:
    '''Updates both the 'dynamic.played' and 'dynamic.unplayed' playlists in the output XML collection.

    Args:
        input_collection_path: Path to the input collection XML file
        output_collection_path: Path where the output collection XML will be written

    Returns:
        The modified root element
    '''
    # load the collection and base roots
    collection_root = load_collection(input_collection_path)
    base_root = load_collection(constants.COLLECTION_PATH_TEMPLATE)

    # copy collection to base
    base_collection = find_node(base_root, constants.XPATH_COLLECTION)
    collection = find_node(collection_root, constants.XPATH_COLLECTION)
    base_collection.clear()
    base_collection.attrib = collection.attrib
    for track in collection:
        base_collection.append(track)

    # update both playlists on the same base_root
    add_played_tracks(collection_root, base_root)
    add_unplayed_tracks(collection_root, base_root)

    # write the result to file
    tree = ET.ElementTree(base_root)
    tree.write(output_collection_path, encoding='UTF-8', xml_declaration=True)

    return base_root


# Main
if __name__ == '__main__':
    # setup
    common.configure_log_module(__file__, level=logging.DEBUG)
    script_args = parse_args(Namespace.FUNCTIONS, sys.argv[1:])

    if script_args.root_path:
        logging.info(f"args root path: '{script_args.root_path}'")

    if script_args.function == Namespace.FUNCTION_DATE_PATHS:
        print(get_pipe_output(generate_date_paths_cli(script_args)))
    elif script_args.function == Namespace.FUNCTION_IDENTIFIERS or script_args.function == Namespace.FUNCTION_FILENAMES:
        tree = load_collection(script_args.collection)
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
        with open(script_args.output, 'w', encoding='utf-8') as file:
            file.writelines(lines)
    elif script_args.function == Namespace.FUNCTION_RECORD_DYNAMIC:
        record_dynamic_tracks(script_args.collection, script_args.output)