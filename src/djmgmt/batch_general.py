'''
This script performs bulk operations on a list of files contained in the input file.
'''

import os
import sys
import shutil
import argparse
from typing import Callable

# classes
class Namespace(argparse.Namespace):
    '''Command-line arguments for batch_general module.'''

    # Required
    function: str

    # Optional (alphabetical)
    column: int
    input: str
    interactive: bool
    output: str

    # Function constants
    FUNCTION_MOVE = 'move'
    SCRIPT_FUNCTIONS = {'move'}

# helper functions
def parse_args(functions: set[str], argv: list[str]) -> Namespace:
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
    parser.add_argument('--column', '-c', type=int, default=0,
                       help="Column to process in TSV input file. Default: 0")
    parser.add_argument('--input', '-i', type=str,
                       help='Input TSV file containing list of paths')
    parser.add_argument('--interactive', action='store_true',
                       help='Run script in interactive mode')
    parser.add_argument('--output', '-o', type=str,
                       help='Output directory for files')

    # Parse into Namespace
    args = parser.parse_args(argv, namespace=Namespace())

    # Validate function
    if args.function not in functions:
        parser.error(f"invalid function '{args.function}'\n"
                    f"expect one of: {', '.join(sorted(functions))}")

    # Function-specific validation
    _validate_function_args(parser, args)

    # Normalize paths (only if not None)
    from . import common
    common.normalize_arg_paths(args, ['input', 'output'])

    return args


def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''

    # All functions require --input and --output
    if not args.input:
        parser.error(f"'{args.function}' requires --input")
    if not args.output:
        parser.error(f"'{args.function}' requires --output")

    # Validate input file type
    if os.path.splitext(args.input)[1] != '.tsv':
        parser.error(f"--input must be a .tsv file, got: {args.input}")

def batch_file_operation(args: Namespace) -> None:
    '''Performs the given operation on each file contained in the input file.

    Function parameters:
        args -- The command-line arguments.
    '''
    with open(args.input, 'r', encoding='utf-8') as input_file:
        lines : list[str] = input_file.readlines()
        action: Callable[[str, str], str] = shutil.move

        if args.function != 'mv':
            print(f"error: unsupported operation: {args.function}")
            return

        if not os.path.exists(os.path.normpath(args.output)):
            os.makedirs(os.path.normpath(args.output))

        # Main loop.
        for line in lines:
            if '\t'not in line:
                print(f"info: skip: no tab on line '{line}' for TSV file '{args.input}'")
                continue

            input_path = os.path.normpath(line.split('\t')[args.column])
            if not os.path.exists(input_path):
                print(f"info: skip: input path '{input_path} does not exist.'")
                continue

            new_path = os.path.normpath(f"{args.output}/{os.path.basename(input_path)}")
            if os.path.exists(new_path):
                print(f"info: skip: path '{new_path}' exists")
                continue

            if args.interactive:
                choice = input(f"input: {args.function} '{input_path}' to '{args.output}' continue? [y/N]")
                if choice != 'y':
                    print("info: exit: user quit")
    
                    break

            action(input_path, args.output)

# Main
def main(argv: list[str]) -> None:
    script_args = parse_args(Namespace.SCRIPT_FUNCTIONS, argv[1:])

    if script_args.function == Namespace.FUNCTION_MOVE:
        batch_file_operation(script_args)

if __name__ == '__main__':
    main(sys.argv)
