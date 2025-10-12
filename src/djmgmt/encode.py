'''
encode tracks scripts
'''

import subprocess
import argparse
import os
import sys
import shlex
import logging
import sys
import asyncio
from asyncio import Task
from typing import Any

from . import common
from . import constants

# classes
class Namespace(argparse.Namespace):
    # arguments
    ## required
    function: str
    input: str
    output: str

    ## optional    
    extension: str
    store_path: str
    store_skipped: bool
    interactive: bool
    scan_mode: str
    # threads: int TODO: add and integrate
    
    # functions
    FUNCTION_LOSSLESS    = 'lossless'
    FUNCTION_LOSSY       = 'lossy'
    FUNCTION_MISSING_ART = 'missing_art'
    
    FUNCTIONS = {FUNCTION_LOSSLESS, FUNCTION_LOSSY, FUNCTION_MISSING_ART}
    
    # options
    SCAN_MODE_XML = 'xml'
    SCAN_MODE_OS  = 'os'
    
    SCAN_MODES = {SCAN_MODE_XML, SCAN_MODE_OS}

# helper functions
def parse_args(functions: set[str]) -> type[Namespace]:
    '''Process the script's command line aruments.'''
    EXTENSION_FUNCTIONS = {Namespace.FUNCTION_LOSSLESS, Namespace.FUNCTION_LOSSY}
    
    # configure args
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str, help=f"the function to run; one of: '{functions}'")
    parser.add_argument('input', type=str, help='the input path')
    parser.add_argument('output', type=str, help='the output path')
    
    parser.add_argument('--extension', '-e', type=str, help=f"the output extension for each file; required for '{EXTENSION_FUNCTIONS}'")
    parser.add_argument('--store-path', type=str, help='the script storage path to write to')
    parser.add_argument('--store-skipped', action='store_true', help='store the skipped files in store path')
    parser.add_argument('--interactive', '-i', action='store_true', help='run the script in interactive mode')
    parser.add_argument('--scan-mode', type=str, help=f"the missing art scan mode; one of: '{Namespace.SCAN_MODES}' (case-insensitive)")

    # parse args
    args = parser.parse_args(namespace=Namespace)
    
    # validate function
    if args.function not in functions:
        parser.error(f"invalid function '{args.function}', expect one of: '{functions}'")

    # validate storage path args
    if args.store_skipped and not args.store_path:
        parser.error("if option '--store-skipped' is set, option '--store-path' is required")
    
    # validate extension argument
    if args.extension and args.function not in EXTENSION_FUNCTIONS:
        parser.error(f"function '{args.function}' requires '--extension' argument")
        
    # validate scan mode argument
    if args.scan_mode:
        args.scan_mode = args.scan_mode.lower()
        if args.scan_mode not in Namespace.SCAN_MODES:
            parser.error(f"invalid scan mode: '{args.scan_mode}'")
    elif args.function == Namespace.FUNCTION_MISSING_ART:
        parser.error(f"funtion '{args.function}' requires '--scan-mode' option")

    return args

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
def encode_lossless_cli(args: type[Namespace]) -> list[tuple[str, str]]:
    return asyncio.run(encode_lossless(args.input,
                                       args.output,
                                       extension=args.extension,
                                       store_path_dir=args.store_path,
                                       store_skipped=args.store_skipped,
                                       interactive=args.interactive))

