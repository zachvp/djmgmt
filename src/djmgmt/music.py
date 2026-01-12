'''
# Summary
Functions to scan and manipulate a batch of music files.

    - sweep:           Moves all music files and archives from source to target
    - flatten:         Recusrively flattens all files in a given directory
    - extract:         Extract files from all archives in a given directory.
    - compress:        Zips the contents of a given directory.
    - prune:           Removes all empty folders and non-music files from a directory.
    - prune_non_music  Removes all non-music files from a directory.
    - process:         Convenience function to run sweep, extract, flatten, standardize lossless encodings, and prune from source to target.
    - update_library   Processes a directory containing music files into a local library folder, then syncs the updated library.
    - record_dynamic   Updates both 'dynamic.played' and 'dynamic.unplayed' playlists in an XML collection based on archive and pruned tracks.
'''

import argparse
import os
import shutil
import zipfile
import logging

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from . import constants
from . import common
from . import encode
from . import library
from .tags import Tags
from .common import FileMapping
from .sync import SyncResult

# constants
PREFIX_HINTS = {'beatport_tracks', 'juno_download'}

# classes
@dataclass
class ProcessResult:
    '''Results from processing music files.'''
    processed_files: list[FileMapping]
    missing_art_paths: list[str]
    archives_extracted: int
    files_encoded: int

@dataclass
class RecordResult:
    '''Results from recording tracks to XML collection.'''
    # TODO: include XML collection path, remove collection_root
    collection_root: ET.Element
    tracks_added: int
    tracks_updated: int

@dataclass
class UpdateLibraryResult:
    '''Complete results from library update operation.'''
    process_result: ProcessResult
    record_result: RecordResult
    sync_result: SyncResult
    changed_mappings: list[FileMapping]

class Namespace(argparse.Namespace):
    '''Command-line arguments for music module.'''

    # Required
    function: str

    # Optional (alphabetical)
    client_mirror_path: str
    dry_run: bool
    input: str
    output: str

    # Function constants
    FUNCTION_SWEEP = 'sweep'
    FUNCTION_FLATTEN = 'flatten'
    FUNCTION_EXTRACT = 'extract'
    FUNCTION_COMPRESS = 'compress'
    FUNCTION_PRUNE = 'prune'
    FUNCTION_PROCESS = 'process'
    FUNCTION_PRUNE_NON_MUSIC = 'prune_non_music'
    FUNCTION_UPDATE_LIBRARY = 'update_library'

    FUNCTIONS_SINGLE_ARG = {FUNCTION_COMPRESS, FUNCTION_FLATTEN, FUNCTION_PRUNE, FUNCTION_PRUNE_NON_MUSIC}
    FUNCTIONS = {FUNCTION_SWEEP, FUNCTION_EXTRACT, FUNCTION_PROCESS, FUNCTION_UPDATE_LIBRARY}.union(FUNCTIONS_SINGLE_ARG)

# Helper functions
def parse_args(valid_functions: set[str], single_arg_functions: set[str],
               argv: list[str]) -> Namespace:
    '''Parse command line arguments.

    Args:
        valid_functions: Set of valid function names
        single_arg_functions: Functions that only require --input (not --output)
        argv: Optional argument list for testing (defaults to sys.argv)
    '''
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    # Required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(valid_functions))}")

    # Optional: all function parameters (alphabetical)
    parser.add_argument('--client-mirror-path', '-m', type=str,
                       help='Client mirror path for media sync')
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help="Executes in dry run mode so only read operations are performed. Outputs and logs summary of what *would* happen in normal mode.")
    parser.add_argument('--input', '-i', type=str,
                       help='Input directory or file path')
    parser.add_argument('--output', '-o', type=str,
                       help='Output directory or file path')

    # Parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # Normalize paths (only if not None)
    common.normalize_arg_paths(args, ['input', 'output', 'client_mirror_path'])

    # Validate function
    if args.function not in valid_functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(valid_functions))}")

    # Function-specific validation
    _validate_function_args(parser, args, single_arg_functions)

    # Handle output defaulting to input for single-arg functions
    if not args.output and args.function in single_arg_functions:
        args.output = args.input

    return args


