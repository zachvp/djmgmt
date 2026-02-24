'''
# Summary
Functions to transfer audio files and playlists to a remote media server.

    - music:     Syncs date-structured music files to the media server by encoding to MP3, rsyncing in chronological batches, and triggering a remote library scan.
    - playlist:  Generates a Navidrome M3U8 playlist from a Rekordbox collection and rsyncs it to the media server.
    - preview:   Previews files that would be synced to a client mirror from the _pruned playlist, showing new tracks and metadata changes.
'''

import argparse
import datetime
import os
import sys
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

from . import common
from . import constants
from .library import TrackMetadata
from .common import FileMapping

# Data classes
@dataclass
class SyncBatchResult:
    '''Results from syncing a single date context batch.'''
    date_context: str
    files_processed: int
    success: bool

@dataclass
class SyncResult:
    '''Complete results from sync operation.'''
    mappings: list[FileMapping]
    batches: list[SyncBatchResult]

# Classes
class Namespace(argparse.Namespace):
    '''Command-line arguments for sync module.'''

    # Required
    function: str

    # Optional (alphabetical)
    client_mirror_path: str
    collection: str
    dry_run: bool
    end_date: str | None
    input: str
    library_path: str
    output: str
    playlist_path: str
    scan_mode: str
    sync_mode: str

    # Function constants
    FUNCTION_MUSIC = 'music'
    FUNCTION_PREVIEW = 'preview'
    FUNCTION_PLAYLIST = 'playlist'

    FUNCTIONS = {FUNCTION_MUSIC, FUNCTION_PREVIEW, FUNCTION_PLAYLIST}

    # Scan mode constants
    SCAN_QUICK = 'quick'
    SCAN_FULL = 'full'

    SCAN_MODES = {SCAN_QUICK, SCAN_FULL}

    # Music sync mode constants
    SYNC_MODE_LOCAL = 'local'
    SYNC_MODE_REMOTE = 'remote'

    SYNC_MODES = {SYNC_MODE_LOCAL, SYNC_MODE_REMOTE}
    
class SavedDateContext:
    FILE_SYNC =f"{constants.PROJECT_ROOT}{os.sep}state{os.sep}sync_state.txt"

    @staticmethod
    def to_timestamp(context: str) -> int:
        '''Converts a date_context string to a Unix timestamp (midnight UTC).'''
        parts = context.split('/')
        year = int(parts[0])
        month = int(parts[1].split()[0])
        day = int(parts[2])
        return int(datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc).timestamp())

    @staticmethod
    def save(context: str) -> None:
        '''Persists the date context to disk.'''
        timestamp = SavedDateContext.to_timestamp(context)
        with open(SavedDateContext.FILE_SYNC, encoding='utf-8', mode='w') as state:
            state.write(f"{context}, {timestamp}")

    @staticmethod
    def load() -> tuple[str, int] | None:
        '''Loads the saved context from disk.'''
        with open(SavedDateContext.FILE_SYNC, encoding='utf-8', mode='r') as state: # todo: optimize to only open if recent change
            saved_state = state.readline()
            if saved_state:
                context, ts_str = saved_state.rsplit(',', 1)
                return (context.strip(), int(ts_str.strip()))
        return None

    @staticmethod
    def is_processed(date_context: str) -> bool:
        saved = SavedDateContext.load()
        if saved:
            _, saved_timestamp = saved
            if SavedDateContext.to_timestamp(date_context) <= saved_timestamp:
                logging.info(f"already processed date context: {date_context}")
                return True
        logging.info(f"date context is unprocessed: {date_context}")
        return False

@dataclass
class SyncPreviewTrack:
    '''Represents a track that would be synced, with metadata and sync status.'''
    metadata: TrackMetadata
    change_type: str  # 'new' or 'changed'

