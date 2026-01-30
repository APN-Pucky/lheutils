#!/usr/bin/env python3
"""
CLI tool to convert LHE files with different compression and weight format options.

This tool allows you to convert Les Houches Event (LHE) files from one format
to another, with options to change compression and weight format.
"""

import argparse
import signal
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pylhe

from lheutils.cli.util import create_base_parser

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def convert_lhe_file(
    input_file: str,
    output_file: Optional[str] = None,
    compress: bool = False,
    weight_format: str = "rwgt",
    append_lhe_weight: Optional[tuple[str, str, str]] = None,
    only_weight_id: Optional[str] = None,
) -> tuple[int, str]:
    """Convert an LHE file with specified options.

    Args:
        input_file: Path to the input LHE file
        output_file: Path to the output LHE file (None for stdout)
        compress: Whether to compress the output file
        weight_format: Weight format to use ('rwgt', 'init-rwgt', or 'none')
        append_lhe_weight: Optional tuple containing LHE weight group name and weight ID to append LHE weight to each event
        only_weight_id: Optional weight ID to keep; all other weights will be removed
    """
    try:
        # Read the input file
        if input_file == "-":
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
        else:
            lhefile = pylhe.LHEFile.fromfile(input_file)

        # Determine weight options based on format
        if weight_format == "rwgt":
            rwgt = True
            weights = False
        elif weight_format == "weights":
            rwgt = False
            weights = True
        elif weight_format == "none":
            rwgt = False
            weights = False
        else:
            return 1, f"Error: Invalid weight format: {weight_format}"

        if append_lhe_weight is not None:
            group_name, weight_id, weight_text = append_lhe_weight
            index = 0
            for wg in lhefile.init.weightgroup.values():
                if weight_id in wg.weights:
                    return (
                        1,
                        f"Error: Weight ID '{weight_id}' already exists in group '{wg}'",
                    )
                for w in wg.weights.values():
                    index = max(index, w.index)
            if group_name not in lhefile.init.weightgroup:
                # create weight group
                lhefile.init.weightgroup[group_name] = pylhe.LHEWeightGroup(
                    attrib={"name": group_name}, weights={}
                )
            if weight_id not in lhefile.init.weightgroup[group_name].weights:
                lhefile.init.weightgroup[group_name].weights[weight_id] = (
                    pylhe.LHEWeightInfo(
                        name=weight_text, attrib={"id": weight_id}, index=index + 1
                    )
                )
        if only_weight_id is not None:
            # Validate that the weight ID exists in the init block
            found = False
            for wg in lhefile.init.weightgroup.values():
                if only_weight_id in wg.weights:
                    found = True
                    break
            if not found:
                return (
                    1,
                    f"Error: Weight ID '{only_weight_id}' not found in init weight groups: {[wg.weights.keys() for wg in lhefile.init.weightgroup.values()]}",
                )
            # Remove all other weights from init block
            for wg in lhefile.init.weightgroup.values():
                if only_weight_id in wg.weights:
                    wg.weights = {only_weight_id: wg.weights[only_weight_id]}
                else:
                    wg.weights = {}
            # Remove empty weight groups
            lhefile.init.weightgroup = {
                name: wg
                for name, wg in lhefile.init.weightgroup.items()
                if len(wg.weights) > 0
            }

        # Event loop generator with modifications if needed
        def _generator() -> Iterable[pylhe.LHEEvent]:
            for event in lhefile.events:
                if append_lhe_weight is not None:
                    _group_name, weight_id, _weight_text = append_lhe_weight
                    event.weights[weight_id] = event.eventinfo.weight
                if only_weight_id is not None:
                    # Replace the central weight with the specified weight and remove others
                    if only_weight_id in event.weights:
                        event.eventinfo.weight = event.weights[only_weight_id]
                        event.weights = {only_weight_id: event.weights[only_weight_id]}
                    else:
                        # skip this event
                        continue
                yield event

        # Write the output file
        if output_file is None:
            if compress:
                return (
                    1,
                    f"Error: Compression option ignored when writing to stdout (use `lhe2lhe {input_file} | gzip`)",
                )
            pylhe.LHEFile(lhefile.init, _generator()).write(
                sys.stdout,
                rwgt=rwgt,
                weights=weights,
            )
        else:
            pylhe.LHEFile(lhefile.init, _generator()).tofile(
                output_file,
                gz=compress,
                rwgt=rwgt,
                weights=weights,
            )

    except FileNotFoundError:
        if input_file == "-":
            return 1, "Error: Unable to read from stdin"
        return 1, f"Error: Input file '{input_file}' not found"
    except Exception as e:
        source = "stdin" if input_file == "-" else f"input file '{input_file}'"
        return 1, f"Error during conversion from {source}: {e}"
    return 0, "Conversion successful"


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Convert LHE files with different compression and weight format options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhe2lhe input.lhe                                       # Convert to stdout
  lhe2lhe input.lhe output.lhe                           # Basic conversion
  lhe2lhe input.lhe output.lhe.gz --compress             # Compress output
  lhe2lhe input.lhe output.lhe --weight-format init-rwgt # Use init-rwgt format
  lhe2lhe input.lhe.gz output.lhe --weight-format none   # Remove weights
  lhe2lhe input.lhe output.lhe.gz -c -w rwgt             # Short options
  lhe2lhe input.lhe | gzip > output.lhe.gz               # Pipe to compress
  cat input.lhe | lhe2lhe                                 # Convert from stdin to stdout
  lhe2lhe < input.lhe > output.lhe                       # Redirect stdin/stdout

Weight formats:
  rwgt      - Include weights in 'rwgt' format (default)
  init-rwgt - Include weights in 'init-rwgt' format (both rwgt and weights)
  none      - Exclude all weights
        """,
    )

    parser.add_argument(
        "input", nargs="?", default="-", help="Input LHE file (default: stdin)"
    )
    parser.add_argument("output", nargs="?", help="Output LHE file (default: stdout)")

    parser.add_argument(
        "--compress",
        "-c",
        action=argparse.BooleanOptionalAction,
        help="Compress the output file (ignored if output filename ends with .gz/.gzip)",
        default=False,
    )

    parser.add_argument(
        "--weight-format",
        "-w",
        choices=["rwgt", "weights", "none"],
        default="rwgt",
        help="Weight format to use in output (default: rwgt)",
    )

    parser.add_argument(
        "--append-lhe-weight",
        nargs=3,
        type=str,
        help="Copies the LHE weight for each event into the explicit weight block. First argument is LHE weight group name, second is weight ID, third is the text inside of the weight.",
    )

    parser.add_argument(
        "--only-weight-id",
        type=str,
        help="Removes all weights but the specified weight. Also the central xwgtup LHE event weight is replaced.",
    )

    args = parser.parse_args()

    # Validate input file exists (skip validation for stdin)
    if args.input != "-":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
            sys.exit(1)

    # Check if output directory exists and create it if needed
    if args.output is not None:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Perform the conversion
    retcode, message = convert_lhe_file(
        args.input,
        args.output,
        args.compress,
        args.weight_format,
        args.append_lhe_weight,
        args.only_weight_id,
    )
    if retcode != 0:
        print(message, file=sys.stderr)
        sys.exit(retcode)


if __name__ == "__main__":
    main()
