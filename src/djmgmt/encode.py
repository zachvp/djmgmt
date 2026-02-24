'''
# Summary
Functions for audio transcoding using ffmpeg.

    - lossless:      Encodes lossless audio files exceeding 44.1kHz/16-bit to the target lossless format.
    - lossy:         Encodes audio files to lossy format (MP3 at 320kbps), preserving cover art from video streams.
    - missing_art:   Identifies tracks missing cover artwork from a Rekordbox XML collection or filesystem scan.
'''

import subprocess
import argparse
import os
import sys
import shlex
import logging
import asyncio
from asyncio import Task
from typing import Any

from . import common
from . import constants
from .common import FileMapping

# classes
class Namespace(argparse.Namespace):
    '''Command-line arguments for encode module.'''

    # Required
    function: str

    # Optional (alphabetical)
    dry_run: bool
    extension: str
    input: str
    interactive: bool
    output: str
    scan_mode: str
    store_path: str
    store_skipped: bool

    # Function constants
    FUNCTION_LOSSLESS    = 'lossless'
    FUNCTION_LOSSY       = 'lossy'
    FUNCTION_MISSING_ART = 'missing_art'

    FUNCTIONS = {FUNCTION_LOSSLESS, FUNCTION_LOSSY, FUNCTION_MISSING_ART}

    # Scan mode constants
    SCAN_MODE_XML = 'xml'
    SCAN_MODE_OS  = 'os'

    SCAN_MODES = {SCAN_MODE_XML, SCAN_MODE_OS}

# helper functions
def parse_args(functions: set[str], argv: list[str]) -> Namespace:
    '''Parse command line arguments.

    Args:
        functions: Set of valid function names
        argv: Optional argument list for testing (defaults to sys.argv)
    '''
    parser = argparse.ArgumentParser()

    # required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(functions))}")

    # optional: all function parameters (alphabetical)
    parser.add_argument('--dry-run', action='store_true',
                       help='Run script in dry run mode')
    parser.add_argument('--extension', '-e', type=str,
                       help='Output file extension (e.g., .aiff, .mp3)')
    parser.add_argument('--input', '-i', type=str,
                       help='Input directory or file path')
    parser.add_argument('--output', '-o', type=str,
                       help='Output directory or file path')
    parser.add_argument('--scan-mode', type=str,
                       help=f"Scan mode for missing art.", choices=list(Namespace.SCAN_MODES))
    parser.add_argument('--store-path', type=str,
                       help='Storage path for script output files')
    parser.add_argument('--store-skipped', action='store_true',
                       help='Store skipped files in storage path')

    # parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # normalize paths
    common.normalize_arg_paths(args, ['input', 'output', 'store_path'])

    # validate function
    if args.function not in functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(functions))}")

    # function-specific validation
    _validate_function_args(parser, args)

    return args

def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''

    EXTENSION_FUNCTIONS = {Namespace.FUNCTION_LOSSLESS, Namespace.FUNCTION_LOSSY}

    # all functions require --input and --output
    if not args.input:
        parser.error(f"'{args.function}' requires --input")
    if not args.output:
        parser.error(f"'{args.function}' requires --output")

    # lossless and lossy require --extension
    if args.function in EXTENSION_FUNCTIONS and not args.extension:
        parser.error(f"'{args.function}' requires --extension")

    # --store-skipped requires --store-path
    if args.store_skipped and not args.store_path:
        parser.error("'--store-skipped' requires --store-path")

    # missing_art requires --scan-mode
    if args.function == Namespace.FUNCTION_MISSING_ART:
        if not args.scan_mode:
            parser.error(f"'{args.function}' requires --scan-mode")

def ffmpeg_base(input_path: str, output_path: str, options: str) -> list[str]:
    '''Creates the base FFMPEG transcoding command with the options:
        -ar 44100: Set the audio sampling frequency to 44100 Hz
        -write_id3v2 1: Write ID3 V2 tags
    '''
    all_options = f"-ar 44100 -write_id3v2 1 {options}".strip()
    return ['ffmpeg', '-i', input_path] + shlex.split(all_options) + [output_path]

def ffmpeg_lossless(input_path: str, output_path: str) -> list[str]:
    # TODO: fix docstring formatting
    '''Creates an FFMPEG command that will transcode the `input_path` to the `output_path` with high quality lossless settings.
    Core command example:
        ffmpeg -i /path/to/input.foo -ar 44100 -c:a pcm_s16be -write_id3v2 1 -y path/to/output.bar
    Options:
        -c:a: decode audio stream
        pcm_s16be: 16-bit PCM big-endian
        -y: overwrite output file if present, without asking permission
    '''
    options = '-c:a pcm_s16be -y'

    return ffmpeg_base(input_path, output_path, options)

