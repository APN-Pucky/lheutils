#!/usr/bin/env python3
"""
Convert a LHE file to HepMC.
"""

import argparse
import signal
import sys
from pathlib import Path
from typing import TextIO, Union

import pyhepmc  # type: ignore[import-untyped]

from lheutils.cli.util import create_base_parser

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def convert_lhe_to_hepmc(
    input_file: Union[str, TextIO],
    output_file: Union[str, TextIO, None] = None,
    format: str = "HepMC3",
) -> None:
    """Convert LHE file to HepMC format.

    Args:
        input_file: Path to the input LHE file or file object (stdin)
        output_file: Path to the output HepMC file or file object (stdout), None for stdout
        format: HepMC output format (e.g. 'HepMC3', 'HepMC2', or 'HEPEVT')
    """
    try:
        # Determine display name for error messages
        input_display_name = input_file if isinstance(input_file, str) else "<stdin>"

        with (
            pyhepmc.open(output_file or sys.stdout, "w", format=format) as output,
            pyhepmc.open(input_file or sys.stdin, "r", format="LHEF") as input,
        ):
            for event in input:
                # event.remove_vertex(event.vertices[0])
                # event.remove_vertex(event.vertices[0])
                output.write(event)

    except FileNotFoundError:
        print(f"Error: Input file '{input_display_name}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error converting {input_display_name}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Convert LHE files to HepMC format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhe2hepmc --input events.lhe --output events.hepmc    # Convert LHE to HepMC
  lhe2hepmc --input events.lhe                          # Convert to stdout
  lhe2hepmc --output events.hepmc                       # Convert from stdin
  cat events.lhe | lhe2hepmc                            # Convert stdin to stdout
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Input LHE file (read from stdin if not provided)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output HepMC file (write to stdout if not provided)",
    )

    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["HepMC3", "HepMC2", "HEPEVT"],
        default="HepMC3",
        help="HepMC format version (default: HepMC3)",
    )

    args = parser.parse_args()

    # Determine input source
    if args.input:
        # Validate input file exists
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
            sys.exit(1)
        input_source = args.input
    else:
        # Check if reading from stdin
        if sys.stdin.isatty():
            print(
                "Error: No input file provided and no stdin data available",
                file=sys.stderr,
            )
            sys.exit(1)
        input_source = sys.stdin

    # Determine output destination
    output_destination = args.output

    # Create output directory if needed
    if output_destination is not None:
        output_path = Path(output_destination)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Perform the conversion
    convert_lhe_to_hepmc(input_source, output_destination, format=args.format)


if __name__ == "__main__":
    main()