def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace, single_arg_functions: set[str]) -> None:
    '''Validate function-specific required arguments.'''

    # All functions require --input
    if not args.input:
        parser.error(f"'{args.function}' requires --input")

    # Multi-arg functions require --output (single-arg functions use input as output)
    if args.function not in single_arg_functions and not args.output:
        parser.error(f"'{args.function}' requires --output")

    # update_library requires additional paths
    if args.function == Namespace.FUNCTION_UPDATE_LIBRARY:
        if not args.client_mirror_path:
            parser.error(f"'{args.function}' requires --client-mirror-path")

        # Validate paths exist
        if not os.path.exists(args.client_mirror_path):
            parser.error(f"--client-mirror-path '{args.client_mirror_path}' does not exist")

def compress_dir(input_path: str, output_path: str) -> tuple[str, list[str]]:
    '''Compresses all files in a directory into a zip archive.

    Args:
        input_path: Directory containing files to compress (e.g., '/path/to/tracks')
        output_path: Base path for output archive without .zip extension (e.g., '/output/myarchive')

    Returns:
        Tuple of (archive_path, list of compressed file paths)

    Example:
        >>> compress_dir('/music/album', '/archives/album')
        ('/archives/album.zip', ['/music/album/track1.mp3', '/music/album/track2.mp3'])
    '''
    compressed: list[str] = []
    archive_path = f"{output_path}.zip"
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file_path in common.collect_paths(input_path):
            name = os.path.basename(file_path)
            archive.write(file_path, arcname=name)
            compressed.append(file_path)
    return (archive_path, compressed)

def is_prefix_match(value: str, prefixes: set[str]) -> bool:
    '''Checks if a string starts with any of the given prefixes.

    Args:
        value: String to check (e.g., 'beatport_tracks_20231027')
        prefixes: Set of prefix strings to match against (e.g., {'beatport_tracks', 'juno_download'})

    Returns:
        True if value starts with any prefix, False otherwise

    Example:
        >>> is_prefix_match('beatport_tracks_20231027', {'beatport_tracks', 'juno_download'})
        True
        >>> is_prefix_match('random_archive', {'beatport_tracks', 'juno_download'})
        False
    '''
    for prefix in prefixes:
        if value.startswith(prefix):
            return True
    return False

def prune(working_dir: str, directories: list[str], filenames: list[str]) -> None:
    '''Removes hidden files, hidden directories, and .app archives from the given lists in-place.

    Args:
        working_dir: Base directory path for logging purposes (e.g., '/music/library')
        directories: List of directory names to filter (modified in-place)
        filenames: List of filenames to filter (modified in-place)

    Example:
        >>> dirs = ['Album', '.hidden', '_temp', 'App.app']
        >>> files = ['track.mp3', '.DS_Store', 'cover.jpg']
        >>> prune('/music', dirs, files)
        >>> dirs
        ['Album']
        >>> files
        ['track.mp3', 'cover.jpg']
    '''
    for index, directory in enumerate(directories):
        if is_prefix_match(directory, {'.', '_'}) or '.app' in directory:
            logging.info(f"prune: hidden directory or '.app' archive '{os.path.join(working_dir, directory)}'")
            del directories[index]
    for index, name in enumerate(filenames):
        if name.startswith('.'):
            logging.info(f"prune: hidden file '{name}'")
            del filenames[index]
def flatten_zip(zip_path: str, extract_path: str) -> None:
    '''Extracts a zip archive and moves all files to the extract path root, removing nested directories.

    Args:
        zip_path: Path to the zip archive (e.g., '/downloads/album.zip')
        extract_path: Directory to extract and flatten into (e.g., '/music/temp')

    Example:
        Given archive structure:
            album.zip
            └── album/
                ├── track1.mp3
                └── track2.mp3

        After flatten_zip('/downloads/album.zip', '/music/temp'):
            /music/temp/
            ├── track1.mp3
            └── track2.mp3
    '''
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

