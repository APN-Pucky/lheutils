#!/usr/bin/env python3
"""
CLI tool to merge LHE files with identical initialization sections.

This tool merges multiple Les Houches Event (LHE) files into a single output file,
but only if all input files have exactly the same initialization section.
This ensures the merged file maintains physical consistency.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pylhe

from lheutils.cli.util import create_base_parser


def check_init_compatibility(init_files: list[pylhe.LHEInit]) -> bool:
    """
    Check if all LHEInit objects are identical.

    Args:
        init_files: List of LHEInit objects to compare

    Returns:
        True if all init sections are identical, False otherwise
    """
    if len(init_files) < 2:
        return True

    reference_init = init_files[0]

    return all(reference_init == init for init in init_files[1:])


def merge_lhe_files(
    input_files: list[str],
    output_file: Optional[str] = None,
    rwgt: bool = True,
    weights: bool = False,
) -> tuple[int, str]:
    """
    Merge multiple LHE files into a single output file or stdout.

    Args:
        input_files: List of paths to input LHE files
        output_file: Path to the output LHE file (None for stdout)
        rwgt: Whether to preserve rwgt weights in output
        weights: Whether to preserve event weights in output
    """
    # Read all input files and their initialization sections
    lhefiles = []
    init_sections = []
    total_events = 0

    for input_file in input_files:
        try:
            lhefile = pylhe.LHEFile.fromfile(input_file)

            lhefiles.append(lhefile)
            init_sections.append(lhefile.init)

        except Exception as e:
            return 1, f"Error reading input file '{input_file}': {e}"

    # Check that all initialization sections are identical
    if not check_init_compatibility(init_sections):
        return (
            1,
            """Error: Input files have different initialization sections.
        All files must have identical <init> blocks to be merged.""",
        )

    total_events = 0

    # Create merged file with events from all input files
    def merged_events() -> Iterable[pylhe.LHEEvent]:
        """Generator that yields events from all input files in sequence."""
        nonlocal total_events
        for lhefile in lhefiles:
            for event in lhefile.events:
                total_events += 1
                yield event

    # Create output file
    merged_file = pylhe.LHEFile(init=lhefiles[0].init, events=merged_events())

    # Write the merged file
    if output_file:
        merged_file.tofile(output_file, rwgt=rwgt, weights=weights)
        return (
            0,
            f"Merged {len(input_files)} files into '{output_file}' with {total_events} total events.",
        )
    merged_file.write(sys.stdout, rwgt=rwgt, weights=weights)
    return (
        0,
        f"Merged {len(input_files)} files to stdout with {total_events} total events.",
    )


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Merge LHE files with identical initialization sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhemerge input1.lhe input2.lhe input3.lhe                   # Merge to stdout
  lhemerge split_*.lhe --output merged.lhe.gz                 # Merge to compressed file
  lhemerge file1.lhe file2.lhe --no-weights                  # Merge to stdout without weights
  lhemerge a.lhe b.lhe c.lhe --output combined.lhe --rwgt    # Merge to file with rwgt weights
  lhemerge *.lhe | lhefilter --process-id 1                  # Chain with other tools
        """,
    )

    parser.add_argument(
        "input_files",
        nargs="+",
        help="Input LHE files to merge (must have identical initialization sections)",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output LHE file path (default: stdout, can include .gz extension for compression)",
    )

    parser.add_argument(
        "--weight-format",
        choices=["rwgt", "weights", "none"],
        default="rwgt",
        help="Weight format to use in output (default: rwgt)",
    )

    args = parser.parse_args()

    # Validate arguments
    if len(args.input_files) < 2:
        print("Error: At least 2 input files are required for merging", file=sys.stderr)
        sys.exit(1)

    # Check that all input files exist
    for input_file in args.input_files:
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"Error: Input file '{input_file}' does not exist", file=sys.stderr)
            sys.exit(1)
        if not input_path.is_file():
            print(f"Error: '{input_file}' is not a file", file=sys.stderr)
            sys.exit(1)

    # Check for duplicate input files
    if len(set(args.input_files)) != len(args.input_files):
        print("Error: Duplicate input files detected", file=sys.stderr)
        sys.exit(1)

    # Merge the files
    code, msg = merge_lhe_files(
        args.input_files,
        args.output,
        rwgt=args.weight_format == "rwgt",
        weights=args.weight_format == "weights",
    )
    if code != 0:
        print(msg, file=sys.stderr)
        sys.exit(code)


if __name__ == "__main__":
    main()
