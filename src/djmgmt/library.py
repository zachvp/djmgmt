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
    date_added: str
    total_time: str

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
    path_components = os.path.split(node.attrib[constants.ATTR_LOCATION].lstrip(library_root))
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

def syspath_to_collection_path(file_path: str) -> str:
    '''Transforms the given system path to an XML file path'''
    return f"{constants.REKORDBOX_ROOT}{quote(file_path, safe=constants.URL_SAFE_CHARS)}"

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

def find_playlist_node(root: ET.Element, playlist_dot_path: str) -> ET.Element | None:
    '''Find a playlist node by dot-separated hierarchical path (e.g., "dynamic.unplayed").

    Constructs an XPath from the dot path and queries the XML tree directly.

    Args:
        root: XML root element
        playlist_dot_path: Dot-separated playlist path (e.g., "dynamic.unplayed")

    Returns:
        Playlist NODE element or None if not found
    '''
    parts = playlist_dot_path.split('.')
    segments = '/'.join(f'{constants.TAG_NODE}[@Name="{part}"]' for part in parts)
    xpath = f'./PLAYLISTS/{constants.TAG_NODE}[@Name="ROOT"]/{segments}'
    node = root.find(xpath)
    if node is None:
        logging.error(f"Unable to find playlist node at path '{playlist_dot_path}' (xpath: {xpath})")
    return node

def get_playlist_track_ids(playlist_node: ET.Element) -> list[str]:
    '''Extract ordered track IDs (Key attribute) from a playlist node.

    Args:
        playlist_node: The playlist NODE element containing TRACK children

    Returns:
        Ordered list of track Key values
    '''
    track_ids: list[str] = []
    for track in playlist_node.findall(constants.TAG_TRACK):
        track_id = track.get(constants.ATTR_TRACK_KEY)
        if track_id is None:
            logging.error(f"No track ID exists for playlist '{playlist_node.get(constants.ATTR_TITLE)}'. Track metadata: {create_track_metadata(track)}")
        if track_id is not None:
            track_ids.append(track_id)
    return track_ids

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
        path = track.get(constants.ATTR_LOCATION)
        if track_id and path and track_id in track_keys:
            track_paths.add(collection_path_to_syspath(path))
    
    # filter the mappings according to the track paths
    filtered = [mapping for mapping in mappings if mapping[0] in track_paths]
    return filtered

def create_track_metadata(track_node: ET.Element) -> TrackMetadata:
    return TrackMetadata(
        title=track_node.get(constants.ATTR_TITLE, ''),
        artist=track_node.get(constants.ATTR_ARTIST, ''),
        album=track_node.get(constants.ATTR_ALBUM, ''),
        date_added=track_node.get(constants.ATTR_DATE_ADDED, ''),
        total_time=track_node.get(constants.ATTR_TOTAL_TIME, '0'),
        path=collection_path_to_syspath(track_node.get(constants.ATTR_LOCATION, ''))
    )

def extract_track_metadata_by_path(collection: ET.Element, syspath: str) -> TrackMetadata | None:
    '''Extracts track metadata from XML collection by file path.

    Args:
        collection: The COLLECTION node element
        syspath: System file path to look up

    Returns:
        TrackMetadata with title, artist, album, path, or None if not found
    '''

    # Convert system path to URL format for XML lookup (pattern from music.py:254)
    file_url = syspath_to_collection_path(syspath)

    # Find track in collection
    track_node = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_LOCATION}="{file_url}"]')

    if track_node is None:
        logging.warning(f'Track not found in collection: {syspath}')
        return None

    return create_track_metadata(track_node)

def extract_track_metadata_by_id(collection: ET.Element, track_id: str) -> TrackMetadata | None:
    '''Extracts track metadata from XML collection by TrackID.

    Args:
        collection: The COLLECTION node element
        track_id: Track ID to look up

    Returns:
        TrackMetadata with metadata or None if not found
    '''
    track_node = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_TRACK_ID}="{track_id}"]')

    if track_node is None:
        logging.warning(f'Track ID {track_id} not found in COLLECTION')
        return None

    # Get location and convert to system path
    return create_track_metadata(track_node)

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

def add_pruned_tracks(collection_root: ET.Element, base_root: ET.Element) -> ET.Element:
    '''Updates the '_pruned' playlist in the base XML root with tracks from the input collection.

    Args:
        collection_root: The input XML root containing the source _pruned playlist
        base_root: The XML root element to modify

    Returns:
        The modified root element
    '''
    pruned_node = find_node(collection_root, constants.XPATH_PRUNED)
    pruned_ids = get_playlist_track_ids(pruned_node)
    return add_playlist_tracks(base_root, pruned_ids, constants.XPATH_PRUNED)

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