def standardize_lossless(source: str, valid_extensions: set[str], prefix_hints: set[str], dry_run: bool = False) -> list[FileMapping]:
    '''Standardizes all lossless files in the source directory according to `.encode.encode_lossless()` using the .aiff extension.
    Returns a list of each (source, encoded_file) mapping.'''
    from tempfile import TemporaryDirectory
    import asyncio
    
    # create a temporary directory to place the encoded files.
    with TemporaryDirectory() as temp_dir:
        # encode all non-standard lossless files
        result = asyncio.run(encode.encode_lossless(source, temp_dir, '.aiff', dry_run=dry_run))
        
        # remove all of the original non-standard files that have been encoded.
        for input_path, _ in result:
            if dry_run:
                common.log_dry_run('remove directory', f"{input_path}")
            else:
                os.remove(input_path)
        # sweep all the encoded files from the temporary directory to the original source directory
        sweep(temp_dir, source, valid_extensions, prefix_hints, dry_run=dry_run)
        return result

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
    root          = library.load_collection(xml_path)
    collection    = library.find_node(root, constants.XPATH_COLLECTION)
    playlist_root = library.find_node(root, constants.XPATH_PLAYLISTS)
    pruned        = library.find_node(root, constants.XPATH_PRUNED)
    
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

# Primary functions
def sweep(source: str, output: str, valid_extensions: set[str], prefix_hints: set[str], dry_run: bool = False) -> list[FileMapping]:
    '''Moves all music files and valid archives from source to output directory.

    Validates archives by inspecting contents - archives must contain music files and not contain .app files.
    Archives matching prefix_hints (e.g., 'beatport_tracks') are automatically considered valid.

    Args:
        source: Directory to scan for music files (e.g., '/downloads')
        output: Destination directory (e.g., '/music/staging')
        valid_extensions: Set of valid music file extensions (e.g., {'.mp3', '.aiff', '.wav'})
        prefix_hints: Set of archive name prefixes to auto-validate (e.g., {'beatport_tracks', 'juno_download'})

    Returns:
        List of (source_path, destination_path) tuples for all moved files

    Example:
        >>> sweep('/downloads', '/music/staging', False, {'.mp3', '.aiff'}, {'beatport_tracks'})
        [('/downloads/track1.mp3', '/music/staging/track1.mp3'),
         ('/downloads/beatport_tracks.zip', '/music/staging/beatport_tracks.zip')]
    '''
    swept: list[FileMapping] = []
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
            logging.debug(f"move from '{input_path}' to '{output_path}'")
            if dry_run:
                common.log_dry_run('move', f"{input_path} -> {output_path}")
            else:
                shutil.move(input_path, output_path)
            swept.append((input_path, output_path))
    logging.info(f"swept all files ({len(swept)})\n{swept}")
    return swept    

def sweep_cli(args: Namespace, valid_extensions: set[str], prefix_hints: set[str]) -> None:
    '''CLI wrapper for the core sweep function.'''
    sweep(args.input, args.output, valid_extensions, prefix_hints)

def flatten_hierarchy(source: str, output: str, dry_run: bool = False) -> list[FileMapping]:
    '''Recursively moves all files from nested directories to the output root, removing the directory structure.

    Args:
        source: Directory to flatten (e.g., '/music/nested')
        output: Destination directory for flattened files (e.g., '/music/flat')
        interactive: If True, prompts for confirmation before each move

    Returns:
        List of (source_path, destination_path) tuples for all moved files

    Example:
        Given structure:
            /music/nested/
            ├── album1/track1.mp3
            └── album2/track2.mp3

        >>> flatten_hierarchy('/music/nested', '/music/flat', False)
        [('/music/nested/album1/track1.mp3', '/music/flat/track1.mp3'),
         ('/music/nested/album2/track2.mp3', '/music/flat/track2.mp3')]
    '''
    flattened: list[FileMapping] = []
    for input_path in common.collect_paths(source):
        name = os.path.basename(input_path)
        output_path = os.path.join(output, name)

        # move the files to the output root
        if not os.path.exists(output_path):
            logging.debug(f"move '{input_path}' to '{output_path}'")
            try:
                if dry_run:
                    common.log_dry_run('move', f"'{input_path}' -> '{output_path}'")
                else:
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

def flatten_hierarchy_cli(args: Namespace) -> None:
    '''CLI wrapper for the core flatten_hierarchy function.'''
    flatten_hierarchy(args.input, args.output, args.interactive)

