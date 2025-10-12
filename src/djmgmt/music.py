'''
Functions to scan and manipulate a batch of music files.
    sweep:           Moves all music files and archives to another directory.
    flatten:         Flattens all files in a given directory, including subdirectories.
    extract:         Extract files from all archives.
    compress:        Zips the contents of a given directory.
    prune:           Removes all empty folders and non-music files from a directory.
    prune_non_music  Removes all non-music files from a directory.
    process:         Convenience function to run sweep, extract, flatten, and all prune functions in sequence for a directory.
    update_library   Processes a directory containing music files into a local library folder, then syncs the updated library.
'''

import argparse
import os
import shutil
import zipfile
import logging

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

from . import constants
from . import common
from . import encode
from . import library
from .tags import Tags

# constants
PREFIX_HINTS = {'beatport_tracks', 'juno_download'}
COLLECTION_PATH = os.path.join(constants.PROJECT_ROOT, 'state', 'processed-collection.xml')
COLLECTION_TEMPLATE_PATH = os.path.join(constants.PROJECT_ROOT, 'state', 'collection-template.xml')
MISSING_ART_PATH = os.path.join(constants.PROJECT_ROOT, 'state', 'missing-art.txt')

## xml references
TAG_TRACK     = 'TRACK'
TAG_NODE      = 'NODE'

# classes
class Namespace(argparse.Namespace):
    # arguments
    ## required
    function: str
    input: str
    output: str
    
    ## optional
    interactive: bool    
    client_mirror_path: str
    collection_backup_directory: str
    
    # primary functions
    FUNCTION_SWEEP = 'sweep'
    FUNCTION_FLATTEN = 'flatten'
    FUNCTION_EXTRACT = 'extract'
    FUNCTION_COMPRESS = 'compress'
    FUNCTION_PRUNE = 'prune'
    FUNCTION_PROCESS = 'process'
    FUNCTION_PRUNE_NON_MUSIC = 'prune_non_music'
    FUNCTION_UPDATE_LIBRARY = 'update_library'
    FUNCTION_RECORD_UNPLAYED = 'record_unplayed'
    
    FUNCTIONS_SINGLE_ARG = {FUNCTION_COMPRESS, FUNCTION_FLATTEN, FUNCTION_PRUNE, FUNCTION_PRUNE_NON_MUSIC}
    FUNCTIONS = {FUNCTION_SWEEP, FUNCTION_EXTRACT, FUNCTION_PROCESS, FUNCTION_UPDATE_LIBRARY, FUNCTION_RECORD_UNPLAYED}.union(FUNCTIONS_SINGLE_ARG)

# Helper functions
# TODO: include function docstring in help summary (-h)
def parse_args(valid_functions: set[str], single_arg_functions: set[str]) -> type[Namespace]:
    # create the parser
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    
    # configure arguments
    parser.add_argument('function', type=str, help=f"Which script function to run. One of '{valid_functions}'.\
        The following functions only require a single argument: '{single_arg_functions}'.")
    # TODO: define argument strings as Namespace constants
    parser.add_argument('input', type=str, help='The input path.')
    parser.add_argument('output', nargs='?', type=str, help='The output path.')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run script in interactive mode.')
    parser.add_argument('--client-mirror-path', '-m', type=str, help='The client mirror path to pass to media sync.')
    parser.add_argument('--collection-backup-directory', '-b', type=str, help='The directory that stores the backup XML files.')
    
    # parse arguments
    args = parser.parse_args(namespace=Namespace)

    # validate the arguments
    if args.function not in valid_functions:
        parser.error(f"Invalid function '{args.function}'")
    if not args.output and args.function not in single_arg_functions:
        parser.error(f"The 'output' argument is required for function '{args.function}'")
    if args.function == Namespace.FUNCTION_UPDATE_LIBRARY:
        if not args.client_mirror_path:
            parser.error(f"The '--client-mirror-path' argument is required for {Namespace.FUNCTION_UPDATE_LIBRARY}")
        if not args.collection_backup_directory:
            parser.error(f"The '--collection-backup-path' argument is required for {Namespace.FUNCTION_UPDATE_LIBRARY}")

    # normalize and validate path arguments
    args.input = os.path.normpath(args.input)
    if args.client_mirror_path:
        if not os.path.exists(args.client_mirror_path):
            parser.error(f"The '--client-mirror-path' '{args.client_mirror_path}' does not exist.")
        args.client_mirror_path = os.path.normpath(args.client_mirror_path)
    
    if args.collection_backup_directory:
        if not os.path.exists(args.collection_backup_directory):
            parser.error(f"The '--collection-backup-path' '{args.collection_backup_directory}' does not exist.")
        args.collection_backup_directory = os.path.normpath(args.collection_backup_directory)

    # handle input and output for single vs. multiple arg functions
    if args.output:
        args.output = os.path.normpath(args.output)
    else:
        args.output = args.input

    return args