def parse_args(valid_functions: set[str], valid_scan_modes: set[str], valid_sync_modes: set[str],
               argv: list[str]) -> Namespace:
    '''Parse command line arguments.


    Args:
        valid_functions: Set of valid function names
        valid_scan_modes: Set of valid scan mode names
        valid_sync_modes: Set of valid sync mode names
        argv: Optional argument list for testing (defaults to sys.argv)
    '''
    parser = argparse.ArgumentParser()

    # Required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(valid_functions))}")

    # Optional: all function parameters (alphabetical)
    # TODO: condense these so more sharing across functions
    parser.add_argument('--client-mirror-path', '-m', type=str,
                       help="Client mirror path (for preview_sync)")
    parser.add_argument('--collection', '-c', type=str,
                       help="Rekordbox XML collection file path (for preview_sync)")
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help="Executes in dry run mode so only read operations are performed. Outputs and logs summary of what *would* happen in normal mode.")
    parser.add_argument('--end-date', type=str,
                       help="Optional end date context (e.g., '2025/10 october/09'). Sync will stop after processing this date")
    parser.add_argument('--input', '-i', type=str,
                       help="Input directory (date-structured: /year/month/day/...)")
    parser.add_argument('--library-path', '-l', type=str,
                       help="Library path (for preview_sync)")
    parser.add_argument('--output', '-o', type=str,
                       help="Output directory to populate")
    parser.add_argument('--playlist-path', '-p', type=str,
                       help="Dot-separated Rekordbox playlist path (e.g. 'dynamic.unplayed')")
    parser.add_argument('--scan-mode', type=str, choices=list(valid_scan_modes),
                       help="Scan mode for the server")
    parser.add_argument('--sync-mode', type=str, choices=list(valid_sync_modes),
                       default=Namespace.SYNC_MODE_REMOTE,
                       help="Sync mode: 'local' (encode only) or 'remote' (encode + transfer). Default: 'remote'")

    # Parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # Normalize paths (only if not None)
    common.normalize_arg_paths(args, ['input', 'output', 'collection', 'client_mirror_path', 'library_path'])

    # Validate function
    if args.function not in valid_functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(valid_functions))}")

    # Function-specific validation
    _validate_function_args(parser, args)

    return args

def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''

    if args.function == Namespace.FUNCTION_PREVIEW:
        # preview_sync requires different arguments
        if not args.collection:
            parser.error(f"'{args.function}' requires --collection")
        if not args.client_mirror_path:
            parser.error(f"'{args.function}' requires --client-mirror-path")
        if not args.library_path:
            parser.error(f"'{args.function}' requires --library-path")
    elif args.function == Namespace.FUNCTION_PLAYLIST:
        if not args.collection:
            parser.error(f"'{args.function}' requires --collection")
        if not args.playlist_path:
            parser.error(f"'{args.function}' requires --playlist-path")
    else:
        # Other functions require --input, --output, and --scan-mode
        if not args.input:
            parser.error(f"'{args.function}' requires --input")
        if not args.output:
            parser.error(f"'{args.function}' requires --output")
        # only remote sync requires scan mode
        if args.sync_mode == Namespace.SYNC_MODE_REMOTE and not args.scan_mode:
            parser.error(f"'{args.function}' requires --scan-mode")

# Helper functions
def relative_paths(paths: list[str], parent: str) -> list[str]:
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
    '''Rsync-specific. Transforms the given path into a format that will include the required subdirectories.
        Example:
        path: /Users/user/developer/test-private/data/tracks-output/2022/04 april/24/1-Gloria_Jones_-_Tainted_Love_(single_version).mp3
            -> 
             /Users/user/developer/test-private/data/tracks-output/./2022/04 april/24/
    '''
    
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

def key_date_context(mapping: FileMapping) -> int:
    date_context = common.find_date_context(mapping[1])
    return SavedDateContext.to_timestamp(date_context[0]) if date_context else 0
    
