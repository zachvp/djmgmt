'''
This script performs bulk operations on a list of files contained in the input file.
'''

import os
import shutil
import argparse
from typing import Callable

# classes
class Namespace(argparse.Namespace):
    # Arguments
    ## Required
    function: str
    input_path: str
    output_path: str
    
    ## Optional
    column: int
    interactive: bool
    
    # Functions
    FUNCTION_MOVE = 'move'
    SCRIPT_FUNCTIONS = {'move'}

# helper functions
def parse_args(functions: set[str]) -> type[Namespace]:
    '''Returns the parsed command-line arguments.

    Function parameters:
        functions -- The valid functions that this script can run.
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('function', type=str,
        help=f"The type of function to perform. One of: {functions}")
    parser.add_argument('input_path', type=str,
        help='The input path to the file containing the list of paths. Expects TSV format.')
    parser.add_argument('output_path', type=str, help='The output path that all files will be written to.')
    parser.add_argument('--column', '-c', type=int, help="The column to process in the input file. Defaults to '0'")
    parser.add_argument('--interactive', '-i', action='store_true',
        help="Run the script in interactive mode. Defaults to 'False'")

    args = parser.parse_args(namespace=Namespace)

    # validate arguments
    if args.function not in functions:
        parser.error(f"Invalid parameter '{args.function}' for positional argument 'function'. Expect one of: {functions}.")

    # normalize arguments
    args.input_path = os.path.normpath(args.input_path)
    args.output_path = os.path.normpath(args.output_path)
    if not args.column:
        args.column = 0

    # check filetype
    if os.path.splitext(args.input_path)[1] != '.tsv':
        parser.error(f"Invalid parameter {args.input_path} for positional argument 'input_path'. Expect '*.tsv' file.")

    return args

def batch_file_operation(args: type[Namespace]) -> None:
    '''Performs the given operation on each file contained in the input file.

    Function parameters:
        args -- The command-line arguments.
    '''
    with open(args.input_path, 'r', encoding='utf-8') as input_file:
        lines : list[str] = input_file.readlines()
        action: Callable[[str, str], str] = shutil.move

        if args.function != 'mv':
            print(f"error: unsupported operation: {args.function}")
            return

        if not os.path.exists(os.path.normpath(args.output_path)):
            os.makedirs(os.path.normpath(args.output_path))

        # Main loop.
        for line in lines:
            if '\t'not in line:
                print(f"info: skip: no tab on line '{line}' for TSV file '{args.input_path}'")
                continue

            input_path = os.path.normpath(line.split('\t')[args.column])
            if not os.path.exists(input_path):
                print(f"info: skip: input path '{input_path} does not exist.'")
                continue

            new_path = os.path.normpath(f"{args.output_path}/{os.path.basename(input_path)}")
            if os.path.exists(new_path):
                print(f"info: skip: path '{new_path}' exists")
                continue

            if args.interactive:
                choice = input(f"input: {args.function} '{input_path}' to '{args.output_path}' continue? [y/N]")
                if choice != 'y':
                    print("info: exit: user quit")
    
                    break

            action(input_path, args.output_path)

# Main
if __name__ == '__main__':
    script_args = parse_args(Namespace.SCRIPT_FUNCTIONS)

    if script_args.function == Namespace.FUNCTION_MOVE:
        batch_file_operation(script_args)