def compress_dir(input_path: str, output_path: str) -> tuple[str, list[str]]:
    compressed: list[str] = []
    archive_path = f"{output_path}.zip"
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file_path in common.collect_paths(input_path):
            name = os.path.basename(file_path)
            archive.write(file_path, arcname=name)
            compressed.append(file_path)
    return (archive_path, compressed)

def is_prefix_match(value: str, prefixes: set[str]) -> bool:
    for prefix in prefixes:
        if value.startswith(prefix):
            return True
    return False

def prune(working_dir: str, directories: list[str], filenames: list[str]) -> None:
    for index, directory in enumerate(directories):
        if is_prefix_match(directory, {'.', '_'}) or '.app' in directory:
            logging.info(f"prune: hidden directory or '.app' archive '{os.path.join(working_dir, directory)}'")
            del directories[index]
    for index, name in enumerate(filenames):
        if name.startswith('.'):
            logging.info(f"prune: hidden file '{name}'")
            del filenames[index]

def extract_all_normalized_encodings(zip_path: str, output: str) -> tuple[str, list[str]]:
    extracted: list[str] = []
    with zipfile.ZipFile(zip_path, 'r') as file:
        for info in file.infolist():
            # default to the current filename
            corrected = info.filename
            
            # try to normalize the filename encoding
            try:
                # attempt to encode the filename with the common zip encoding and decode as utf-8
                corrected = info.filename.encode('cp437').decode('utf-8')
                logging.debug(f"Corrected filename '{info.filename}' to '{corrected}' using utf-8 encoding")
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    # attempt universal decoding to latin1
                    corrected = info.filename.encode('cp437').decode('latin1')
                    logging.debug(f"Fallback filename encoding from '{info.filename}' to '{corrected}' using latin1 encoding")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    logging.warning(f"Unable to fix encoding for filename: '{info.filename}'")
            info.filename = corrected
            file.extract(info, os.path.normpath(output))
            extracted.append(info.filename)
    logging.debug(f"extracting archive '{zip_path}' to {extracted}")
    return (zip_path, extracted)

def flatten_zip(zip_path: str, extract_path: str) -> None:
    output_directory = os.path.splitext(os.path.basename(zip_path))[0]
    logging.debug(f"output dir: {os.path.join(extract_path, output_directory)}")
    extract_all_normalized_encodings(zip_path, extract_path)

    unzipped_path = os.path.join(extract_path, output_directory)
    for file_path in common.collect_paths(unzipped_path):
        logging.debug(f"move from {file_path} to {extract_path}")
        shutil.move(file_path, extract_path)
    if os.path.exists(unzipped_path) and len(os.listdir(unzipped_path)) < 1:
        logging.info(f"remove empty unzipped path {unzipped_path}")
        shutil.rmtree(unzipped_path)

def has_no_user_files(dir_path: str) -> bool:
    '''Returns True if the given path contains nothing or only hidden files and other directories.
    Returns False if a non-hidden file exists in the directory.'''
    if not os.path.isdir(dir_path):
        raise TypeError(f"path '{dir_path}' is not a directory")

    # get all child paths
    paths = os.listdir(dir_path)
    
    # count the number of directories and hidden files
    non_user_files = 0
    for path in paths:
        check_path = os.path.join(dir_path, path)
        logging.debug(f"check path: {check_path}")
        if path.startswith('.') or os.path.isdir(check_path):
            non_user_files += 1

    logging.debug(f"{non_user_files} == {len(paths)}?")
    return non_user_files == len(paths)

def get_dirs(dir_path: str) -> list[str]:
    '''Return all directory paths within the given directory, relative to that given directory.'''
    if not os.path.isdir(dir_path):
        # TODO: move to common function that takes Error type and message, then logs and raises the error
        raise TypeError(f"path '{dir_path}' is not a directory")

    # collect the directories
    dirs = []
    dir_list = os.listdir(dir_path)
    for item in dir_list:
        path = os.path.join(dir_path, item)
        if os.path.isdir(path):
            dirs.append(path)
    return dirs