def transfer_files(source_path: str, dest_address: str, rsync_module: str, dry_run: bool = False) -> tuple[int, str]:
    '''Uses rsync to transfer files using remote daemon.

    Args:
        source_path: Path to source directory
        dest_address: Destination rsync address
        rsync_module: Rsync module name
        dry_run: If True, add --dry-run flag to rsync command

    Example command:
        rsync '/Users/user/developer/test-private/data/tracks-output/./2025/03 march/14'
              rsync://user@pi.local:12000/navidrome --progress -auvzitR --exclude '.*'
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
    #   --dry-run: perform a trial run with no changes made
    options = ' -avzitR --progress --exclude \'.*\''
    if dry_run:
        options += ' --dry-run'
    command = shlex.split(f'rsync {shlex.quote(source_path)} {dest_address}/{rsync_module} {options}')
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
def sync_batch(batch: list[FileMapping], date_context: str, source: str, full_scan: bool, sync_mode: str, dry_run: bool = False) -> SyncBatchResult:
    '''Transfers all files in the batch to the given destination, then tells the music server to perform a scan.

    Args:
        batch: List of file mappings to sync
        date_context: Date context string (e.g., '2023/01 january/01')
        source: Source directory path
        full_scan: Whether to perform full scan on server
        sync_mode: Sync mode (local or remote)
        dry_run: If True, skip API calls

    Returns:
        SyncBatchResult with date_context, files_processed count, and success status
    '''
    import asyncio
    from . import subsonic_client, encode

    # return flag
    success = True

    # encode the current batch to MP3 format
    logging.info(f"encoding batch in date context {date_context}:\n{batch}")
    asyncio.run(encode.encode_lossy(batch, '.mp3', threads=28, dry_run=dry_run))
    logging.info(f"finished encoding batch in date context {date_context}")

    # skip remote transfer if in local mode
    if sync_mode == Namespace.SYNC_MODE_LOCAL:
        logging.info('local sync mode: skipping remote transfer and scan')
        return SyncBatchResult(date_context=date_context, files_processed=len(batch), success=True)

    # transfer batch to the media server (remote mode only)
    transfer_path = transform_implied_path(source)
    success = bool(transfer_path)
    if transfer_path:
        logging.info(f"transferring files from {source}")
        returncode, _ = transfer_files(transfer_path, constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME, dry_run=dry_run)
        
        success = returncode == 0
        # no actual paths are created in dry run mode, so rsync is unable to sync anything
        if dry_run:
            success = returncode == 23

        # check if file transfer succeeded
        if success:
            # skip API calls in dry-run mode
            if dry_run:
                logging.info('[DRY-RUN] Would initiate remote scan')
                return SyncBatchResult(date_context=date_context, files_processed=len(batch), success=True)

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

    return SyncBatchResult(date_context=date_context, files_processed=len(batch), success=success)

def sync_mappings(mappings:list[FileMapping], full_scan: bool, sync_mode: str, dry_run: bool = False) -> list[SyncBatchResult]:
    '''Syncs file mappings by batching them by date context.

    Args:
        mappings: List of file mappings to sync
        full_scan: Whether to perform full scan on server
        sync_mode: Sync mode (local or remote)
        dry_run: If True, skip state file writes

    Returns:
        list[SyncBatchResult] containing results from each batch, or an empty list if no mappings were synced
    '''
    # validation
    if len(mappings) < 1:
        return []
    
    # core data
    batch: list[FileMapping] = []
    dest_previous = mappings[0][1]
    date_context, dest = '', ''
    index = 0
    batch_results: list[SyncBatchResult] = []

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
            result = sync_batch(batch, date_context_previous, os.path.dirname(dest_previous), full_scan, sync_mode, dry_run=dry_run)
            batch_results.append(result)
            if not result.success:
                raise RuntimeError(f"Batch sync failed for date context '{date_context_previous}'")
            batch.clear()
            batch.append(mapping) # add the first mapping of the new context
            logging.debug(f"add new context mapping: {mapping}")

            # persist the latest processed context (skip in dry-run mode)
            if not dry_run and not SavedDateContext.is_processed(date_context_previous):
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
        result = sync_batch(batch, date_context, os.path.dirname(dest), full_scan, sync_mode, dry_run=dry_run)
        batch_results.append(result)
        if not result.success:
            raise RuntimeError(f"Batch sync failed for date context '{date_context}'")

        # persist the latest processed context (skip in dry-run mode)
        if not dry_run and not SavedDateContext.is_processed(date_context):
            SavedDateContext.save(date_context)
        logging.info(f"processed batch in date context '{date_context}'")
        logging.info(f"sync progress: {progressFormat(index + 1)}")

    return batch_results

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
    
def create_sync_mappings(root: ET.Element, output_dir: str) -> list[FileMapping]:
    '''Creates a mapping list of system paths based on the given XML collection and output directory.
    Each list entry maps from a source collection file path to a target date-structured file path.
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
                                           metadata_path=False)

    # filter out processed date contexts from the mappings
    filtered_mappings: list[FileMapping] = []
    for input_path, output_path in mappings:
        context = common.find_date_context(output_path)
        if context and not SavedDateContext.is_processed(context[0]):
            filtered_mappings.append((input_path, output_path))

    return filtered_mappings