def write_root(root: ET.Element, file_path: str) -> None:
    tree = ET.ElementTree(root)
    tree.write(file_path, encoding='UTF-8', xml_declaration=True)

# Primary functions
def generate_date_paths_cli(args: Namespace) -> list[FileMapping]:
    collection = load_collection(args.collection)
    collection = find_node(collection, constants.XPATH_COLLECTION)
    return generate_date_paths(collection, args.root_path, metadata_path=args.metadata_path)

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
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_LOCATION])
        if constants.REKORDBOX_ROOT not in node.attrib[constants.ATTR_LOCATION]:
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

def collect_identifiers(collection: ET.Element, playlist_ids: set[str] = set()) -> list[str]:
    from .tags import Tags
    
    identifiers: list[str] = []
    
    for node in collection:
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_LOCATION])
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
        node_syspath = collection_path_to_syspath(node.attrib[constants.ATTR_LOCATION])
        # check if a playlist is provided
        if playlist_ids and node.attrib[constants.ATTR_TRACK_ID] not in playlist_ids:
            logging.debug(f"skip non-playlist track: '{node_syspath}'")
            continue
        name = os.path.basename(node_syspath)
        name = os.path.splitext(name)[0]
        names.append(name)
    return names

# TODO: extend to save backup of previous X versions
# TODO: implement merge XML function
def record_collection(source: str, base_collection_path: str, output_collection_path: str, dry_run: bool = False) -> RecordResult:
    '''Updates the tracks for the 'COLLECTION' and '_pruned' playlist in the given XML `collection_path`
    with all music files in the `source` directory.
    Returns RecordResult with collection root, tracks added count, and tracks updated count.'''
    # load XML references
    xml_path      = base_collection_path if os.path.exists(base_collection_path) else constants.COLLECTION_PATH_TEMPLATE
    root          = load_collection(xml_path)
    collection    = find_node(root, constants.XPATH_COLLECTION)
    playlist_root = find_node(root, constants.XPATH_PLAYLISTS)
    pruned        = find_node(root, constants.XPATH_PRUNED)
    
    # log
    logging.debug(f"Use xml path: '{xml_path}'")
    
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
            file_url = syspath_to_collection_path(file_path)
            
            # check if track already exists
            existing_track = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_LOCATION}="{file_url}"]')
            
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
                constants.ATTR_LOCATION   : file_url
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
        common.log_dry_run('write collection', base_collection_path)
    else:
        write_root(root, output_collection_path)

    logging.info(f"Collection updated: {new_tracks} new tracks, {updated_tracks} updated tracks at {base_collection_path}")

    return RecordResult(
        collection_root=root,
        tracks_added=new_tracks,
        tracks_updated=updated_tracks
    )

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

    # update all playlists on the same base_root
    add_pruned_tracks(collection_root, base_root)
    add_played_tracks(collection_root, base_root)
    add_unplayed_tracks(collection_root, base_root)

    # write the result to file
    write_root(base_root, output_collection_path)

    return base_root

def _build_track_index(collection: ET.Element) -> dict[str, ET.Element]:
    '''Builds a mapping from Location attribute to TRACK element.

    Args:
        collection: The COLLECTION node containing TRACK elements

    Returns:
        Dict mapping Location URL to TRACK element
    '''
    index: dict[str, ET.Element] = {}
    for track in collection:
        location = track.get(constants.ATTR_LOCATION)
        if location:
            index[location] = track
        else:
            logging.warning(f"No location exists for track {track.get(constants.ATTR_TRACK_ID)}")
    return index


def _build_track_id_to_location(collection: ET.Element) -> dict[str, str]:
    '''Builds a mapping from TrackID to Location for playlist reference resolution.

    Args:
        collection: The COLLECTION node containing TRACK elements

    Returns:
        Dict mapping TrackID to Location URL
    '''
    mapping: dict[str, str] = {}
    for track in collection:
        track_id = track.get(constants.ATTR_TRACK_ID)
        location = track.get(constants.ATTR_LOCATION)
        if track_id and location:
            mapping[track_id] = location
    return mapping


def _get_playlist_track_keys(root: ET.Element, playlist_xpath: str) -> set[str]:
    '''Gets all track Key values from a playlist.

    Args:
        root: The XML root element
        playlist_xpath: XPath to the playlist node

    Returns:
        Set of track Key values (TrackIDs referenced by the playlist)
    '''
    try:
        playlist = find_node(root, playlist_xpath)
    except ValueError:
        return set()

    keys: set[str] = set()
    for track in playlist.findall(constants.TAG_TRACK):
        key = track.get(constants.ATTR_TRACK_KEY)
        if key:
            keys.add(key)
    return keys