def standardize_lossless(source: str, valid_extensions: set[str], prefix_hints: set[str], interactive: bool) -> list[tuple[str, str]]:
    '''Standardizes all lossless files in the source directory according to `.encode.encode_lossless()` using the .aiff extension.
    Returns a list of each (source, encoded_file) mapping.'''
    from tempfile import TemporaryDirectory
    import asyncio
    
    # create a temporary directory to place the encoded files.
    with TemporaryDirectory() as temp_dir:
        # encode all non-standard lossless files
        result = asyncio.run(encode.encode_lossless(source, temp_dir, '.aiff', interactive=interactive))
        
        # remove all of the original non-standard files that have been encoded.
        for input_path, _ in result:
            os.remove(input_path)
        # sweep all the encoded files from the temporary directory to the original source directory
        sweep(temp_dir, source, False, valid_extensions, prefix_hints)
        return result

def get_played_tracks(root: ET.Element) -> list[str]:
    '''Returns a list of TRACK.Key/ID strings for all playlist tracks in the 'archive' folder.'''
    # load XML references
    archive = library.find_node(root, constants.XPATH_MIXTAPES)
    
    # search for and collect tracks in archive
    played_tracks = []
    existing = set()
    track_nodes = archive.findall(f'.//{TAG_TRACK}')
    for track in track_nodes:
        track_id = track.get(constants.ATTR_TRACK_KEY)
        if track_id not in existing:
            played_tracks.append(track_id)
            existing.add(track_id)
    return played_tracks

# TODO: write played tracks to XML
def record_played_tracks() -> ET.Element:
    pass

def get_unplayed_tracks(root: ET.Element) -> list[str]:
    '''Returns a list of TRACK.Key/ID strings for all pruned tracks NOT in the 'archive' folder.'''
    # load XML references
    pruned = library.find_node(root, constants.XPATH_PRUNED)
    
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

# TODO: add test coverage
def record_unplayed_tracks(input_collection_path: str, output_collection_path: str) -> ET.Element:
    '''Updates the 'dynamic.unplayed' playlist in the output XML collection.'''
    # load XML references
    input_root = library.load_collection(input_collection_path)
    input_collection = library.find_node(input_root, constants.XPATH_COLLECTION)
    template_root = library.load_collection(COLLECTION_TEMPLATE_PATH)
    
    # replace template's collection with input's collection to resolve playlist track references
    template_collection = library.find_node(template_root, constants.XPATH_COLLECTION)
    template_collection.clear()
    template_collection.attrib = input_collection.attrib
    for track in input_collection:
        template_collection.append(track)
    
    # populate the unplayed playlist
    unplayed = get_unplayed_tracks(input_root)
    unplayed_node = library.find_node(template_root, constants.XPATH_UNPLAYED)
    for track in unplayed:
        ET.SubElement(unplayed_node, TAG_TRACK, {constants.ATTR_TRACK_KEY : track})
    unplayed_node.set('Entries', str(len(unplayed)))
    
    # write the collection containing the unplayed tracks
    tree = ET.ElementTree(template_root)
    tree.write(output_collection_path, encoding='UTF-8', xml_declaration=True)
    return template_root

def record_tracks(input_collection_path: str, output_collection_path: str, tracks: list[str], playlist: str) -> ET.Element:
    pass

# TODO: move to library module
# TODO: extend to save backup of previous X versions
def record_collection(source: str, collection_path: str) -> ET.Element:
    '''Updates the tracks for the 'COLLECTION' and '_pruned' playlist in the given XML `collection_path`
    with all music files in the `source` directory.
    Returns the XML collection root.'''
    # load XML references
    xml_path      = collection_path if os.path.exists(collection_path) else COLLECTION_TEMPLATE_PATH
    root          = library.load_collection(xml_path)
    collection    = library.find_node(root, constants.XPATH_COLLECTION)
    playlist_root = library.find_node(root, constants.XPATH_PLAYLISTS)
    pruned        = library.find_node(root, constants.XPATH_PRUNED)
    
    # count existing tracks
    existing_tracks = len(collection.findall(TAG_TRACK))
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
            existing_track = collection.find(f'./{TAG_TRACK}[@{constants.ATTR_PATH}="{file_url}"]')
            
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
                
                ET.SubElement(collection, TAG_TRACK, track_attrs)
                new_tracks += 1
                logging.debug(f"Added new track: '{file_path}'")
                
                # add to pruned playlist
                ET.SubElement(pruned, TAG_TRACK, {constants.ATTR_TRACK_KEY : track_id})
    
    # update the 'Entries' attributes
    collection.set('Entries', str(existing_tracks + new_tracks))
    pruned.set('Entries', str(len(pruned.findall(TAG_TRACK))))
    
    # update ROOT node's Count based on its child nodes
    root_node_children = len(playlist_root.findall(TAG_NODE))
    playlist_root.set('Count', str(root_node_children))
    
    # write the tree to the XML file
    tree = ET.ElementTree(root)
    tree.write(collection_path, encoding='UTF-8', xml_declaration=True)
    logging.info(f"Collection updated: {new_tracks} new tracks, {updated_tracks} updated tracks at {collection_path}")
    
    return root