def preview_sync(collection: ET.Element,
                client_mirror_path: str,
                library_path: str) -> list[SyncPreviewTrack]:
    '''Previews files that would be synced from _pruned playlist to client mirror.

    Returns tracks with metadata and change type (new/changed).
    Mirrors the logic from music.update_library (lines 632-636).
    '''
    from . import tags_info
    from . import library

    preview_tracks: list[SyncPreviewTrack] = []

    # Get new files from _pruned playlist (not yet in client mirror)
    new_mappings = create_sync_mappings(collection, client_mirror_path)

    # Get files with metadata changes (library vs client mirror)
    changed_mappings = tags_info.compare_tags(library_path, client_mirror_path)
    changed_mappings = library.filter_path_mappings(changed_mappings, collection, constants.XPATH_PRUNED)

    # Convert mappings to preview tracks with metadata
    collection_node = library.find_node(collection, constants.XPATH_COLLECTION)

    for source_path, _ in new_mappings:
        metadata = library.extract_track_metadata_by_path(collection_node, source_path)
        if metadata:
            preview_tracks.append(SyncPreviewTrack(metadata=metadata, change_type='new'))

    for source_path, _ in changed_mappings:
        metadata = library.extract_track_metadata_by_path(collection_node, source_path)
        if metadata:
            preview_tracks.append(SyncPreviewTrack(metadata=metadata, change_type='changed'))

    return preview_tracks

# Primary functions
def run_music(mappings: list[FileMapping],
              full_scan: bool = True,
              sync_mode: str = Namespace.SYNC_MODE_REMOTE,
              end_date: str | None = None,
              dry_run: bool = False) -> SyncResult:
    '''Runs the music sync process with the given file mappings, returning the result. Sorts mappings according to date context,
    and filters mappings according to the current date context state.
    '''
    # record initial run timestamp
    timestamp = time.time()

    # only attempt sync if remote is accessible (skip healthcheck for local mode)
    if sync_mode == Namespace.SYNC_MODE_REMOTE and not rsync_healthcheck():
        raise RuntimeError("rsync unhealthy, abort sync")

    # sort the mappings so they are synced in chronological order
    mappings.sort(key=lambda m: key_date_context(m))

    # filter mappings based on end_date if provided
    if end_date:
        filtered_mappings: list[FileMapping] = []
        end_timestamp = SavedDateContext.to_timestamp(end_date)
        for mapping in mappings:
            date_context = common.find_date_context(mapping[1])
            if date_context and SavedDateContext.to_timestamp(date_context[0]) <= end_timestamp:
                filtered_mappings.append(mapping)
            elif date_context and SavedDateContext.to_timestamp(date_context[0]) > end_timestamp:
                logging.info(f"skipping mapping with date context '{date_context[0]}' (after end_date '{end_date}')")

        logging.info(f"filtered mappings from {len(mappings)} to {len(filtered_mappings)} based on end_date '{end_date}'")
        mappings = filtered_mappings

    # initialize timing and run the sync
    try:
        batch_results = sync_mappings(mappings, full_scan, sync_mode, dry_run=dry_run)
    except Exception as e:
        logging.error(e)
        raise
    timestamp = time.time() - timestamp
    logging.info(f"sync duration: {format_timing(timestamp)}")
    return SyncResult(mappings=mappings, batches=batch_results)

