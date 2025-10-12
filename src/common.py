import logging
import os

from . import constants

# Constants
# TODO: use project path as root for logs, they shouldn't be in src/
DEFAULT_PATH = os.path.abspath(__file__)

def configure_log(level: int=logging.DEBUG, path: str=DEFAULT_PATH) -> None:
    '''Standard log configuration.'''
    if path == DEFAULT_PATH:
        logs_path = os.path.join(os.path.dirname(DEFAULT_PATH), 'logs')
    else:
        logs_path = os.path.join(os.path.dirname(os.path.abspath(path)), 'logs')
    if not os.path.exists(logs_path):
        os.makedirs(logs_path)

    # Determine filename
    filename = os.path.abspath(path)
    split = os.path.basename(filename)
    split = os.path.splitext(split)
    if len(split) > 1:
        filename = split[0]
    
    logging.basicConfig(filename=f"{logs_path}/{filename}.log",
                        level=level,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%D %H:%M:%S",
                        filemode='w')

# TODO: refactor calling functions to use filter
def collect_paths(root: str, filter: set[str] = set()) -> list[str]:
    '''Returns the paths of all files for the given root.
    If `filter` is provided, only files with a matching extension will be returned.'''
    paths: list[str] = []
    for working_dir, _, names in os.walk(root):
        for name in names:
            # construct the absolute file path
            full_path = os.path.join(working_dir, name)
            
            # skip hidden directories
            directory = os.path.split(os.path.dirname(full_path))[-1]
            if directory.startswith('.'):
                continue
            
            # skip hidden files or files that don't match the extension filter
            _, extension = os.path.splitext(name)
            if name.startswith('.') or (filter and extension and extension not in filter):
                continue
            paths.append(full_path)
    return paths

def add_output_path(output_path: str, input_paths: list[str], root_input_path: str) -> list[tuple[str, str]]:
    '''Adds the given path + filename as the output path for each input path.
    Maintains the path structure relative to the root input path.'''
    paths: list[tuple[str, str]] = []
    for input_path in input_paths:
        full_output_path = os.path.join(output_path, os.path.relpath(input_path, root_input_path))
        paths.append((input_path, full_output_path))
        
    return paths

def raise_exception(error: Exception):
    logging.exception(error)
    raise error

def find_date_context(path: str) -> tuple[str, int] | None:
    '''Extracts the date subpath and start path component index from the input path.
    Example path: '/data/tracks-output/2022/04 april/24/1-Gloria_Jones_-_Tainted_Love_(single_version).mp3'
    Example output: '2022/04 april/24', 3
    '''
    # Edge case: '/Users/user/developer/test-private/data/tracks-output/2024/08 august/18/Paolo Mojo/1983/159678_1983_(Eric_Prydz_Remix).aiff'
    components = path.split(os.sep)
    found: dict[str, int] = {}
    context: list[str] = []
    
    for i, component in enumerate(components):
        if 'y' not in found and len(component) == 4 and component.isdecimal():
            found['y'] = i
            context.append(component)
        if 'y' in found and found['y'] == i - 1:
            month_label = component.split()
            month_num = month_label[0]
            if len(month_num) == 2 and month_num.isdecimal()\
                and int(month_num) in constants.MAPPING_MONTH and constants.MAPPING_MONTH[int(month_num)] == month_label[1]:
                    found['m'] = i
                    context.append(component)
        if 'm' in found and found['m'] == i - 1:
            if len(component) == 2 and component.isdecimal():
                found['d'] = i
                context.append(component)
    # check for valid date context
    if len(context) != 3:
        return None
    
    return (os.sep.join(context), found['y'])

def remove_subpath(path: str, preserve_root: str, preserve_index: int) -> str:
    '''Given a path, removes the intermediary path components after the root and before the preserve index.'''
    transformed = path.split(os.sep)
    removals = [i for i in range(preserve_index)]
    for _ in removals:
        del transformed[0]
    return os.path.join(preserve_root, os.sep.join(transformed))

def remove_substring(source: str, start_inclusive: int, end_exclusive: int) -> str:
    assert start_inclusive < end_exclusive, f"invalid start, end: '{start_inclusive}', '{end_exclusive}'"
    return f"{source[:start_inclusive]}{source[end_exclusive:]}"

def get_encoding(path: str) -> str:
    '''Uses chardet to guess the file encoding of the given path.'''
    import chardet
    
    # Read, detect and decode the input file data
    raw_bytes = b''
    with open(path, 'rb') as file:
        raw_bytes = file.read()
    
    # Attempt extract the detected encoding
    result = chardet.detect(raw_bytes)
    if result and result['encoding']:
        return result['encoding']
    else:
        return ''

def write_paths(paths: list[str], output_path: str) -> None:
    '''Sorts and writes the given list of full file paths to the specified output file.'''
    sorted_paths = sorted([f"{p}\n" for p in paths])
    with open(output_path, 'w', encoding='utf-8') as file:
        file.writelines(sorted_paths)