# TODO: add support for FLAC
async def encode_lossless(input_dir: str,
                          output_dir: str,
                          extension: str = '',
                          store_path_dir: str | None = None,
                          store_skipped: bool = False,
                          interactive: bool = False,
                          threads: int = 16,
                          encode_always: bool = False) -> list[tuple[str, str]]:
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
            processed_files.append((src_path, dest_path))
            
            # compute (input - output) size difference after encoding
            size_diff = os.path.getsize(src_path)/10**6 - os.path.getsize(dest_path)/10**6
            size_diff_sum += size_diff
            size_diff = round(size_diff, 2)
            logging.info(f"file size diff: {size_diff} MB")
            
            if store_path_dir and store_path_size_diff:
                with open(store_path_size_diff, 'a', encoding='utf-8') as store_file:
                    store_file.write(f"{src_path}\t{dest_path}\t{size_diff}\n")
        logging.debug(f"ran {len(run_tasks)} tasks")
        tasks.clear()
        # separate entries
        logging.info("= = = =")
    
    # validate extension
    if extension:
        if not extension.startswith('.') or len(extension) != len(extension.strip()):
            error = ValueError(f"invalid extension {extension}")
            logging.error(error)
            raise error
    
    # core data
    processed_files: list[tuple[str, str]] = []
    size_diff_sum = 0.0
    tasks: list[tuple[str, str, Task[tuple[int, str]]]] = []

    # set up storage
    store_path_size_diff = None
    store_path_skipped = None
    skipped_files: list[str] | None = None
    if store_path_dir:
        store_path_size_diff = setup_storage(store_path_dir, 'size-diff.tsv')
        if store_skipped:
            store_path_skipped = setup_storage(store_path_dir, 'skipped.tsv')
            skipped_files = []

        # interactive: confirm storage with user
        if interactive:
            choice = input("storage set up, does everything look okay? [y/N]")
            if choice != 'y':
                logging.info("user quit")
                return processed_files

    # main processing loop
    # for working_dir, dirnames, filenames in os.walk(input_dir):
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

        # interactive: confirm encoding action with user
        if interactive:
            choice = input(f"re-encode '{input_path}'? [y/N]")
            if choice != 'y':
                logging.info('exit, user quit')
                break

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

def encode_lossy_cli(args: type[Namespace]) -> None:
    '''Parse each path mapping entry into an encoding operation.'''
    path_mappings = common.collect_paths(args.input)
    path_mappings = common.add_output_path(args.output, path_mappings, args.input)
    asyncio.run(encode_lossy(path_mappings, args.extension))

async def encode_lossy(path_mappings: list[tuple[str, str]], extension: str, threads: int = 4) -> None:
    '''Encodes the given input, output mappings in lossy format with the given extension. Uses FFMPEG as backend.
    Encoding operations are parallelized.'''
    tasks: list[Task[tuple[int, str]]] = []
    
    # loop through the input/output mappings
    for mapping in path_mappings:
        source, dest = mapping[0], mapping[1]
        dest = os.path.splitext(dest)[0] + extension
        
        # create the destination folders if needed
        dest_dir = os.path.dirname(dest)
        if not os.path.exists(dest_dir):
            logging.debug(f"create path: '{dest_dir}'")
            os.makedirs(dest_dir)
        
        # determine if the source file has a cover image
        ffprobe_data = read_ffprobe_json(source)
        cover_stream = guess_cover_stream_specifier(ffprobe_data)
        map_options = f"-map 0:0"
        if cover_stream > -1:
            logging.debug(f"guessed cover image in stream: {cover_stream}")
            map_options += f" -map 0:{cover_stream}"
        else:
            logging.info(f"no cover image found for '{source}'")
        
        # construct the command and add it to the task batch
        command = ffmpeg_lossy(source, dest, map_options=map_options)
        task = asyncio.create_task(run_command_async(command))
        tasks.append(task)
        logging.debug(f"add task: {len(tasks)}")
        
        # run the full task batch
        if len(tasks) == threads:
            run_tasks = tasks.copy()
            await asyncio.gather(*run_tasks)
            logging.debug(f"ran {len(run_tasks)} tasks")
            tasks.clear()
    
    # run any remaining tasks in the batch
    if tasks:
        run_tasks = tasks.copy()
        await asyncio.gather(*run_tasks)
        logging.debug(f"ran {len(tasks)} tasks")
        tasks.clear()
    logging.info('finished lossy encoding')

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
        source = library.collection_path_to_syspath(node.attrib[constants.ATTR_PATH])
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

def missing_art_cli(args: type[Namespace]) -> None:
    # TODO: add timing
    # TODO: refactor into wrapper + internal functions
    coroutine = None
    missing = []
    if args.scan_mode == Namespace.SCAN_MODE_XML:        
        coroutine = find_missing_art_xml(args.input, constants.XPATH_COLLECTION, constants.XPATH_PRUNED, threads=72)
    else:
        coroutine = find_missing_art_os(args.input, threads=72)
    
    # run the configured function and write the result to the given file
    missing = asyncio.run(coroutine)
    common.write_paths(missing, args.output)

# Main
if __name__ == '__main__':
    common.configure_log(level=logging.DEBUG, path=__file__)
    script_args = parse_args(Namespace.FUNCTIONS)
    
    if script_args.function == Namespace.FUNCTION_LOSSLESS:
        encode_lossless_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_LOSSY:
        encode_lossy_cli(script_args)
    elif script_args.function == Namespace.FUNCTION_MISSING_ART:
        missing_art_cli(script_args)