# Primary functions
def sweep(source: str, output: str, interactive: bool, valid_extensions: set[str], prefix_hints: set[str]) -> list[tuple[str, str]]:
    swept: list[tuple[str, str]] = []
    for input_path in common.collect_paths(source):
        # loop state
        name = os.path.basename(input_path)
        output_path = os.path.join(output, name)
        name_split = os.path.splitext(name)

        if os.path.exists(output_path):
            logging.info(f"skip: path '{output_path}' exists in destination")
            continue

        # handle zip archive
        # TODO: refactor so that is_music_archive is its own function
        is_valid_archive = False
        if name_split[1] == '.zip':
            is_valid_archive = True
            
            # inspect zip archive to determine if this is likely a music container
            if not is_prefix_match(name, prefix_hints):
                valid_files = 0
                with zipfile.ZipFile(input_path, 'r') as archive:
                    for archive_file in archive.namelist():
                        if not is_valid_archive:
                            logging.debug(f"invalid archive: '{input_path}''")
                            break

                        # ignore archive that contains an app
                        filepath_split = os.path.split(archive_file)
                        for f in filepath_split:
                            if '.app' in os.path.splitext(f)[1]:
                                logging.info(f"app {archive_file} detected, skipping")
                                is_valid_archive = False
                                break
                        
                        # only the given valid extensions and images are allowed
                        file_ext = os.path.splitext(archive_file)[1]
                        if file_ext in valid_extensions:
                            valid_files += 1
                        else:
                            is_valid_archive &= file_ext in {'.jpg', '.png', '.jpeg'}
                is_valid_archive &= valid_files > 0
                logging.debug(f"archive '{input_path}' valid = '{is_valid_archive}'")

        # move input file if it has a supported extension or is a valid archive
        if name_split[1] in valid_extensions or is_valid_archive:
            logging.debug(f"filter matched file '{input_path}'")
            if interactive:
                print(f"move from '{input_path}' to '{output_path}'")
                choice = input('Continue? [y/N/q]')
                if choice == 'q':
                    logging.info('user quit')
                    return swept
                if choice != 'y' or choice in 'nN':
                    logging.info('skip: user skipped file')
                    continue
            logging.debug(f"move from '{input_path}' to '{output_path}'")
            shutil.move(input_path, output_path)
            swept.append((input_path, output_path))
    logging.info(f"swept all files ({len(swept)})\n{swept}")
    return swept    

def sweep_cli(args: type[Namespace], valid_extensions: set[str], prefix_hints: set[str]) -> None:
    sweep(args.input, args.output, args.interactive, valid_extensions, prefix_hints)

def flatten_hierarchy(source: str, output: str, interactive: bool) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    for input_path in common.collect_paths(source):
        name = os.path.basename(input_path)
        output_path = os.path.join(output, name)

        # move the files to the output root
        if not os.path.exists(output_path):
            msg = f"move '{input_path}' to '{output_path}'"
            if interactive:
                print(msg)
                choice = input('Continue? [y/N/q]')
                if choice == 'q':
                    logging.info('info: user quit')
                    return flattened
                if choice != 'y' or choice in 'nN':
                    logging.info(f"skip: {input_path}")
                    continue
            logging.debug(msg)
            try:
                shutil.move(input_path, output_path)
                flattened.append((input_path, output_path))
            except FileNotFoundError as error:
                if error.filename == input_path:
                    logging.info(f"skip: encountered ghost file: '{input_path}'")
                    continue
        else:
            logging.debug(f"skip: {input_path}")
    logging.debug(f"flattened all files ({len(flattened)})\n{flattened}")
    return flattened

