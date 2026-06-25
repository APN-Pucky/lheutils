#!/usr/bin/env python3
"""
CLI tool to convert LHE files with different output format presets.

This tool allows you to convert Les Houches Event (LHE) files from one format
to another, with options to change the output format preset.
"""

import argparse
import signal
import sys
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path

import pylhe

from lheutils.cli.util import (
    add_output_format_argument,
    create_base_parser,
    parse_output_format,
)

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def _ensure_header(lhefile: pylhe.LHEFile) -> pylhe.LHEHeader:
    """Ensure the LHE file has a header so initrwgt entries can be stored."""
    if lhefile.header is None:
        lhefile.header = pylhe.LHEHeader(initrwgt=pylhe.LHEInitRWGT())
    return lhefile.header


def _find_weight_group(
    initrwgt: pylhe.LHEInitRWGT,
    group_name: str,
) -> pylhe.LHEInitRWGTWeightGroup | None:
    """Find a matching weight group by name or legacy type attribute."""
    for entry in initrwgt.entries:
        if not isinstance(entry, pylhe.LHEInitRWGTWeightGroup):
            continue
        if entry.name == group_name or entry.attributes.get("type") == group_name:
            return entry
    return None


def _find_weight_location(initrwgt: pylhe.LHEInitRWGT, weight_id: str) -> str | None:
    """Return where a weight ID already exists, if present."""
    for entry in initrwgt.entries:
        if isinstance(entry, pylhe.LHEInitRWGTWeight):
            if entry.id == weight_id:
                return "<initrwgt>"
            continue

        for weight in entry.weights:
            if weight.id == weight_id:
                group_name = entry.name or entry.attributes.get("type", "")
                if group_name:
                    return f"weight group '{group_name}'"
                return "<initrwgt>"
    return None


def _add_initrwgt_weight(
    lhefile: pylhe.LHEFile,
    group_name: str,
    weight_id: str,
    weight_text: str,
) -> str | None:
    """Add a weight definition to the initrwgt header block."""
    header = _ensure_header(lhefile)
    existing_location = _find_weight_location(header.initrwgt, weight_id)
    if existing_location is not None:
        return f"Error: Weight ID '{weight_id}' already exists in {existing_location}"

    group = _find_weight_group(header.initrwgt, group_name)
    weight = pylhe.LHEInitRWGTWeight(
        id=weight_id,
        name=weight_text,
    )

    if group is None:
        group = pylhe.LHEInitRWGTWeightGroup(
            name=group_name,
            weights=[],
        )
        header.initrwgt.entries.append(group)

    group.weights.append(weight)
    return None


def _keep_only_weight_definition(
    lhefile: pylhe.LHEFile,
    only_weight_id: str,
) -> None:
    """Keep only the requested initrwgt weight definition."""
    if lhefile.header is None:
        return

    kept_entries: list[pylhe.InitRWGTEntry] = []
    for entry in lhefile.header.initrwgt.entries:
        if isinstance(entry, pylhe.LHEInitRWGTWeight):
            if entry.id == only_weight_id:
                kept_entries.append(entry)
            continue

        kept_weights = [
            weight for weight in entry.weights if weight.id == only_weight_id
        ]
        if kept_weights:
            entry.weights = kept_weights
            kept_entries.append(entry)

    lhefile.header.initrwgt.entries = kept_entries