def extract_all_normalized_encodings(zip_path: str, output: str, dry_run: bool = False) -> tuple[str, list[str]]:
    '''Extracts all files from a zip archive with normalized filename encodings.

    Handles common zip encoding issues by attempting to correct filenames using UTF-8 and Latin-1 encodings.

    Args:
        zip_path: Path to the zip archive (e.g., '/downloads/beatport_tracks.zip')
        output: Directory to extract files into (e.g., '/temp/extracted')

    Returns:
        Tuple of (original zip path, list of extracted filenames)

    Example:
        >>> extract_all_normalized_encodings('/downloads/tracks.zip', '/temp')
        ('/downloads/tracks.zip', ['01 Track One.mp3', '02 Track Two.mp3'])
    '''
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
            output_path = os.path.normpath(output)
            if dry_run:
                input_path = os.path.join(zip_path, info.filename)
                common.log_dry_run('extract', f"file {input_path} -> {output_path}")
            else:
                file.extract(info, output_path)
            extracted.append(info.filename)
    logging.debug(f"extracted archive '{zip_path}' to {extracted}")
    return (zip_path, extracted)

def extract(source: str, output: str, dry_run: bool = False) -> list[tuple[str, list[str]]]:
    '''Extracts all zip archives in the source directory to the output directory.

    Args:
        source: Directory to scan for zip archives (e.g., '/music/archives')
        output: Destination directory for extracted files (e.g., '/music/extracted')

    Returns:
        List of (archive_path, list of extracted filenames) tuples

    Example:
        >>> extract('/music/archives', '/music/extracted', False)
        [('/music/archives/album1.zip', ['track1.mp3', 'track2.mp3']),
         ('/music/archives/album2.zip', ['track3.mp3', 'track4.mp3'])]
    '''
    extracted: list[tuple[str, list[str]]] = []
    for input_path in common.collect_paths(source):
        name = os.path.basename(input_path)
        name_split = os.path.splitext(name)
        if name_split[1] == '.zip':
            zip_output_path = os.path.join(output, name_split[0])

            if os.path.exists(zip_output_path) and os.path.isdir(zip_output_path):
                logging.info(f"skip: existing ouput path '{zip_output_path}'")
                continue

            logging.debug(f"extracting '{input_path}' to '{output}'")
            # extract all zip contents, with normalized filename encodings
            extracted.append(extract_all_normalized_encodings(input_path, output, dry_run=dry_run))
        else:
            logging.debug(f"skip: non-zip file '{input_path}'")
    return extracted

def extract_cli(args: Namespace) -> None:
    '''CLI wrapper for the core extract function.'''
    extract(args.input, args.output, args.interactive)

def compress_all_cli(args: Namespace) -> None:
    '''CLI wrapper that compresses each subdirectory in the input path into separate zip archives.

    Example:
        Given structure:
            /input/
            ├── album1/
            └── album2/

        Creates:
            /output/album1.zip
            /output/album2.zip
    '''
    for working_dir, directories, _ in os.walk(args.input):
        for directory in directories:
            compress_dir(os.path.join(working_dir, directory), os.path.join(args.output, directory))

def prune_non_user_dirs(source: str, dry_run: bool = False) -> list[str]:
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
        logging.debug(f"will remove: '{path}'")
        if dry_run:
            common.log_dry_run('remove directory', f"{path}")
        else:
            try:
                shutil.rmtree(path)
            except OSError as e:
                if e.errno == 39: # directory not empty
                    logging.warning(f"skip: non-empty dir {path}")

    # return the pruned directories
    result = list(pruned)
    logging.debug(f"pruned all non-user directories ({len(result)}\n{result})")
    return result

def prune_non_user_dirs_cli(args: Namespace) -> None:
    '''CLI wrapper for the core `prune_non_user_dirs` function.'''
    prune_non_user_dirs(args.input, args.interactive)
    