def flatten_hierarchy_cli(args: type[Namespace]) -> None:
    flatten_hierarchy(args.input, args.output, args.interactive)

def extract(source: str, output: str, interactive: bool) -> list[tuple[str, list[str]]]:
    extracted: list[tuple[str, list[str]]] = []
    for input_path in common.collect_paths(source):
        name = os.path.basename(input_path)
        name_split = os.path.splitext(name)
        if name_split[1] == '.zip':
            zip_output_path = os.path.join(output, name_split[0])

            if os.path.exists(zip_output_path) and os.path.isdir(zip_output_path):
                logging.info(f"skip: existing ouput path '{zip_output_path}'")
                continue

            msg = f"extracting '{input_path}' to '{output}'"
            logging.debug(msg)
            if interactive:
                print(msg)
                choice = input('Continue? [y/N/q]')
                if choice == 'q':
                    logging.info('user quit')
                    return extracted
                if choice != 'y' or choice in 'nN':
                    logging.info(f"skip: {input_path}")
                    continue
            # extract all zip contents, with normalized filename encodings
            extracted.append(extract_all_normalized_encodings(input_path, output))
        else:
            logging.debug(f"skip: non-zip file '{input_path}'")
    return extracted

def extract_cli(args: type[Namespace]) -> None:
    extract(args.input, args.output, args.interactive)

def compress_all_cli(args: type[Namespace]) -> None:
    for working_dir, directories, _ in os.walk(args.input):
        for directory in directories:
            compress_dir(os.path.join(working_dir, directory), os.path.join(args.output, directory))

def prune_non_user_dirs(source: str, interactive: bool) -> list[str]:
    '''Removes all directories that pass the filter according to `has_no_user_files()`.
    Returns a list of all removed directories.'''
    search_dirs: list[str] = []
    pruned: set[str] = set()

    # DFS for all directories inside 'source' that don't contain user files
    logging.debug(f"prune_non_user_dirs starting from root '{source}'")
    dir_list = get_dirs(source)
    search_dirs = [os.path.join(source, d) for d in dir_list]
    while len(search_dirs) > 0:
        search_dir = search_dirs.pop(0)
        if has_no_user_files(search_dir):
            pruned.add(search_dir)
        else:
            logging.info(f"search_dir: {search_dir}")
            dir_list = get_dirs(search_dir)
            for d in dir_list:
                search_dirs.append(os.path.join(search_dir, d))

    # remove the collected directories
    for path in pruned:
        msg = f"will remove: '{path}'"
        if interactive:
            print(msg)
            choice = input("continue? [y/N]")
            if choice != 'y':
                logging.info('skip: user skipped')
                continue
        logging.debug(msg)
        try:
            shutil.rmtree(path)
        except OSError as e:
            if e.errno == 39: # directory not empty
                logging.warning(f"skip: non-empty dir {path}")

    # return the pruned directories
    result = list(pruned)
    logging.debug(f"pruned all non-user directories ({len(result)}\n{result})")
    return result

def prune_non_user_dirs_cli(args: type[Namespace]) -> None:
    '''CLI wrapper for the core `prune_non_user_dirs` function.'''
    prune_non_user_dirs(args.input, args.interactive)
    
def prune_non_music(source: str, valid_extensions: set[str], interactive: bool) -> list[str]:
    '''Removes all files that don't have a valid music extension from the given directory.'''
    pruned = []
    for input_path in common.collect_paths(source):
        _, extension = os.path.splitext(input_path)
        
        # check extension
        if extension not in valid_extensions:
            logging.info(f"non-music file found: '{input_path}'")
            
            # check interactive mode
            if interactive:
                choice = input("continue? [y/N]")
                if choice != 'y':
                    logging.info('skip: user skipped')
                    continue
            # try to remove the file/dir
            try:
                if os.path.isdir(input_path):
                    shutil.rmtree(input_path)
                    pruned.append(input_path)
                else:
                    os.remove(input_path)
                    pruned.append(input_path)
                logging.info(f"removed: '{input_path}'")
            except OSError as e:
                msg = f"Error removing file '{input_path}': {str(e)}" # TODO: use helper
                logging.error(msg)
                raise RuntimeError(msg)
    return pruned

def prune_non_music_cli(args: type[Namespace], valid_extensions: set[str]) -> None:
    prune_non_music(args.input, valid_extensions, args.interactive)

