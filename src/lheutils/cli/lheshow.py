#!/usr/bin/env python3
"""
CLI tool to display specific events or init block from LHE files.

This tool allows you to view individual events or the initialization block
from Les Houches Event (LHE) files.
"""

import argparse
import sys
import warnings
from pathlib import Path
from typing import TextIO, Union

import pylhe

from lheutils.cli.util import create_base_parser


def show_event(
    filepath_or_fileobj: Union[str, TextIO],
    event_number: int,
    file_inputs_count: int = 1,
) -> None:
    """Show a specific event from an LHE file.

    Args:
        filepath_or_fileobj: Path to the LHE file or file object
        event_number: Event number to display (1-indexed)
        file_inputs_count: Number of total files being processed
    """
    try:
        if isinstance(filepath_or_fileobj, str):
            file_display_name = filepath_or_fileobj
            lhefile = pylhe.LHEFile.fromfile(filepath_or_fileobj)
        else:
            file_display_name = "<stdin>"
            lhefile = pylhe.LHEFile.frombuffer(filepath_or_fileobj)

        target_index = event_number

        if target_index < 0:
            print(
                f"Error: Event number must be positive (got {event_number})",
                file=sys.stderr,
            )
            sys.exit(1)

        # Iterate through events to find the target
        i = 0
        for i, event in enumerate(lhefile.events, start=1):
            if i == target_index:
                if file_inputs_count > 1:
                    print(f"=== {file_display_name} ===")
                print(event.tolhe())
                return

        # If we get here, the event number was too high
        print(
            f"Error: Event {event_number} not found in {file_display_name}. File has {i} events.",
            file=sys.stderr,
        )
        sys.exit(1)

    except FileNotFoundError:
        print(f"Error: File '{file_display_name}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{file_display_name}': {e}", file=sys.stderr)
        sys.exit(1)


def show_init(
    filepath_or_fileobj: Union[str, TextIO], file_inputs_count: int = 1
) -> None:
    """Show the init block from an LHE file.

    Args:
        filepath_or_fileobj: Path to the LHE file or file object
        file_inputs_count: Number of total files being processed
    """
    try:
        if isinstance(filepath_or_fileobj, str):
            file_display_name = filepath_or_fileobj
            lhefile = pylhe.LHEFile.fromfile(filepath_or_fileobj)
        else:
            file_display_name = "<stdin>"
            lhefile = pylhe.LHEFile.frombuffer(filepath_or_fileobj)

        if file_inputs_count > 1:
            print(f"=== {file_display_name} ===")
        print(lhefile.init.tolhe())

    except FileNotFoundError:
        print(f"Error: File '{file_display_name}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{file_display_name}': {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Display specific events or init block from LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheshow file.lhe --event 45           # Show the 45th event
  lheshow file.lhe --init               # Show the init block
  lheshow file.lhe.gz --event 1         # Show first event from gzipped file
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE file(s) to read from (or read from stdin if not provided)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--event", type=int, metavar="N", help="Show the Nth event (1-indexed)"
    )
    group.add_argument("--init", action="store_true", help="Show the init block")

    args = parser.parse_args()

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[Union[str, TextIO]] = []
    if use_stdin:
        # Read from stdin
        file_inputs += [sys.stdin]
    else:
        # Expand file paths
        for pattern in args.files:
            path = Path(pattern)
            if path.exists():
                if path.is_file():
                    file_inputs.append(str(path))
                else:
                    warnings.warn(f"{pattern} is not a file", UserWarning, stacklevel=2)
        if not file_inputs:
            print("Error: No valid files found and no stdin data", file=sys.stderr)
            sys.exit(1)

    # Execute the requested action
    for file_input in file_inputs:
        if args.event is not None:
            show_event(file_input, args.event, len(file_inputs))
        elif args.init:
            show_init(file_input, len(file_inputs))


if __name__ == "__main__":
    main()