def prune_non_music(source: str, valid_extensions: set[str], dry_run: bool = False) -> list[str]:
    '''Removes all files that don't have a valid music extension from the given directory.

    Args:
        source: Directory to scan (e.g., '/music/library')
        valid_extensions: Set of valid music file extensions (e.g., {'.mp3', '.aiff', '.wav'})
        interactive: If True, prompts for confirmation before each removal

    Returns:
        List of paths that were removed

    Example:
        >>> prune_non_music('/music/mixed', {'.mp3', '.aiff'}, False)
        ['/music/mixed/readme.txt', '/music/mixed/cover.jpg', '/music/mixed/.DS_Store']
    '''
    pruned = []
    for input_path in common.collect_paths(source):
        _, extension = os.path.splitext(input_path)
        
        # check extension
        if extension not in valid_extensions:
            logging.info(f"non-music file found: '{input_path}'")

            # try to remove the file/dir
            try:
                if os.path.isdir(input_path):
                    if dry_run:
                        common.log_dry_run('remove directory', f"{input_path}")
                    else:
                        shutil.rmtree(input_path)
                    pruned.append(input_path)
                else:
                    if dry_run:
                        common.log_dry_run('remove', f"{input_path}")
                    else:
                        os.remove(input_path)
                    pruned.append(input_path)
                logging.info(f"removed: '{input_path}'")
            except OSError as e:
                msg = f"Error removing file '{input_path}': {str(e)}" # TODO: use helper
                logging.error(msg)
                raise RuntimeError(msg)
    return pruned

def prune_non_music_cli(args: Namespace, valid_extensions: set[str]) -> None:
    '''CLI wrapper for the core prune_non_music function.'''
    prune_non_music(args.input, valid_extensions, args.interactive)

def process(source: str, output: str, valid_extensions: set[str], prefix_hints: set[str], dry_run: bool = False) -> ProcessResult:
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
    from tempfile import TemporaryDirectory

    # track source files to correlate with final output (use filename without extension)
    file_to_source_path: dict[str, str] = {}

    # process all files in a temporary directory, then move the processed files to the output directory
    with TemporaryDirectory() as processing_dir:
        # first sweep: source → processing
        initial_sweep = sweep(source, processing_dir, valid_extensions, prefix_hints, dry_run=dry_run)
        # track for correlation
        for source_path, _ in initial_sweep:
            filename_no_ext = os.path.splitext(os.path.basename(source_path))[0]
            if filename_no_ext in file_to_source_path:
                logging.error(f"Duplicate filename detected: '{filename_no_ext}' from '{source_path}' and '{file_to_source_path[filename_no_ext]}'")
            file_to_source_path[filename_no_ext] = source_path

        # track extracted archives and map extracted files to their archive origin
        extracted = extract(processing_dir, processing_dir, dry_run=dry_run)
        for archive_path, extracted_files in extracted:
            # get the original archive source path
            archive_name_no_ext = os.path.splitext(os.path.basename(archive_path))[0]
            original_archive_source = file_to_source_path.get(archive_name_no_ext, archive_path)

            # map each extracted file to archive_source/filename
            for extracted_file in extracted_files:
                extracted_basename = os.path.basename(extracted_file)
                extracted_name_no_ext = os.path.splitext(extracted_basename)[0]
                
                # build source path as: original_archive.zip/extracted_file.ext
                archive_relative_source = os.path.join(original_archive_source, extracted_basename)
                if extracted_name_no_ext in file_to_source_path:
                    logging.error(f"Duplicate filename detected: '{extracted_name_no_ext}' from '{archive_relative_source}' and '{file_to_source_path[extracted_name_no_ext]}'")
                file_to_source_path[extracted_name_no_ext] = archive_relative_source

        flatten_hierarchy(processing_dir, processing_dir, dry_run=dry_run)

        # track encoded files and prune the processing directory
        encoded = standardize_lossless(processing_dir, valid_extensions, prefix_hints, dry_run=dry_run)
        prune_non_music(processing_dir, valid_extensions, dry_run=dry_run)
        prune_non_user_dirs(processing_dir, dry_run=dry_run)

        # final sweep: processing → output
        final_sweep = sweep(processing_dir, output, valid_extensions, prefix_hints, dry_run=True)

    # map final output back to original source using filename without extension
    processed_files: list[FileMapping] = []
    for processing_path, output_path in final_sweep:
        filename_no_ext = os.path.splitext(os.path.basename(output_path))[0]
        original_source = file_to_source_path.get(filename_no_ext, processing_path)
        processed_files.append((original_source, output_path))

    # Find missing art
    missing = asyncio.run(encode.find_missing_art_os(output, threads=72))
    if dry_run:
        common.log_dry_run('write paths', constants.MISSING_ART_PATH)
    else:
        common.write_paths(missing, constants.MISSING_ART_PATH)

    return ProcessResult(
        processed_files=processed_files,
        missing_art_paths=missing,
        archives_extracted=len(extracted),
        files_encoded=len(encoded)
    )

