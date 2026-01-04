'''
Uses a combination of audio file metadata to determine duplicates
'''

import os
import argparse
import logging
from typing import Callable, Iterator

from .tags import Tags, Diff
from . import common

# command support
class Namespace(argparse.Namespace):
    '''Command-line arguments for tags_info module.'''

    # Required
    function: str

    # Optional (alphabetical)
    comparison: str
    input: str
    output: str

    # Function constants
    FUNCTION_LOG_DUPLICATES = 'log_duplicates'
    FUNCTION_WRITE_IDENTIFIERS = 'write_identifiers'
    FUNCTION_WRITE_PATHS = 'write_paths'
    FUNCTION_COMPARE = 'compare'
    FUNCTIONS = {FUNCTION_LOG_DUPLICATES, FUNCTION_WRITE_IDENTIFIERS, FUNCTION_WRITE_PATHS, FUNCTION_COMPARE}

def parse_args(functions: set[str], argv: list[str] | None = None) -> Namespace:
    '''Parse command line arguments.

    Args:
        functions: Set of valid function names
        argv: Optional argument list for testing (defaults to sys.argv)
    '''
    parser = argparse.ArgumentParser()

    # Required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(functions))}")

    # Optional: all function parameters (alphabetical)
    parser.add_argument('--comparison', '-c', type=str,
                       help='Comparison directory for tag comparison')
    parser.add_argument('--input', '-i', type=str,
                       help='Input directory or file path')
    parser.add_argument('--output', '-o', type=str,
                       help='Output file to write results to')

    # Parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # Normalize paths (only if not None)
    common.normalize_arg_paths(args, ['comparison', 'input', 'output'])

    # Validate function
    if args.function not in functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(functions))}")

    # Function-specific validation
    _validate_function_args(parser, args)

    return args


def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''

    # All functions require --input
    if not args.input:
        parser.error(f"'{args.function}' requires --input")

    # Functions that require --output
    if args.function in {Namespace.FUNCTION_WRITE_IDENTIFIERS,
                         Namespace.FUNCTION_WRITE_PATHS,
                         Namespace.FUNCTION_COMPARE}:
        if not args.output:
            parser.error(f"'{args.function}' requires --output")

    # compare function requires --comparison
    if args.function == Namespace.FUNCTION_COMPARE:
        if not args.comparison:
            parser.error(f"'{args.function}' requires --comparison")

# primary functions
# TODO: update tests to check return value
# TODO: rename to 'find_duplicates'
def log_duplicates(root: str) -> list[str]:
    '''Searches recursively to find all duplicate audio files in the input path, according to artist and title.'''
    # state: track existing IDs and duplicate files
    file_set: set[str] = set()
    duplicate_paths: list[str] = []

    # process: explore all paths
    paths = common.collect_paths(root)
    for path in paths:
        # load track tags, check for errors
        tags = Tags.load(path)
        if not tags:
            continue

        # set item = concatenation of track title & artist
        item = f"{tags.artist}{tags.title}".lower()

        # check for duplicates based on set contents
        # before and after insertion
        count = len(file_set)

        file_set.add(item)
        if len(file_set) == count:
            duplicate_paths.append(path)
            logging.info(path)
    return duplicate_paths

def collect_identifiers(root: str) -> list[str]:
    tracks: list[str] = []

    paths = common.collect_paths(root)
    for path in paths:
        # load track tags, check for errors
        tags = Tags.load(path)
        if not tags or not tags.artist or not tags.title:
            logging.error(f"incomplete tags: {tags}")
            continue

        # set item = concatenation of track title & artist
        tracks.append(tags.basic_identifier())
    return tracks

def collect_filenames(root: str) -> list[str]:
    names: list[str] = []

    paths = common.collect_paths(root)
    for path in paths:
        name = os.path.basename(path)
        name = os.path.splitext(name)[0]
        names.append(name)
    return names

def _generate_tag_pairs(source: str, comparison: str) -> Iterator[tuple[str, str, Tags, Tags]]:
    '''Generator that yields matching tag pairs from source and comparison directories.

    Yields:
        Tuples of (source_path, compare_path, source_tags, compare_tags) for files
        with matching names (excluding extension)
    '''
    # use to compare files based on filename, excluding extension
    normalize_filename: Callable[[str], str] = lambda path: os.path.splitext(os.path.basename(path))[0]

    # collect paths and build a mapping for comparison files by normalized filename
    source_paths = common.collect_paths(source)
    comparison_files = {}
    for compare_path in common.collect_paths(comparison):
        base_name = normalize_filename(compare_path)
        comparison_files[base_name] = compare_path

    # yield matching source/comparison tag pairs
    for source_path in source_paths:
        base_name = normalize_filename(source_path)
        if base_name in comparison_files:
            compare_path = comparison_files[base_name]

            # read tags from both files
            source_tags = Tags.load(source_path)
            compare_tags = Tags.load(compare_path)

            # skip if tags can't be read from either file
            if not source_tags or not compare_tags:
                logging.error(f"Unable to read tags from '{source_path}' or '{compare_path}'")
                continue

            yield (source_path, compare_path, source_tags, compare_tags)

# TODO: enhance to report progress to caller
def compare_tags(source: str, comparison: str) -> list[tuple[str, str]]:
    '''Compares tag metadata between files in source and comparison directories.
    Returns a list of (source, comparison) path mappings where tags have changed for matching filenames.'''
    changed_paths: list[tuple[str, str]] = []

    for source_path, compare_path, source_tags, compare_tags in _generate_tag_pairs(source, comparison):
        # compare using Tags.__eq__
        if source_tags != compare_tags:
            changed_paths.append((os.path.abspath(source_path), os.path.abspath(compare_path)))
            logging.info(f"Detected tag difference in '{source_path}'")

    return changed_paths

def compare_tags_with_diff(source: str, comparison: str) -> list[tuple[str, str, Diff]]:
    '''Compares tag metadata between files in source and comparison directories.
    Returns a list of (source, comparison, diff) tuples where tags have changed for matching filenames.'''
    changed_paths: list[tuple[str, str, Diff]] = []

    for source_path, compare_path, source_tags, compare_tags in _generate_tag_pairs(source, comparison):
        # compare using Tags.diff() for detailed difference information
        diff = source_tags.diff(compare_tags)
        if diff.has_differences():
            changed_paths.append((os.path.abspath(source_path), os.path.abspath(compare_path), diff))
            logging.info(f"Detected tag difference in '{source_path}'")

    return changed_paths

# main
if __name__ == '__main__':
    from . import common
    
    common.configure_log(level=logging.DEBUG, path=__file__)
    args = parse_args(Namespace.FUNCTIONS)
    
    logging.info(f"running function '{args.function}'")
    if args.function == Namespace.FUNCTION_LOG_DUPLICATES:
        # TODO: write duplicates to file
        log_duplicates(args.input)
    elif args.function == Namespace.FUNCTION_WRITE_IDENTIFIERS:
        identifiers = sorted(collect_identifiers(args.input))
        lines = [f"{id}\n" for id in identifiers]
        with open(args.output, 'w', encoding='utf-8') as file:
            file.writelines(lines)
    elif args.function == Namespace.FUNCTION_WRITE_PATHS:
        paths = collect_filenames(args.input)
        lines = [f"{p}\n" for p in paths]
        lines.sort()
        with open(args.output, 'w', encoding='utf-8') as file:
            file.writelines(lines)
    elif args.function == Namespace.FUNCTION_COMPARE:
        changed = compare_tags(args.input, args.comparison)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as file:
                for paths in changed:
                    file.write(f"{paths}\n")
        else:
            for paths in changed:
                print(paths)