def run_playlist(collection: str, playlist_dot_path: str, dry_run: bool = False) -> FileMapping | None:
    '''Generates a Navidrome M3U8 playlist from a Rekordbox collection and rsyncs it to the media server.

    Args:
        collection: Path to Rekordbox XML collection file
        playlist_path: Dot-separated playlist path (e.g., "dynamic.unplayed")
        dry_run: If True, skip destructive operations

    Returns:
        FileMapping tuple (local_path, rsync_path) on success, None on failure.
    '''
    from . import playlist

    # Build output path: state/output/playlists/{playlist_name}.m3u8
    playlist_name = playlist_dot_path.replace('.', '_')
    os.makedirs(constants.PLAYLIST_OUTPUT_PATH, exist_ok=True)
    local_path = f"{constants.PLAYLIST_OUTPUT_PATH}{os.path.sep}{playlist_name}.m3u8"

    # Generate M3U8
    logging.info(f"generating playlist '{playlist_dot_path}' to '{local_path}'")
    tracks = playlist.generate_m3u8(collection, playlist_dot_path, local_path, dry_run=dry_run)
    if not tracks:
        logging.error(f"playlist generation failed or returned no tracks for '{playlist_dot_path}'")
        return None

    # Check rsync daemon
    if not rsync_healthcheck():
        logging.error('rsync daemon unreachable; aborting playlist sync')
        return None

    # Rsync: use ./playlists/ so -R flag preserves subdirectory at remote root
    # Result: navidrome/playlists/{name}.m3u8 -> /media/zachvp/SOL/music/playlists/{name}.m3u8
    output_base = str(constants.STATE_PATH_BASE / 'output')
    rsync_implied_path = f"{output_base}/./playlists/{playlist_name}.m3u8"
    returncode, _ = transfer_files(rsync_implied_path, constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME, dry_run=dry_run)
    if returncode != 0:
        logging.error(f"playlist rsync failed (code {returncode})")
        return None

    logging.info(f"playlist sync complete: {len(tracks)} tracks")
    return (local_path, rsync_implied_path)

# TODO add interactive mode to confirm sync state before any sync batch is possible
def main(argv: list[str]) -> None:
    common.configure_log_module(__file__, level=logging.DEBUG)
    script_args = parse_args(Namespace.FUNCTIONS, Namespace.SCAN_MODES, Namespace.SYNC_MODES, argv[1:])

    logging.info(f"running function '{script_args.function}'")
    if script_args.function == Namespace.FUNCTION_MUSIC:
        from . import library
        tree = library.load_collection(script_args.input)
        mappings = create_sync_mappings(tree, script_args.output)
        full_scan = script_args.scan_mode == Namespace.SCAN_FULL
        sync_result = run_music(mappings, full_scan, script_args.sync_mode, script_args.end_date, dry_run=script_args.dry_run)
        if script_args.dry_run:
            common.log_dry_run('sync', f"{len(sync_result.mappings)} file mappings")
            logging.debug(f"file mappings:\n{sync_result.mappings}")
            common.log_dry_run('sync', f"{len(sync_result.batches)} batches")
            logging.debug(f"batches:\n{sync_result.batches}")
            for batch in sync_result.batches:
                logging.debug(f"{batch.date_context}: {batch.files_processed} files")

    elif script_args.function == Namespace.FUNCTION_PREVIEW:
        from . import library

        # Load collection
        collection = library.load_collection(script_args.collection)

        # Run preview
        preview_tracks = preview_sync(
            collection,
            script_args.client_mirror_path,
            script_args.library_path
        )

        # Display results
        if not preview_tracks:
            print('No tracks to sync - library is up to date!')
        else:
            print(f'Found {len(preview_tracks)} tracks to sync:\n')

            # Group by change type for clearer output
            new_tracks = [t for t in preview_tracks if t.change_type == 'new']
            changed_tracks = [t for t in preview_tracks if t.change_type == 'changed']

            if new_tracks:
                print(f'NEW TRACKS ({len(new_tracks)}):')
                for track in new_tracks:
                    print(f'  {track.metadata.artist} - {track.metadata.title}')
                    print(f'    Album: {track.metadata.album}')
                    print(f'    Path: {track.metadata.path}')
                    print()

            if changed_tracks:
                print(f'CHANGED TRACKS ({len(changed_tracks)}):')
                for track in changed_tracks:
                    print(f'  {track.metadata.artist} - {track.metadata.title}')
                    print(f'    Album: {track.metadata.album}')
                    print(f'    Path: {track.metadata.path}')
                    print()

            print(f'Summary: {len(new_tracks)} new, {len(changed_tracks)} changed')

    elif script_args.function == Namespace.FUNCTION_PLAYLIST:
        run_playlist(script_args.collection, script_args.playlist_path, dry_run=script_args.dry_run)

if __name__ == '__main__':
    main(sys.argv)
