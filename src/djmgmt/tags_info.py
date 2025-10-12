'''
Uses a combination of audio file metadata to determine duplicates
'''

import os
import argparse
import logging
from typing import Callable

from .tags import Tags
from . import common

# command support
class Namespace(argparse.Namespace):
    # required
    function: str
    input: str
    
    # optional
    output: str
    comparison: str
    
    # constants
    FUNCTION_LOG_DUPLICATES = 'log_duplicates'
    FUNCTION_WRITE_IDENTIFIERS = 'write_identifiers'
    FUNCTION_WRITE_PATHS = 'write_paths'
    FUNCTION_COMPARE = 'compare'
    FUNCTIONS = {FUNCTION_LOG_DUPLICATES, FUNCTION_WRITE_IDENTIFIERS, FUNCTION_WRITE_PATHS, FUNCTION_COMPARE}

def parse_args(functions: set[str]) -> type[Namespace]:
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str, help=f"The function to run. One of '{functions}'")
    parser.add_argument('input', type=str, help='The input/source path root.')
    parser.add_argument('--output', '-o', type=str, help='The output file to write to.')
    parser.add_argument('--comparison', '-c', type=str, help='The comparison directory (required for compare).')
    
    args = parser.parse_args(namespace=Namespace)
    args.input = os.path.normpath(args.input)
    if args.output:
        args.output = os.path.normpath(args.output)
    if args.comparison:
        args.comparison = os.path.normpath(args.comparison)
    
    if args.function not in functions:
        parser.error(f"invalid function '{args.function}'; expect one of '{functions}'")
    if args.function == Namespace.FUNCTION_COMPARE and not args.comparison:
        parser.error(f"missing required --comparison argument for '{Namespace.FUNCTION_COMPARE}'")
    
    return args

# primary functions
def log_duplicates(root: str) -> None:
    # script state
    file_set: set[str] = set()

    # script process
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
            logging.info(path)

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

def compare_tags(source: str, comparison: str) -> list[tuple[str, str]]:
    '''Compares tag metadata between files in source and comparison directories.
    Returns a list of (source, comparison) path mappings where tags have changed for matching filenames.'''
    # output data
    changed_paths: list[tuple[str, str]] = []
    
    # use to compare files based on filename, excluding extension
    normalize_filename: Callable[[str], str] = lambda path: os.path.splitext(os.path.basename(path))[0]
    
    # collect paths and build a mapping for comparison files by normalized filename
    source_paths = common.collect_paths(source)
    comparison_files = {}
    for compare_path in common.collect_paths(comparison):
        base_name = normalize_filename(compare_path)
        comparison_files[base_name] = compare_path
    
    # compare the source paths present in the comparison directory
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
            
            # compare relevant tags (title, artist, cover image, genre, etc) add to list if any differ
            if source_tags != compare_tags:
                changed_paths.append((os.path.abspath(source_path), os.path.abspath(compare_path)))
                logging.info(f"Detected tag difference in '{source_path}'")
                
    return changed_paths

# main
if __name__ == '__main__':
    from . import common
    
    common.configure_log(level=logging.DEBUG, path=__file__)
    args = parse_args(Namespace.FUNCTIONS)
    
    logging.info(f"running function '{args.function}'")
    if args.function == Namespace.FUNCTION_LOG_DUPLICATES:
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