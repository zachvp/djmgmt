'''
# Summary
    1. Scans an input directory of date-structured audio files in chronological order.
    2. Transfers each audio file into the output directory, maintaining the
        date and subdirectory structure of the source directory.
      2a. Suspends process when scan switches from one day to another.

Definitions
    date-structured directory:
        /year/month/day/** (e.g. /2020/january/01/artist/album/audio.file)
    year:       4-digit positive int (e.g. 2023)
    month:      english month name (e.g. january)
    day:        2-digit positive int (e.g 05)
    audio.file: must be an audio file type
'''

import argparse
import os
import shutil
import logging
import time
import xml.etree.ElementTree as ET
from typing import Callable

from . import common
from . import constants

# Classes
class Namespace(argparse.Namespace):
    # script Arguments
    ## required
    function: str
    input: str
    output: str
    scan_mode: str
    
    ## optional
    path_0: str
    
    # functions
    FUNCTION_COPY = 'copy'
    FUNCTION_MOVE = 'move'
    FUNCTION_SYNC = 'sync'
    
    FUNCTIONS = {FUNCTION_COPY, FUNCTION_MOVE, FUNCTION_SYNC}
    
    # scan modes
    SCAN_QUICK = 'quick'
    SCAN_FULL = 'full'
    
    SCAN_MODES = {SCAN_QUICK, SCAN_FULL}
    
class SavedDateContext:
    FILE_SYNC =f"{constants.PROJECT_ROOT}{os.sep}state{os.sep}sync_state.txt"
    FILE_SYNC_KEY = 'sync_date'
    
    @staticmethod
    def save(context: str) -> None:
        '''Persists the date context to disk.'''
        with open(SavedDateContext.FILE_SYNC, encoding='utf-8', mode='w') as state:
            state.write(f"{SavedDateContext.FILE_SYNC_KEY}: {context}")
    
    @staticmethod
    def load() -> str:
        '''Loads the saved context from disk.'''
        with open(SavedDateContext.FILE_SYNC, encoding='utf-8', mode='r') as state: # todo: optimize to only open if recent change
            saved_state = state.readline()
            if saved_state:
                return saved_state.split(':')[1].strip()
        return ''

    @staticmethod
    def is_processed(date_context: str) -> bool:
        date_context_processed = SavedDateContext.load()
        if date_context_processed:
            if date_context <= date_context_processed:
                logging.info(f"already processed date context: {date_context}")
                return True
        logging.info(f"date context is unprocessed: {date_context}")
        return False