def convert_lhe_file(
    input_file: str,
    output_file: str | None = None,
    output_format: pylhe.LHEOutputFormat = pylhe.DEFAULT_FORMAT,
    append_lhe_weight: tuple[str, str, str] | None = None,
    only_weight_id: str | None = None,
    add_initrwgt: list[tuple[str, str, str]] | None = None,
) -> tuple[int, str]:
    """Convert an LHE file with specified options.

    Args:
        input_file: Path to the input LHE file
        output_file: Path to the output LHE file (None for stdout)
        output_format: Output format preset to use when writing
        append_lhe_weight: Optional tuple containing LHE weight group name and weight ID to append LHE weight to each event
        only_weight_id: Optional weight ID to keep; all other weights will be removed
        add_initrwgt: Optional list of tuples containing LHE weight group name, weight ID, and weight text to add to the init-rwgt block
    """
    try:
        # Read the input file
        if input_file == "-":
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
        else:
            lhefile = pylhe.LHEFile.fromfile(input_file)

        output_lhefile = pylhe.LHEFile(
            init=lhefile.init,
            header=deepcopy(lhefile.header),
            comment=lhefile.comment,
            version=lhefile.version,
            extra_attributes=lhefile.extra_attributes.copy(),
        )

        if add_initrwgt:
            for group_name, weight_id, weight_text in add_initrwgt:
                error_message = _add_initrwgt_weight(
                    output_lhefile,
                    group_name,
                    weight_id,
                    weight_text,
                )
                if error_message is not None:
                    return 1, error_message
        if append_lhe_weight is not None:
            group_name, weight_id, weight_text = append_lhe_weight
            error_message = _add_initrwgt_weight(
                output_lhefile,
                group_name,
                weight_id,
                weight_text,
            )
            if error_message is not None:
                return 1, error_message
        if only_weight_id is not None:
            _keep_only_weight_definition(output_lhefile, only_weight_id)

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
                        # After promoting this weight to central, remove all alternate weights
                        event.weights = {only_weight_id: event.eventinfo.weight}
                    else:
                        # skip this event
                        continue
                yield event

        # Write the output file
        if output_file is None:
            if (
                not isinstance(output_format, pylhe.LHEXMLFormat)
                or output_format.compress
            ):
                return (
                    1,
                    "Error: Stdout only supports uncompressed XML output formats",
                )
            output_lhefile.events = _generator()
            output_lhefile.write(
                sys.stdout,
                lheformat=output_format,
            )
        else:
            output_lhefile.events = _generator()
            output_lhefile.tofile(
                output_file,
                lheformat=output_format,
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
        description="Convert LHE files with different output format presets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhe2lhe -i input.lhe                                    # Convert to stdout
  lhe2lhe -i input.lhe -o output.lhe                     # Basic conversion
  lhe2lhe -i input.lhe -o output.lhe.gz --output-format gz      # Gzip-compressed XML output
  lhe2lhe -i input.lhe -o output.lhe --output-format weights    # XML output with <weights> blocks
  lhe2lhe -i input.lhe -o output.lhe --output-format no-weights # XML output without alternate weights
  lhe2lhe -i input.lhe -o output.h5 --output-format hdf5        # HDF5/LHEH5 output
  lhe2lhe -i input.lhe -o output.h5 --output-format hdf5-gz     # HDF5 with gzip-compressed datasets
  lhe2lhe -i input.lhe | gzip > output.lhe.gz            # Pipe to compress
  cat input.lhe | lhe2lhe                                 # Convert from stdin to stdout
  lhe2lhe < input.lhe > output.lhe                       # Redirect stdin/stdout

Output formats:
  default     - pylhe.DEFAULT_FORMAT (default XML/RWGT output)
  gz          - pylhe.GZ_FORMAT
  rwgt        - pylhe.RWGT_FORMAT
  weights     - pylhe.WEIGHTS_FORMAT
  rwgt-gz     - pylhe.RWGT_GZ_FORMAT
  weights-gz  - pylhe.WEIGHTS_GZ_FORMAT
  no-weights  - pylhe.NO_WEIGHTS_FORMAT
  hdf5        - pylhe.HDF5_FORMAT
  hdf5-gz     - pylhe.HDF5_GZ_FORMAT
        """,
    )

    parser.add_argument(
        "--input", "-i", default="-", help="Input LHE file (default: stdin)"
    )
    parser.add_argument("--output", "-o", help="Output LHE file (default: stdout)")

    add_output_format_argument(
        parser,
        "--output-format",
        help_text="Output format preset to use (default: default)",
    )

    parser.add_argument(
        "--append-lhe-weight",
        nargs=3,
        type=str,
        help="Copies the LHE weight for each event into the explicit weight block. First argument is LHE weight group name, second is weight ID, third is the text inside of the weight.",
    )

    parser.add_argument(
        "--add-initrwgt",
        action="append",
        nargs=3,
        type=str,
        help="Adds a new weight to the init-rwgt block. First argument is LHE weight group name, second is weight ID, third is the text inside of the weight.",
    )

    parser.add_argument(
        "--only-weight-id",
        type=str,
        help="Removes all weights but the specified weight. Also the central xwgtup LHE event weight is replaced.",
    )

    args = parser.parse_args()

    output_format = parse_output_format(args.output_format)

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
        input_file=args.input,
        output_file=args.output,
        output_format=output_format,
        append_lhe_weight=args.append_lhe_weight,
        only_weight_id=args.only_weight_id,
        add_initrwgt=args.add_initrwgt,
    )
    if retcode != 0:
        print(message, file=sys.stderr)
        sys.exit(retcode)


if __name__ == "__main__":
    main()