def _merge_playlist_references(
    primary_root: ET.Element,
    secondary_root: ET.Element,
    primary_collection: ET.Element,
    secondary_collection: ET.Element,
    merged_track_index: dict[str, ET.Element],
    playlist_xpath: str
) -> set[str]:
    '''Merges playlist track references from two collections.

    Resolves TrackID references to Locations, then maps back to the merged
    collection's TrackIDs. Deduplicates by Location to handle ID conflicts.

    Args:
        primary_root: Primary XML root
        secondary_root: Secondary XML root
        primary_collection: Primary COLLECTION node
        secondary_collection: Secondary COLLECTION node
        merged_track_index: Location -> TRACK mapping of merged collection
        playlist_xpath: XPath to the playlist to merge

    Returns:
        Set of TrackIDs for the merged playlist
    '''
    # build TrackID -> Location mappings for both collections
    primary_id_to_loc = _build_track_id_to_location(primary_collection)
    secondary_id_to_loc = _build_track_id_to_location(secondary_collection)

    # get playlist track keys from both
    primary_keys = _get_playlist_track_keys(primary_root, playlist_xpath)
    secondary_keys = _get_playlist_track_keys(secondary_root, playlist_xpath)

    # resolve keys to locations (deduplicate by location)
    merged_locations: set[str] = set()

    for key in primary_keys:
        location = primary_id_to_loc.get(key)
        if location:
            merged_locations.add(location)

    for key in secondary_keys:
        location = secondary_id_to_loc.get(key)
        if location:
            merged_locations.add(location)

    # map locations back to merged TrackIDs
    merged_keys: set[str] = set()
    for location in merged_locations:
        track = merged_track_index.get(location)
        if track is not None:
            track_id = track.get(constants.ATTR_TRACK_ID)
            if track_id:
                merged_keys.add(track_id)

    return merged_keys


def merge_collections(primary_path: str, secondary_path: str) -> ET.Element:
    '''Merges two Rekordbox XML collections into a single root element.

    Combines COLLECTION tracks and _pruned playlist from both files. When the
    same track (by Location) exists in both, uses metadata from the file with
    the newer modification time.

    Args:
        primary_path: Path to first XML collection file
        secondary_path: Path to second XML collection file

    Returns:
        Merged ET.Element root with combined COLLECTION tracks and _pruned playlist
    '''
    # load both XML files
    primary_root = load_collection(primary_path)
    secondary_root = load_collection(secondary_path)
    primary_collection = find_node(primary_root, constants.XPATH_COLLECTION)
    secondary_collection = find_node(secondary_root, constants.XPATH_COLLECTION)

    # determine which file is newer (source of truth for conflicts)
    primary_mtime = os.path.getmtime(primary_path)
    secondary_mtime = os.path.getmtime(secondary_path)

    if primary_mtime >= secondary_mtime:
        newer_collection = primary_collection
        older_collection = secondary_collection
    else:
        newer_collection = secondary_collection
        older_collection = primary_collection

    # start with a fresh template
    output_root = load_collection(constants.COLLECTION_PATH_TEMPLATE)
    output_collection = find_node(output_root, constants.XPATH_COLLECTION)

    # build index from older collection first
    track_index = _build_track_index(older_collection)

    # overwrite with newer collection tracks (newer wins on conflict)
    for track in newer_collection:
        location = track.get(constants.ATTR_LOCATION)
        if location:
            track_index[location] = track

    # copy all tracks to output collection
    for track in track_index.values():
        output_collection.append(track)

    # update Entries count
    output_collection.set('Entries', str(len(track_index)))

    # merge _pruned playlist
    merged_pruned_keys = _merge_playlist_references(
        primary_root,
        secondary_root,
        primary_collection,
        secondary_collection,
        track_index,
        constants.XPATH_PRUNED
    )

    # populate output _pruned playlist
    output_pruned = find_node(output_root, constants.XPATH_PRUNED)
    for track_id in merged_pruned_keys:
        ET.SubElement(output_pruned, constants.TAG_TRACK, {constants.ATTR_TRACK_KEY: track_id})
    output_pruned.set('Entries', str(len(merged_pruned_keys)))

    logging.info(f"Merged collections: {len(track_index)} tracks, {len(merged_pruned_keys)} pruned")
    return output_root


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