def process(source: str, output: str, interactive: bool, valid_extensions: set[str], prefix_hints: set[str]) -> None:
    '''Performs the following, in sequence:
        1. Sweeps all music files and archives from the `source` directory into the `output` directory.
        2. Extracts all zip archives within the `output` directory.
        3. Flattens the files within the `output` directory.
        3. Standardizes lossless file encodings within the `output` directory.
        4. Removes all non-music files in the `output` directory.
        5. Removes all directories that contain no visible files within the `output` directory.
        6. Records the paths of the `output` tracks that are missing artwork to a text file.
        
        The source and output directories may be the same for effectively in-place processing.
    '''
    import asyncio
    
    sweep(source, output, interactive, valid_extensions, prefix_hints)
    extract(output, output, interactive)
    flatten_hierarchy(output, output, interactive)
    standardize_lossless(output, valid_extensions, prefix_hints, interactive)
    prune_non_music(output, valid_extensions, interactive)
    prune_non_user_dirs(output, interactive)
    
    missing = asyncio.run(encode.find_missing_art_os(output, threads=72))
    common.write_paths(missing, MISSING_ART_PATH)

def process_cli(args: type[Namespace], valid_extensions: set[str], prefix_hints: set[str]) -> None:
    '''CLI wrapper for the core `process` function.'''
    process(args.input, args.output, args.interactive, valid_extensions, prefix_hints)

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

def update_library(source: str,
                   library_path: str,
                   client_mirror_path: str,
                   collection_backup_directory: str,
                   interactive: bool,
                   valid_extensions: set[str],
                   prefix_hints: set[str]) -> None:
    '''Performs the following, in sequence:
        1. Processes files from source dir -> temp dir
        2. Sweeps files from temp dir -> library
        3. Records the updated library to the XML collection
        4. Collects library -> client mirror file mappings according to the new files added to the XML collection
        4. Adds file mappings according to metadata differences between library <-> client mirror
        5. Syncs the new and changed files from library -> client mirror path -> media server
        
        The source, library, and client_mirror_path arguments should all be distinct directories.
    '''
    from tempfile import TemporaryDirectory
    from . import sync
    from . import tags_info
    
    # create a temporary directory to process the files from source
    with TemporaryDirectory() as processing_dir:
        # process all of the source files into the temp dir
        process(source, processing_dir, interactive, valid_extensions, prefix_hints)
        
        # move the processed files to the library
        sweep(processing_dir, library_path, interactive, valid_extensions, prefix_hints)
    
    # update the djmgmt collection record according to any new files
    collection = record_collection(library_path, COLLECTION_PATH)

    # combine any changed mappings in _pruned with the standard filtered collection mappings
    changed = tags_info.compare_tags(library_path, client_mirror_path)
    changed = library.filter_path_mappings(changed, collection, constants.XPATH_PRUNED)
    mappings = sync.create_sync_mappings(collection, client_mirror_path)
    if changed:
        mappings += changed
    
    # run the sync
    sync.run_sync_mappings(mappings)

if __name__ == '__main__':
    common.configure_log(path=__file__)

    # parse arguments
    script_args = parse_args(Namespace.FUNCTIONS, Namespace.FUNCTIONS_SINGLE_ARG)
    logging.info(f"will execute: '{script_args.function}'")

    if script_args.function == Namespace.FUNCTION_SWEEP:
        sweep_cli(script_args, constants.EXTENSIONS, PREFIX_HINTS)
    elif script_args.function == Namespace.FUNCTION_FLATTEN:
        flatten_hierarchy_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_EXTRACT:
        extract_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_COMPRESS:
        compress_all_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_PRUNE:
        prune_non_user_dirs_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_PRUNE_NON_MUSIC:
        prune_non_music_cli(script_args, constants.EXTENSIONS)
    elif script_args.function == Namespace.FUNCTION_PROCESS:
        process_cli(script_args, constants.EXTENSIONS, PREFIX_HINTS)
    elif script_args.function == Namespace.FUNCTION_UPDATE_LIBRARY:
        update_library(script_args.input,
                       script_args.output,
                       script_args.client_mirror_path,
                       script_args.collection_backup_directory,
                       script_args.interactive,
                       constants.EXTENSIONS,
                       PREFIX_HINTS)
    elif script_args.function == Namespace.FUNCTION_RECORD_UNPLAYED:
        record_unplayed_tracks(script_args.input, script_args.output)
