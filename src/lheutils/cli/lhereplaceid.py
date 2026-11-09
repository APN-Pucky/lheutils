#!/usr/bin/env python3
"""
CLI tool to replace PDG IDs of particles in an LHE file.

Useful e.g. for relabeling tau leptons as muons (15 -> 13, -15 -> -13) when a
calculation was done with taus that are meant to represent muons.
"""

import argparse
import sys
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path

import pylhe

from lheutils.cli.util import (
    add_weight_format_argument,
    create_base_parser,
    create_output_format,
    parse_weight_format,
)


def parse_id_map(values: list[str]) -> dict[int, int]:
    """Parse FROM->TO id mapping arguments into a dict."""
    id_map = {}
    for value in values:
        try:
            from_id_str, to_id_str = value.split("->")
            id_map[int(from_id_str)] = int(to_id_str)
        except ValueError:
            err = f"Invalid id mapping: {value!r} (expected FROM->TO, e.g. 15->13)"
            raise SystemExit(err) from None
    return id_map


def replace_ids(event: pylhe.LHEEvent, id_map: dict[int, int]) -> pylhe.LHEEvent:
    """Replace particle PDG IDs in an event according to id_map (in place).

    Each particle's original id is looked up and replaced exactly once, so
    swaps (e.g. 13->15 and 15->13) are applied simultaneously rather than
    chaining into each other.
    """
    original_ids = [particle.id for particle in event.particles]
    for particle, original_id in zip(event.particles, original_ids, strict=True):
        if original_id in id_map:
            particle.id = id_map[original_id]
    return event


def replace_ids_in_file(
    input_file: str,
    id_map: dict[int, int],
    weight_format: pylhe.LHEWeightFormat = pylhe.LHEWeightFormat.RWGT,
    output_file: str | None = None,
) -> None:
    """Replace particle PDG IDs throughout an LHE file."""
    if input_file == "-":
        lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
    else:
        lhefile = pylhe.LHEFile.fromfile(input_file)

    def _generator() -> Iterable[pylhe.LHEEvent]:
        for event in lhefile.events:
            yield replace_ids(event, id_map)

    output_lhefile = pylhe.LHEFile(
        init=lhefile.init,
        events=_generator(),
        header=deepcopy(lhefile.header),
        comment=lhefile.comment,
        version=lhefile.version,
        extra_attributes=lhefile.extra_attributes.copy(),
    )
    lheformat = create_output_format(weight_format)

    if output_file:
        output_lhefile.tofile(output_file, lheformat=lheformat)
    else:
        output_lhefile.write(sys.stdout, lheformat=lheformat)


def main() -> None:
    """Main entry point for lhereplaceid CLI."""
    parser = create_base_parser(
        prog="lhereplaceid",
        description="Replace particle PDG IDs in an LHE file, e.g. to relabel "
        "taus as muons.",
        epilog="Example: lhereplaceid input.lhe '15->13' '-15->-13' -o output.lhe\n"
        "         cat input.lhe | lhereplaceid - '15->13' '-15->-13'\n"
        "Note: quote each mapping (e.g. '15->13') so the shell does not "
        "interpret '->' as output redirection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("input", help="Input LHE file, or '-' to read from stdin")
    parser.add_argument("-o", "--output", help="Output file (default: write to stdout)")
    parser.add_argument(
        "mappings",
        nargs="+",
        metavar="FROM->TO",
        help="PDG ID mapping(s) to apply, e.g. 15->13 -15->-13. Repeatable "
        "for multiple mappings, including swaps (e.g. 13->15 15->13), which "
        "are applied simultaneously.",
    )

    add_weight_format_argument(parser)

    args = parser.parse_args()

    if args.input != "-" and not Path(args.input).exists():
        print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
        sys.exit(1)

    id_map = parse_id_map(args.mappings)

    replace_ids_in_file(
        input_file=args.input,
        id_map=id_map,
        weight_format=parse_weight_format(args.weight_format),
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