def ffmpeg_lossy(input_path: str, output_path: str, map_options: str='-map 0') -> list[str]:
    '''Creates an FFMPEG command that will transcode the `input_path` to the `output_path` with high quality lossy settings.
    Options:
      -b:a 320k: sets bitrate to 320K
      -y: overwrite output file if present, without asking permission'''
    options = f"-b:a 320k {map_options} -y"
    return ffmpeg_base(input_path, output_path, options)

def read_ffprobe_value(input_path: str, stream_key: str) -> str:
    '''Uses ffprobe command line tool. Reads the ffprobe value for a particular stream entry.

    Args:
    `args`        : The script's arguments.
    `input_path`  : Path to the file to probe.
    `stream_key`  : The stream label according to 'ffprobe' documentation.

    Returns:
    Stripped stdout of the ffprobe command or empty string.
    '''
    command = shlex.split(f"ffprobe -v error -show_entries stream={stream_key} -of default=noprint_wrappers=1:nokey=1")
    command.append(input_path)

    try:
        logging.debug(f"read_ffprobe_value command: {command}")
        value = subprocess.run(command, check=True, capture_output=True, encoding='utf-8').stdout.strip()
        logging.debug(f"read_ffprobe_value result: {value}")
        return value
    except subprocess.CalledProcessError as error:
        logging.error(f"fatal: read_ffprobe_value: CalledProcessError:\n{error.stderr}".strip())
        logging.debug(f"command: {shlex.join(command)}")
        sys.exit()

def command_ffprobe_json(path: str) -> list[str]:
    # ffprobe -v error -select_streams v -show_entries stream=index,codec_name,codec_type,width,height,:tags=comment -of json '/Users/user/Music/DJ/Bernard Badie - Train feat Dajae (Original .aiff'
    
    command_str = f"ffprobe -v error -select_streams v"
    command_str += f" -show_entries stream=index,width,height,:tags=comment -of json {shlex.quote(path)}"
    command = shlex.split(command_str)
    return command    

def read_ffprobe_json(path: str) -> list[dict[str, Any]]:
    '''Reads the ffprobe video streams of the given file.'''
    import json
    command = command_ffprobe_json(path)
    code, output = run_command(command)
    
    if code == 0:
        streams = json.loads(output)['streams']
        logging.debug(f"read streams for '{path}':\n{streams}")
        return streams
    return []

def guess_cover_stream_specifier(streams: list[dict[str, Any]]) -> int:
    '''Inspects the width and height of the video stream JSON to try to find a likely cover image.'''
    min_index, min_diff = -1, float('inf')
    for stream in streams:
        index = stream['index']
        width, height = stream['width'], stream['height']
        
        diff = abs(width - height)
        threshold = 3 # based on common placeholder image dimensions 250x1500
        
        if width / height >  threshold or height / width > threshold:
            logging.debug(f"found non-square video content at index {index}")
            continue
        if 'tags' in stream and 'comment' in stream['tags'] and 'logotype' in stream['tags']['comment'].lower():
            logging.debug(f"found non-cover video content at index {index}: '{stream['tags']['comment']}")
            continue
        if width == height and width == 849:
            return -2
        if diff < min_diff:
            min_diff = diff
            min_index = index
    return min_index

def check_skip_sample_rate(input_path: str) -> bool:
    '''Returns `True` if sample rate for `input_path` is at or below the standardized value.'''
    result = read_ffprobe_value(input_path, 'sample_rate')
    return False if len(result) < 1 else int(result) <= 44100

def check_skip_bit_depth(input_path: str) -> bool:
    '''Returns `True` if bit depth (aka 'sample format') is at or below the standardized value.'''
    result = read_ffprobe_value(input_path, 'sample_fmt').lstrip('s')
    return False if len(result) < 1 else int(result) <= 16

def setup_storage(dir_path: str, filename: str) -> str:
    '''Create or clear a storage file called `filename` at the path specified in `args`.

    Returns:
    The absolute path to the storage file.
    '''
    script_path_list = os.path.normpath(__file__).split(os.sep)
    storage_dir = os.path.normpath(f"{dir_path}/{script_path_list[-1].rstrip('.py')}/")
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)

    # create the file or clear any existing storage
    store_path = os.path.join(storage_dir, filename)
    with open(store_path, 'w', encoding='utf-8'):
        pass
    logging.debug(f"set up store path: {store_path}")

    return store_path

