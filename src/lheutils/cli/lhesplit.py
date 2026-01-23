#!/usr/bin/env python3
"""
CLI tool to split LHE files into multiple smaller files.

This tool splits Les Houches Event (LHE) files into multiple output files
with approximately equal numbers of events distributed among them.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

import pylhe

from lheutils.cli.util import create_base_parser


def split_lhe_file(
    input_file: str,
    output_base: str,
    num_events: int,
    rwgt: bool = True,
    weights: bool = True,
) -> tuple[int, str]:
    """
    Split an LHE file into multiple output files.

    Args:
        input_file: Path to the input LHE file
        output_base: Base name for output files including .lhe or .lhe.gz extension
        num_events: Number of events per output file
        rwgt: Whether to use rwgt section if present in the input file
        weights: Whether to preserve event weights in output
    """
    # Read the LHE file
    try:
        if input_file == "-":
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
            events_iter = iter(lhefile.events)
        else:
            lhefile = pylhe.LHEFile.fromfile(input_file)
            events_iter = iter(lhefile.events)
    except Exception as e:
        source = "stdin" if input_file == "-" else f"file '{input_file}'"
        return 1, f"Error reading input {source}: {e}"

    # events per file
    events_per_file = num_events

    exhausted = False

    def _generator() -> Iterable[pylhe.LHEEvent]:
        nonlocal exhausted
        for _ in range(events_per_file):
            try:
                yield next(events_iter)
            except StopIteration:
                exhausted = True
                break

    i = 0
    while not exhausted:
        i += 1
        output_filename = f"{output_base.replace('.', f'_{i}.', 1)}"
        new_file = pylhe.LHEFile(init=lhefile.init, events=_generator())
        new_file.tofile(output_filename, rwgt=rwgt, weights=weights)
    return (
        0,
        f"Split events into {i} files with base name '{output_base}'.",
    )


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Split LHE events from input file into multiple output files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhesplit -i input.lhe -o output.lhe 3           # Split into output_1.lhe, output_2.lhe, output_3.lhe
  lhesplit -i events.lhe -o split.lhe.gz 5        # Split into split_1.lhe.gz, split_2.lhe.gz, ... (compressed)
  cat input.lhe | lhesplit -o output.lhe 2     # Split from stdin into output_0.lhe, output_1.lhe
  lhesplit -o output.lhe 4 < input.lhe         # Split from stdin (alternative syntax)
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        default="-",
        help="Input LHE file to split (default: stdin)",
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Base name for output files including .lhe or .lhe.gz extension",
    )

    parser.add_argument(
        "num_events",
        type=int,
        help="Number of events per output file",
    )

    parser.add_argument(
        "--no-weights",
        action="store_true",
        help="Do not preserve event weights in output files",
    )

    parser.add_argument(
        "--rwgt",
        action="store_true",
        help="Use rwgt section if present in the input file",
    )

    args = parser.parse_args()

    # Check if input file exists (skip validation for stdin)
    if args.input != "-":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
            sys.exit(1)

        if not input_path.is_file():
            print(f"Error: '{args.input}' is not a file", file=sys.stderr)
            sys.exit(1)

    # Split the file
    code, msg = split_lhe_file(
        args.input,
        args.output,
        args.num_events,
        rwgt=args.rwgt,
        weights=not args.no_weights,
    )

    if code != 0:
        print(msg, file=sys.stderr)
        sys.exit(code)


if __name__ == "__main__":
    main()
