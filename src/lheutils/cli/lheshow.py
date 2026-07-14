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
from typing import TextIO

import pylhe

from lheutils.cli.util import (
    create_base_parser,
    lhapdf_name_and_id,
    pdg_name,
    pdg_name_and_id,
)

SHOW_FORMAT_CHOICES = ("pretty", "repr", "lhe")


def _format_number(value: float) -> str:
    """Format numeric values for concise human-readable output."""
    return f"{value:.6g}"


def _format_optional_attribute(
    attributes: dict[str, str],
    key: str,
) -> str:
    """Return a stripped event attribute value or ``None`` when absent."""
    value = attributes.get(key)
    if value is None:
        return "None"
    return value.strip()


def _format_extra_event_attributes(attributes: dict[str, str]) -> str:
    """Return formatted non-standard XML event attributes."""
    extra_attributes = {
        key: value.strip()
        for key, value in attributes.items()
        if key not in {"npLO", "npNLO"}
    }
    if not extra_attributes:
        return "None"
    return ", ".join(
        f"{key}={value}" for key, value in sorted(extra_attributes.items())
    )


def _format_scales(scales: dict[str, float]) -> str:
    """Return formatted event scale entries."""
    if not scales:
        return "None"
    return ", ".join(
        f"{key}={_format_number(value)}" for key, value in sorted(scales.items())
    )


def _format_event_pretty(event: pylhe.LHEEvent) -> str:
    """Return a human-readable summary of an event."""
    incoming = [
        pdg_name(particle.id) for particle in event.particles if particle.status == -1
    ]
    outgoing = [
        pdg_name(particle.id) for particle in event.particles if particle.status == 1
    ]

    lines = [
        "Event Summary",
        f"  Process ID: {event.eventinfo.pid}",
        f"  Central weight: {_format_number(event.eventinfo.weight)}",
        f"  Scale: {_format_number(event.eventinfo.scale)}",
        f"  alpha_QED: {_format_number(event.eventinfo.aqed)}",
        f"  alpha_QCD: {_format_number(event.eventinfo.aqcd)}",
        f"  XML attributes: {_format_extra_event_attributes(event.attributes)}",
        f"  Incoming PDG IDs: {incoming}",
        f"  Outgoing PDG IDs: {outgoing}",
        f"  Number of weights: {len(event.weights)}",
        f"  Scales: {_format_scales(event.scales)}",
        f"  Comment: {event.optional}",
        "  Particles:",
    ]

    for index, particle in enumerate(event.particles, start=1):
        lines.append(
            "    "
            f"{index}: {pdg_name_and_id(particle.id)} status={particle.status} "
            f"mothers=({particle.mother1}, {particle.mother2}) "
            f"color=({particle.color1}, {particle.color2}) "
            f"P=({_format_number(particle.px)}, {_format_number(particle.py)}, {_format_number(particle.pz)}) "
            f"E={_format_number(particle.e)} M={_format_number(particle.m)} "
            f"lifetime={_format_number(particle.lifetime)} "
            f"spin={_format_number(particle.spin)}"
        )

    return "\n".join(lines)


def _format_init_pretty(lheinit: pylhe.LHEInit) -> str:
    """Return a human-readable summary of an init block."""
    init_info = lheinit.initInfo
    lines = [
        "Init Summary",
        (
            f"  Beam A: {pdg_name_and_id(init_info.beamA)} @ {_format_number(init_info.energyA)} GeV "
            f"(PDF group {init_info.PDFgroupA}, set {lhapdf_name_and_id(init_info.PDFsetA)})"
        ),
        (
            f"  Beam B: {pdg_name_and_id(init_info.beamB)} @ {_format_number(init_info.energyB)} GeV "
            f"(PDF group {init_info.PDFgroupB}, set {lhapdf_name_and_id(init_info.PDFsetB)})"
        ),
        f"  Weighting strategy: {init_info.weightingStrategy}",
        f"  Number of processes: {init_info.numProcesses}",
        f"  Number of Generators: {len(lheinit.generators)}",
    ]

    if lheinit.generators:
        lines.append("  Generator details:")
        for generator in lheinit.generators:
            lines.append(
                f"    {generator.name} v{generator.version}: {generator.description}"
            )

    if lheinit.procInfo:
        lines.append("  Processes:")
        for proc in lheinit.procInfo:
            lines.append(
                "    "
                f"procId={proc.procId} xSection={_format_number(proc.xSection)} "
                f"error={_format_number(proc.error)} unitWeight={_format_number(proc.unitWeight)} "
                f"npLO={proc.npLO} npNLO={proc.npNLO}"
            )

    return "\n".join(lines)


def _format_output(
    block: pylhe.LHEEvent | pylhe.LHEInit,
    output_format: str,
) -> str:
    """Format an event or init block according to the requested output format."""
    if output_format == "lhe":
        return block.tolhe()
    if output_format == "repr":
        return repr(block)
    if isinstance(block, pylhe.LHEEvent):
        return _format_event_pretty(block)
    return _format_init_pretty(block)


def show_event(
    filepath_or_fileobj: str | TextIO,
    event_number: int,
    output_format: str = "pretty",
    file_inputs_count: int = 1,
) -> None:
    """Show a specific event from an LHE file.

    Args:
        filepath_or_fileobj: Path to the LHE file or file object
        event_number: Event number to display (1-indexed)
        output_format: Output format to display
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
                print(_format_output(event, output_format))
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
    filepath_or_fileobj: str | TextIO,
    output_format: str = "pretty",
    file_inputs_count: int = 1,
) -> None:
    """Show the init block from an LHE file.

    Args:
        filepath_or_fileobj: Path to the LHE file or file object
        output_format: Output format to display
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
        print(_format_output(lhefile.init, output_format))

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
  lheshow file.lhe --event 45                # Pretty-print the 45th event
  lheshow file.lhe --init --format repr     # Show the init block as Python repr
  lheshow file.lhe.gz --event 1 --format lhe # Show first event in raw LHE/XML form
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
    parser.add_argument(
        "--format",
        choices=SHOW_FORMAT_CHOICES,
        default="pretty",
        help="Display format to use: pretty (default), repr, or raw lhe/xml",
    )

    args = parser.parse_args()

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[str | TextIO] = []
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
            show_event(file_input, args.event, args.format, len(file_inputs))
        elif args.init:
            show_init(file_input, args.format, len(file_inputs))


if __name__ == "__main__":
    main()