def run_command(command: list[str]) -> tuple[int, str]:
    '''Run the given command synchronously as a subprocess. Returns subprocess return code and stdout/stderr.'''
    try:
        logging.debug(f"run command: {shlex.join(command)}")
        result = subprocess.run(command, check=True, capture_output=True, encoding='utf-8')
        logging.debug(f"command success:\n{result.stdout.strip()}")
        return (result.returncode, result.stdout.strip())
    except subprocess.CalledProcessError as error:
        logging.error(f"return code '{error.returncode}':\n{error.stderr}".strip())
        return (error.returncode, error.stderr.strip())

async def run_command_async(command: list[str]) -> tuple[int, str]:
    '''Run the given command asynchronously as a subprocess. Returns subprocess return code and stdout/stderr.'''
    # create the async shell process
    logging.debug(f"run async command: {shlex.join(command)}")
    process = await asyncio.create_subprocess_shell(
        shlex.join(command),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    
    # wait for process to finish and handle result
    stdout, stderr = await process.communicate()
    if process.returncode is None:
        raise RuntimeError(f"process has return code 'None'.")
    if process.returncode == 0:
        message = f"command output:\n"
        output = ''
        if stdout:
            output = stdout.decode()
        elif stderr:
            output = stderr.decode()
        
        message += output
        logging.debug(message)
        return (process.returncode, output)
    else:
        stderr = stderr.decode()
        logging.error(f"return code '{process.returncode}':\n{stderr}")
        return (process.returncode, stderr)

# primary functions

# TODO: add support for FLAC
async def encode_lossless(input_dir: str,
                          output_dir: str,
                          extension: str = '',
                          store_path_dir: str | None = None,
                          store_skipped: bool = False,
                          dry_run: bool = False,
                          threads: int = 16,
                          encode_always: bool = False) -> list[FileMapping]:
    '''Primary script function. Recursively walks the input path specified in `input_dir` to re-encode each eligible file.
    Returns a list of the processed (input_file_path, output_file_path) tuples.
    A file is eligible if all conditions are met:
        1) It is an uncompressed `aiff` or `wav` type.
        2) It has a sample rate exceeding 44100 Hz or a bit depth exceeding 16 bits.

    All other files are skipped. If `args` is configured properly, the user can store each skipped path in a file.

    If `args` is configured properly, the script can also store each difference in file size before and after re-encoding.
    '''
    async def run_batch():
        nonlocal size_diff_sum

        run_tasks = [t[2] for t in tasks]
        await asyncio.gather(*run_tasks)
        for src_path, dest_path, _ in tasks:
            # compute (input - output) size difference after encoding
            size_diff = os.path.getsize(src_path)/10**6 - os.path.getsize(dest_path)/10**6
            size_diff_sum += size_diff
            size_diff = round(size_diff, 2)
            logging.info(f'file size diff: {size_diff} MB')

            if store_path_dir and store_path_size_diff:
                with open(store_path_size_diff, 'a', encoding='utf-8') as store_file:
                    store_file.write(f'{src_path}\t{dest_path}\t{size_diff}\n')
        logging.debug(f'ran {len(run_tasks)} tasks')
        tasks.clear()
        # separate entries
        logging.info('= = = =')
    
    # validate extension
    if extension:
        if not extension.startswith('.') or len(extension) != len(extension.strip()):
            error = ValueError(f"invalid extension {extension}")
            logging.error(error)
            raise error
    
    # core data
    processed_files: list[FileMapping] = []
    size_diff_sum = 0.0
    tasks: list[tuple[str, str, Task[tuple[int, str]]]] = []

    # set up storage (skip in dry-run mode)
    store_path_size_diff = None
    store_path_skipped = None
    skipped_files: list[str] | None = None
    if store_path_dir and not dry_run:
        store_path_size_diff = setup_storage(store_path_dir, 'size-diff.tsv')
        if store_skipped:
            store_path_skipped = setup_storage(store_path_dir, 'skipped.tsv')
            skipped_files = []

    # main processing loop
    extensions = {'.aif', '.aiff', '.wav'}
    for input_path in common.collect_paths(input_dir, filter=extensions):
        name = os.path.basename(input_path)
        filename, input_extension = os.path.splitext(name)
        output_extension = extension

        # skip files that meet encoding requirements
        if not encode_always:
            if not name.endswith('.wav') and\
            check_skip_sample_rate(input_path) and\
            check_skip_bit_depth(input_path):
                logging.debug(f"skip: optimal sample rate and bit depth: '{input_path}'")
                if skipped_files:
                    skipped_files.append(f"{input_path}\n")
                continue

        # use the existing input extension if an output extension is not provided
        if not extension and input_extension in extensions:
            output_extension = input_extension

        # build the output path with the resolved extension
        output_path = os.path.join(output_dir, f"{filename}{output_extension}")

        # add to processed files list
        processed_files.append((input_path, output_path))

        if dry_run:
            common.log_dry_run('encode', f'{input_path} -> {output_path}')
            continue

        # create the ffmpeg encode command and task
        command = ffmpeg_lossless(input_path, output_path)
        task = asyncio.create_task(run_command_async(command))
        tasks.append((input_path, output_path, task))

        # run task batch
        if len(tasks) == threads:
            await run_batch()
    
    # run final batch
    if tasks:
        await run_batch()

    if store_path_dir and store_path_size_diff:
        with open(store_path_size_diff, 'a', encoding='utf-8') as store_file:
            store_file.write(f"\n=> size diff sum: {round(size_diff_sum, 2)} MB")
            logging.info(f"wrote cumulative size difference to '{store_path_size_diff}'")
    if store_skipped and store_path_skipped and skipped_files:
        with open(store_path_skipped, 'a', encoding='utf-8') as store_file:
            store_file.writelines(skipped_files)
            logging.info(f"wrote skipped files to '{store_path_skipped}'")
    
    return processed_files

async def encode_lossy(path_mappings: list[FileMapping], extension: str, threads: int = 4, dry_run: bool = False) -> list[FileMapping]:
    '''Encodes the given input, output mappings in lossy format with the given extension. Uses FFMPEG as backend.
    Encoding operations are parallelized.

    Args:
        path_mappings: List of (source, dest) file path tuples
        extension: Target file extension (e.g., '.mp3')
        threads: Number of parallel encoding tasks
        dry_run: If True, skip encoding and return mappings without executing

    Returns:
        List of (source, dest) mappings showing what was or would be encoded
    '''
    from . import common

    tasks: list[Task[tuple[int, str]]] = []
    result_mappings: list[FileMapping] = []

    # loop through the input/output mappings
    for mapping in path_mappings:
        source, dest = mapping[0], mapping[1]
        dest = os.path.splitext(dest)[0] + extension

        # track the mapping for return value
        result_mappings.append((source, dest))

        if dry_run:
            common.log_dry_run('encode', f'{source} -> {dest}')
            continue

        # create the destination folders if needed
        dest_dir = os.path.dirname(dest)
        if not os.path.exists(dest_dir):
            logging.debug(f"create path: '{dest_dir}'")
            os.makedirs(dest_dir)

        # determine if the source file has a cover image
        ffprobe_data = read_ffprobe_json(source)
        cover_stream = guess_cover_stream_specifier(ffprobe_data)
        map_options = f'-map 0:0'
        if cover_stream > -1:
            logging.debug(f'guessed cover image in stream: {cover_stream}')
            map_options += f' -map 0:{cover_stream}'
        else:
            logging.info(f"no cover image found for '{source}'")

        # construct the command and add it to the task batch
        command = ffmpeg_lossy(source, dest, map_options=map_options)
        task = asyncio.create_task(run_command_async(command))
        tasks.append(task)
        logging.debug(f'add task: {len(tasks)}')

        # run the full task batch
        if len(tasks) == threads:
            run_tasks = tasks.copy()
            await asyncio.gather(*run_tasks)
            logging.debug(f'ran {len(run_tasks)} tasks')
            tasks.clear()

    # run any remaining tasks in the batch
    if tasks:
        run_tasks = tasks.copy()
        await asyncio.gather(*run_tasks)
        logging.debug(f'ran {len(tasks)} tasks')
        tasks.clear()

    if dry_run:
        logging.info(f'[DRY-RUN] Would encode {len(result_mappings)} files')
    else:
        logging.info('finished lossy encoding')

    return result_mappings

async def run_missing_art_tasks(tasks: list[tuple[str, Task[tuple[int, str]]]]) -> list[str]:
    '''Outputs a list of system file paths that are missing artwork.'''
    import json
    
    results: list[str] = []
    run_tasks = [task[1] for task in tasks]
    await asyncio.gather(*run_tasks)
    logging.debug(f"ran {len(run_tasks)} tasks")
    
    for i, task in enumerate(run_tasks):
        source = tasks[i][0]
        code, output = task.result()
        if code == 0:
            output = json.loads(output)['streams']
            cover_stream = guess_cover_stream_specifier(output)
            if cover_stream > -1:
                logging.debug(f"guessed cover image in stream: {cover_stream}")
            elif cover_stream == -2:
                logging.info(f"found potential placeholder cover for '{source}'")
            else:
                logging.info(f"no cover image found for '{source}'")
                results.append(source)
        else:
            logging.error(f"unable to determine missing art for '{source}':\n{output}")
    return results

async def find_missing_art_os(input_dir: str, threads: int=24) -> list[str]:
    # output data and command tasks
    missing: list[str] = []
    tasks: list[tuple[str, Task[tuple[int, str]]]] = []
    
    # iterate over the source dir paths
    for path in common.collect_paths(input_dir):
        # collect task batch
        task = asyncio.create_task(run_command_async(command_ffprobe_json(path)))
        tasks.append((path, task))
        logging.debug(f"add task: {len(tasks)}")
        
        # run task batch
        if len(tasks) == threads:
            missing += await run_missing_art_tasks(tasks)
            tasks.clear()
    
    # run remaining tasks
    missing += await run_missing_art_tasks(tasks)
    return missing

async def find_missing_art_xml(collection_file_path: str, collection_xpath: str, playlist_xpath: str, threads: int=24) -> list[str]:
    from . import library
    
    tree = library.load_collection(collection_file_path)
    collection = library.find_node(tree, collection_xpath)
    playlist = library.find_node(tree, playlist_xpath)
    missing: list[str] = []
    
    # collect the playlist IDs
    tasks: list[tuple[str, Task[tuple[int, str]]]] = []
    playlist_ids: set[str] = { track.attrib[constants.ATTR_TRACK_KEY] for track in playlist }
    
    for node in collection:
        # check if node is in playlist
        source = library.collection_path_to_syspath(node.attrib[constants.ATTR_LOCATION])
        if playlist_ids and node.attrib[constants.ATTR_TRACK_ID] not in playlist_ids:
            logging.info(f"skip non-playlist track: '{source}'")
            continue
        
        task = asyncio.create_task(run_command_async(command_ffprobe_json(source)))
        tasks.append((source, task))
        logging.debug(f"add task: {len(tasks)}")
        if len(tasks) == threads:
            missing += await run_missing_art_tasks(tasks)
            tasks.clear()
    
    # run remaining tasks
    missing += await run_missing_art_tasks(tasks)
    return missing

# Main
def main(argv: list[str]) -> None:
    common.configure_log_module(__file__, level=logging.DEBUG)
    script_args = parse_args(Namespace.FUNCTIONS, argv[1:])

    if script_args.function == Namespace.FUNCTION_LOSSLESS:
        result = asyncio.run(encode_lossless(script_args.input,
                                             script_args.output,
                                             extension=script_args.extension,
                                             store_path_dir=script_args.store_path,
                                             store_skipped=script_args.store_skipped,
                                             dry_run=script_args.dry_run))
        if script_args.dry_run:
            print(f'\n[DRY-RUN] Would encode {len(result)} files:')
            for source, dest in result:
                print(f'  {source} -> {dest}')
        else:
            print(f'\nEncoded {len(result)} files')
    elif script_args.function == Namespace.FUNCTION_LOSSY:
        path_mappings = common.collect_paths(script_args.input)
        path_mappings = common.add_output_path(script_args.output, path_mappings, script_args.input)
        result = asyncio.run(encode_lossy(path_mappings, script_args.extension, dry_run=script_args.dry_run))
        if script_args.dry_run:
            print(f'\n[DRY-RUN] Would encode {len(result)} files:')
            for source, dest in result:
                print(f'  {source} -> {dest}')
        else:
            print(f'\nEncoded {len(result)} files')
    elif script_args.function == Namespace.FUNCTION_MISSING_ART:
        if script_args.scan_mode == Namespace.SCAN_MODE_XML:
            coroutine = find_missing_art_xml(script_args.input, constants.XPATH_COLLECTION, constants.XPATH_PRUNED, threads=72)
        else:
            coroutine = find_missing_art_os(script_args.input, threads=72)
        missing = asyncio.run(coroutine)
        common.write_paths(missing, script_args.output)

if __name__ == '__main__':
    main(sys.argv)