def process_cli(args: Namespace, valid_extensions: set[str], prefix_hints: set[str]) -> None:
    '''CLI wrapper for the core `process` function.'''
    process(args.input, args.output, valid_extensions, prefix_hints)

def update_library(source: str,
                   library_path: str,
                   client_mirror_path: str,
                   valid_extensions: set[str],
                   prefix_hints: set[str],
                   full_scan: bool = True,
                   dry_run: bool = False) -> UpdateLibraryResult:
    '''Processes music files into library and syncs to media server.

    Performs the following sequence:
        1. Processes files from source dir -> temp dir
        2. Sweeps files from temp dir -> library
        3. Records the updated library to the XML collection
        4. Collects library -> client mirror file mappings according to the new files added to the XML collection
        5. Adds file mappings according to metadata differences between library <-> client mirror
        6. Syncs the new and changed files from library -> client mirror path -> media server

    Args:
        source: Directory containing new music files to process (e.g., '/downloads/new_music')
        library_path: Main library directory with date structure (e.g., '/music/library')
        client_mirror_path: Local mirror of media server files (e.g., '/music/mirror')
        valid_extensions: Set of valid music file extensions (e.g., {'.mp3', '.aiff', '.wav'})
        prefix_hints: Set of archive name prefixes to auto-validate (e.g., {'beatport_tracks', 'juno_download'})
        dry_run: If True, skips all destructive operations, logging and returning what *would* be done.
        full_scan: If True, triggers full media server scan after sync

    Example:
        >>> update_library(
        ...     '/downloads/new_tracks',
        ...     '/music/library',
        ...     '/music/mirror',
        ...     False,
        ...     {'.mp3', '.aiff'},
        ...     {'beatport_tracks'},
        ...     full_scan=True,
        ...     dry_run=True
        ... )

    Note:
        The source, library, and client_mirror_path arguments should all be distinct directories.
    '''
    from . import sync
    from . import tags_info
    
    # process all of the source files into the library dir
    process_result = process(source, library_path, valid_extensions, prefix_hints, dry_run=dry_run)

    # update the processed collection according to any new files
    record_result = record_collection(library_path, constants.COLLECTION_PATH_PROCESSED, dry_run=dry_run)

    # combine any changed mappings in _pruned with the standard filtered collection mappings
    changed = tags_info.compare_tags(library_path, client_mirror_path)
    changed = library.filter_path_mappings(changed, record_result.collection_root, constants.XPATH_PRUNED)
    mappings = sync.create_sync_mappings(record_result.collection_root, client_mirror_path)
    if changed:
        mappings += changed
    
    # run the sync
    sync_result = sync.run_sync_mappings(mappings, full_scan=full_scan, dry_run=dry_run)
    
    return UpdateLibraryResult(process_result=process_result,
                               record_result=record_result,
                               changed_mappings=changed,
                               sync_result=sync_result)

if __name__ == '__main__':
    import sys
    
    # log config
    common.configure_log(path=__file__)

    # parse arguments
    script_args = parse_args(Namespace.FUNCTIONS, Namespace.FUNCTIONS_SINGLE_ARG, sys.argv[1:])
    logging.info(f"will execute: '{script_args.function}'")

    # function dispatch
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
        result = update_library(script_args.input,
                                script_args.output,
                                script_args.client_mirror_path,
                                constants.EXTENSIONS,
                                PREFIX_HINTS,
                                dry_run=script_args.dry_run)
        if script_args.dry_run:
            common.log_dry_run('process', f"{len(result.process_result.processed_files)} files")
            common.log_dry_run('write', f"{len(result.process_result.missing_art_paths)} missing art files")
            common.log_dry_run('extract', f"{result.process_result.archives_extracted} archives")
            common.log_dry_run('encode', f"{result.process_result.files_encoded} lossless files")
            common.log_dry_run_data('process_result', result.process_result)
            
            common.log_dry_run('record_collection', f"for {script_args.output} files")
            common.log_dry_run_data('record_result', result.record_result)
            
            common.log_dry_run('sync', f"to server")
            common.log_dry_run_data('sync_result', result.sync_result)
            
            common.log_dry_run('sync', f"{len(result.changed_mappings)} changed mappings")
            common.log_dry_run_data('changed_mappings', result.changed_mappings)