def parse_args(valid_functions: set[str], valid_scan_modes: set[str]) -> type[Namespace]:
    ''' Returns the parsed command-line arguments.

    Function arguments:
        valid_modes -- defines the supported script modes
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str, help=f"The mode to apply for the function. One of '{valid_functions}'.")
    parser.add_argument('input', type=str, help="The top level directory to search.\
        It's expected to be structured in a year/month/audio.file format.")
    parser.add_argument('output', type=str, help="The output directory to populate.")
    parser.add_argument('scan_mode', type=str, help=f"The scan mode for the server. One of: '{valid_scan_modes}'.")
    parser.add_argument('--path-0', '-p0', type=str, help="An optional path. Sync uses this as the music root.")

    args = parser.parse_args(namespace=Namespace)
    args.input = os.path.normpath(args.input)
    args.output = os.path.normpath(args.output)

    if args.function not in valid_functions:
        parser.error(f"Invalid function: '{args.function}'")
    if args.scan_mode not in valid_scan_modes:
        parser.error(f"Invalid scan mode: '{args.scan_mode}'")

    return args

# Helper functions
def normalize_paths(paths: list[str], parent: str) -> list[str]:
    '''Returns a collection with the given paths transformed to be relative to the given parent directory.

    Function arguments:
        paths  -- The full paths to transform.
        parent -- The directory that the full paths should be relative to.

    Example:
        path: /full/path/to/file, parent: /full/path -> to/file
    '''
    normalized: list[str] = []
    for path in paths:
        normalized.append(os.path.relpath(path, start=parent))
    return normalized

def transform_implied_path(path: str) -> str | None:
    '''Rsync-specific. Transforms the given path into a format that will include the required subdirectories.'''
    # input : /Users/user/developer/test-private/data/tracks-output/2022/04 april/24/1-Gloria_Jones_-_Tainted_Love_(single_version).mp3
    # output: /Users/user/developer/test-private/data/tracks-output/./2022/04 april/24/
    
    components = path.split(os.sep)[1:]
    if not common.find_date_context(path):
        return None
    transformed = ''
    for i, c in enumerate(components):
        if len(c) == 4 and c.isdecimal() and components[i+1].split()[1] in constants.MAPPING_MONTH.values():
            transformed += f"{os.sep}."
        transformed += f"{os.sep}{c}"
        if common.find_date_context(transformed):
            break
    return transformed

def format_timing(timestamp: float) -> str:
    if timestamp > 60:
        hours, remainder = divmod(timestamp, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds:.3f}s"
    return f"{timestamp:.3f}s"

def key_date_context(mapping: tuple[str, str]) -> str:
    date_context = common.find_date_context(mapping[1])
    return date_context[0] if date_context else ''
    
def transfer_files(source_path: str, dest_address: str, rsync_module: str) -> tuple[int, str]:
    '''Uses rsync to transfer files using remote daemon.
    example command: "rsync '/Users/user/developer/test-private/data/tracks-output/./2025/03 march/14' 
                        rsync://user@pi.local:12000/navidrome --progress -auvzitR --exclude '.*'"
    '''
    import subprocess
    import shlex
    
    logging.info(f"transfer from '{source_path}' to '{dest_address}'")
    
    # Options
    #   -a: archive mode
    #   -v: increase verbosity
    #   -z: compress file data during the transfer
    #   -i: output a change-summary for all updates
    #   -t: preserve modification times
    #   -R: use relative path names
    #   --progess: show progress during transfer
    options = " -avzitR --progress --exclude '.*'"
    command = shlex.split(f"rsync {shlex.quote(source_path)} {dest_address}/{rsync_module} {options}")
    try:
        logging.debug(f'run command: "{shlex.join(command)}"')
        timestamp = time.time()
        process = subprocess.run(command, check=True, capture_output=True, encoding='utf-8')
        timestamp = time.time() - timestamp
        logging.debug(f"duration: {format_timing(timestamp)}\n{process.stdout}".strip())
        return (process.returncode, process.stdout)
    except subprocess.CalledProcessError as error:
        logging.error(f"return code '{error.returncode}':\n{error.stderr}".strip())
        return (error.returncode, error.stderr)

# TODO: add error handling for encoding
def sync_batch(batch: list[tuple[str, str]], date_context: str, source: str, full_scan: bool) -> bool:
    '''Transfers all files in the batch to the given destination, then tells the music server to perform a scan.
    
    Returns True if the batch sync was successful, False otherwise.
    '''
    import asyncio
    from . import subsonic_client, encode
    
    # return flag
    success = True
    
    # encode the current batch to MP3 format
    logging.info(f"encoding batch in date context {date_context}:\n{batch}")
    asyncio.run(encode.encode_lossy(batch, '.mp3', threads=28))
    logging.info(f"finished encoding batch in date context {date_context}")
    
    # transfer batch to the media server
    transfer_path = transform_implied_path(source)
    success = bool(transfer_path)
    if transfer_path:
        logging.info(f"transferring files from {source}")
        returncode, _ = transfer_files(transfer_path, constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME)
        success = returncode == 0
        
        # check if file transfer succeeded
        if success:
            logging.info('file transfer succeeded, initiating remote scan')
            # tell the media server new files are available
            scan_param = 'false'
            if full_scan:
                scan_param = 'true'
            response = subsonic_client.call_endpoint(subsonic_client.API.START_SCAN, {'fullScan': scan_param})
            success = response.ok
            if success:
                # wait until the server has stopped scanning
                while True:
                    # TODO: add error handling
                    response = subsonic_client.call_endpoint(subsonic_client.API.GET_SCAN_STATUS)
                    content = subsonic_client.handle_response(response, subsonic_client.API.GET_SCAN_STATUS)
                    if not content:
                      success = False
                      logging.error('unable to get scan status')  
                    elif content['scanning'] == 'false':
                        logging.info('remote scan complete')
                        break
                    logging.debug("remote scan in progress, waiting...")
                    sleep_time = 5 if full_scan else 1
                    time.sleep(sleep_time)
    return success

def sync_mappings(mappings:list[tuple[str, str]], full_scan: bool) -> None:
    # core data
    batch: list[tuple[str, str]] = []
    dest_previous = mappings[0][1]
    date_context, dest = '', ''
    index = 0
    
    # helper
    progressFormat: Callable[[int], str] = lambda i: f"{(i / len(mappings) * 100):.2f}%"
    logging.info(f"sync progress: {progressFormat(index)}")
    
    # process the file mappings
    logging.debug(f"sync '{len(mappings)}' mappings:\n{mappings}")
    
    for index, mapping in enumerate(mappings):
        dest = mapping[1]
        date_context_previous = common.find_date_context(dest_previous)
        date_context = common.find_date_context(dest)
        
        # validate date contexts        
        if date_context_previous:
            date_context_previous = date_context_previous[0]
        else:
            message = f"no previous date context in path '{dest_previous}'"
            logging.error(message)
            raise ValueError(message)
        if date_context:
            date_context = date_context[0]
        else:
            message = f"no current date context in path '{dest}'"
            logging.error(message)
            raise ValueError(message)
        
        # collect each mapping in a given date context
        if date_context_previous == date_context:
            batch.append(mapping)
            logging.debug(f"add to batch: {mapping}")
        elif batch:
            logging.info(f"processing batch in date context '{date_context_previous}'")
            if not sync_batch(batch, date_context_previous, os.path.dirname(dest_previous), full_scan):
                raise RuntimeError(f"Batch sync failed for date context '{date_context_previous}'")
            batch.clear()
            batch.append(mapping) # add the first mapping of the new context
            logging.debug(f"add new context mapping: {mapping}")
            
            # persist the latest processed context
            if not SavedDateContext.is_processed(date_context_previous):
                SavedDateContext.save(date_context_previous)
            logging.info(f"processed batch in date context '{date_context_previous}'")
            logging.info(f"sync progress: {progressFormat(index + 1)}")
        else:
            batch.append(mapping) # add the first mapping of the new context
            logging.debug(f"add new context mapping: {mapping}")
            logging.info(f"skip empty batch: {date_context_previous}")
        dest_previous = dest
    
    # process the final batch
    if batch and date_context and dest:
        if isinstance(date_context, tuple):
            date_context = date_context[0]
        logging.info(f"processing batch in date context '{date_context}'")
        if not sync_batch(batch, date_context, os.path.dirname(dest), full_scan):
            raise RuntimeError(f"Batch sync failed for date context '{date_context}'")
        
        # persist the latest processed context
        if not SavedDateContext.is_processed(date_context):
            SavedDateContext.save(date_context)
        logging.info(f"processed batch in date context '{date_context}'")
        logging.info(f"sync progress: {progressFormat(index + 1)}")

def rsync_healthcheck() -> bool:
        import subprocess
        import shlex
        
        # check that rsync is running
        command = shlex.split(f"rsync {constants.RSYNC_URL}")
        try:
            subprocess.run(command, check=True, capture_output=True)
            logging.info('rsync daemon is running')
            return True
        except subprocess.CalledProcessError as error:
            # TODO: refactor be lambda function in common
            logging.error(f"return code '{error.returncode}':\n{error.stderr}".strip())
            return False
    
def create_sync_mappings(root: ET.Element, output_dir: str) -> list[tuple[str, str]]:
    '''Creates a mapping list of system paths based on the given XML collection and output directory.
    Each list entry maps from a source collection file path to a target date context + metadata-structured file path.
    See organize_library_dates.generate_date_paths for more info.'''
    from . import library
    
    # collect the target playlist IDs to sync
    pruned = library.find_node(root, constants.XPATH_PRUNED)
    playlist_ids: set[str] = {
        track.attrib[constants.ATTR_TRACK_KEY]
        for track in pruned
    }
    
    # generate the paths to sync based on the target playlist
    collection_node = library.find_node(root, constants.XPATH_COLLECTION)
    mappings = library.generate_date_paths(collection_node,
                                           output_dir,
                                           playlist_ids=playlist_ids,
                                           metadata_path=True)
    
    # filter out processed date contexts from the mappings
    filtered_mappings: list[tuple[str, str]] = []
    for input_path, output_path in mappings:
        context = common.find_date_context(output_path)
        if context and not SavedDateContext.is_processed(context[0]):
            filtered_mappings.append((input_path, output_path))
    
    return filtered_mappings

# Primary functions
def sync_from_path(args: type[Namespace]):
    '''A primary script function.

    Function arguments:
        args -- The parsed command-line arguments.
    '''

    # collect the sorted input paths relative to the input directory
    input_paths = sorted(normalize_paths(common.collect_paths(args.input), args.input))

    # define the date context tracker to determine when a new date context is entered
    previous_date_context = ''

    # assign the action based on the given mode
    action: Callable[[str, str], str] = shutil.copy
    if args.function == Namespace.FUNCTION_MOVE:
        action = shutil.move
    elif args.function != Namespace.FUNCTION_COPY:
        print(f"error: unrecognized mode: {args.function}. Exiting.")
        return

    # performs the configured action for each input and output path
    # waits for user input when input path date context changes
    for path in input_paths:
        # skip any existing valid output paths.
        output_path_full = os.path.join(args.output, path)
        if os.path.exists(output_path_full):
            print(f"info: skip: output path exists: '{output_path_full}'")
            continue
        input_path_full = os.path.join(args.input, path)
        print(f"info: {args.function}: '{input_path_full}' -> {output_path_full}")

        # notify the user if the current date context is different from the previous date context
        date_context = '/'.join(os.path.split(path)[:3]) # format: 'year/month/day'
        if len(previous_date_context) > 0 and previous_date_context != date_context:
            choice = input(f"info: date context changed from '{previous_date_context}' to '{date_context}' continue? [y/N]")
            if choice != 'y':
                print('info: user quit')
                return
        previous_date_context = date_context

        # copy or move the input file to the output path, creating the output directories if needed
        output_parent_path = os.path.split(output_path_full)[0]
        if not os.path.exists(output_parent_path):
            os.makedirs(output_parent_path)
        action(input_path_full, output_path_full)

def run_sync_mappings(mappings: list[tuple[str, str]], full_scan: bool = True) -> None:
    # record initial run timestamp
    timestamp = time.time()
    
    # only attempt sync if remote is accessible
    if not rsync_healthcheck():
        raise RuntimeError("rsync unhealthy, abort sync")
    
    # sort the mappings so they are synced in chronological order
    mappings.sort(key=lambda m: key_date_context(m))
    
    # initialize timing and run the sync
    try:
        sync_mappings(mappings, full_scan)
    except Exception as e:
        logging.error(e)
        raise
    timestamp = time.time() - timestamp
    logging.info(f"sync duration: {format_timing(timestamp)}")

# TODO add interactive mode to confirm sync state before any sync batch is possible
if __name__ == '__main__':
    # setup
    common.configure_log(level=logging.DEBUG, path=__file__)
    script_args = parse_args(Namespace.FUNCTIONS, Namespace.SCAN_MODES)
    
    # run the given command
    logging.info(f"running function '{script_args.function}'")
    if script_args.function in {Namespace.FUNCTION_COPY, Namespace.FUNCTION_MOVE}:
        sync_from_path(script_args)
    elif script_args.function == Namespace.FUNCTION_SYNC:
        from . import library
        tree = library.load_collection(script_args.input)
        mappings = create_sync_mappings(tree, script_args.output)
        run_sync_mappings(mappings)
