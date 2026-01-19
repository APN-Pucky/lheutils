#!/usr/bin/env python3
"""
CLI tool to display information about LHE files.

This tool analyzes Les Houches Event (LHE) files and displays relevant information
including number of events, process information, particle combinations, etc.
"""

import argparse
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, Union

import pylhe
from typing_extensions import Self

from lheutils.cli.util import create_base_parser


@dataclass
class LHEChannel:
    """Information about a single channel in an LHE file."""

    incoming_pdgid: list[int]
    outgoing_pdgid: list[int]
    num_events: int
    num_negative_events: int


def merge_channels(channels: list[LHEChannel]) -> list[LHEChannel]:
    merged: dict[tuple[tuple[int, ...], tuple[int, ...]], LHEChannel] = {}
    for channel in channels:
        key = (
            tuple(sorted(channel.incoming_pdgid)),
            tuple(sorted(channel.outgoing_pdgid)),
        )
        if key not in merged:
            merged[key] = LHEChannel(
                incoming_pdgid=channel.incoming_pdgid,
                outgoing_pdgid=channel.outgoing_pdgid,
                num_events=0,
                num_negative_events=0,
            )
        merged[key].num_events += channel.num_events
        merged[key].num_negative_events += channel.num_negative_events
    return list(merged.values())


@dataclass
class LHEProcess:
    """Information about a single process in an LHE file."""

    procId: int
    xSection: float
    error: float
    channels: list[LHEChannel]


@dataclass
class LHEAccumulatedInfo:
    total_events: int
    total_negative_weighted_events: int
    total_channels: list[LHEChannel]

    def __add__(self, other: "LHEAccumulatedInfo") -> "LHEAccumulatedInfo":
        return LHEAccumulatedInfo(
            total_events=self.total_events + other.total_events,
            total_negative_weighted_events=(
                self.total_negative_weighted_events
                + other.total_negative_weighted_events
            ),
            total_channels=merge_channels(self.total_channels + other.total_channels),
        )

    def __iadd__(self, other: "LHEAccumulatedInfo") -> Self:
        self.total_events += other.total_events
        self.total_negative_weighted_events += other.total_negative_weighted_events
        self.total_channels = merge_channels(self.total_channels + other.total_channels)
        return self

    def print(self, *args: Any, **kwargs: Any) -> None:
        print("=" * 60)
        ratio = (
            self.total_negative_weighted_events / self.total_events
            if self.total_events > 0
            else 0.0
        )
        print(
            f"Total number of events: {self.total_events} (negative: {ratio:.2%})",
            *args,
            **kwargs,
        )
        sorted_channels = sorted(
            self.total_channels, key=lambda ch: ch.num_events, reverse=True
        )
        for channel in sorted_channels:
            percentage = (
                100 * channel.num_events / self.total_events
                if self.total_events > 0
                else 0.0
            )
            negative_ratio = (
                channel.num_negative_events / channel.num_events
                if channel.num_events > 0
                else 0.0
            )
            print(
                f"{channel.incoming_pdgid} -> {channel.outgoing_pdgid}: "
                f"{channel.num_events:,} events ({percentage:.1f}%, "
                f"negative: {negative_ratio:.2%})",
                *args,
                **kwargs,
            )
        print("=" * 60)


@dataclass
class LHEInfo:
    """Information about a single LHE file."""

    filepath: str
    beamA: int
    energyA: float
    pdfA: int
    beamB: int
    energyB: float
    pdfB: int
    weight_groups: dict[str, int]
    num_events: int
    negative_weighted_events: int
    process_info: list[LHEProcess]

    @property
    def negative_weighted_events_ratio(self) -> float:
        """Ratio of negative weighted events to total events."""
        return (
            self.negative_weighted_events / self.num_events
            if self.num_events > 0
            else 0.0
        )

    def print(self) -> LHEAccumulatedInfo:
        print("-" * 60)
        print(f"File: {self.filepath}")

        # Beam information
        print(f"Beam A: {self.beamA} (PDF: {self.pdfA}) @ {self.energyA} GeV")
        print(f"Beam B: {self.beamB} (PDF: {self.pdfB}) @ {self.energyB} GeV")
        # Weight groups
        if self.weight_groups:
            print("  Weight Groups:")
            for name, count in self.weight_groups.items():
                print(f"    {name}: {count} weights")
        # Number of events
        print(
            f"Number of events: {self.num_events} (negative: {self.negative_weighted_events_ratio:.2%})"
        )

        # Process information
        processes = self.process_info
        if processes:
            for proc in processes:
                print(
                    f"Process {proc.procId} cross-section: ({proc.xSection:.3e} +- {proc.error:.3e}) pb"
                )

                channels = proc.channels
                if channels:
                    # Sort channels by num_events in descending order
                    sorted_channels = sorted(
                        channels, key=lambda ch: ch.num_events, reverse=True
                    )
                    for channel in sorted_channels:
                        percentage = (
                            100 * channel.num_events / self.num_events
                            if self.num_events > 0
                            else 0.0
                        )
                        negative_ratio = (
                            channel.num_negative_events / channel.num_events
                            if channel.num_events > 0
                            else 0.0
                        )
                        print(
                            f"  {channel.incoming_pdgid} -> {channel.outgoing_pdgid}: {channel.num_events:,} events ({percentage:.1f}%, negative: {negative_ratio:.2%})"
                        )

        return LHEAccumulatedInfo(
            total_events=self.num_events,
            total_negative_weighted_events=self.negative_weighted_events,
            total_channels=merge_channels(
                [channel for pi in self.process_info for channel in pi.channels]
            ),
        )


# TODO add weight variance
def get_lheinfo(filepath_or_fileobj: Union[str, TextIO]) -> LHEInfo:
    # Read LHE file
    if isinstance(filepath_or_fileobj, str):
        lhefile = pylhe.LHEFile.fromfile(filepath_or_fileobj)
        file_display_name = filepath_or_fileobj
    else:
        lhefile = pylhe.LHEFile.frombuffer(filepath_or_fileobj)
        file_display_name = "<stdin>"
    init_info = lhefile.init.initInfo

    initial_final_combinations: Counter[
        tuple[int, tuple[int, ...], tuple[int, ...]]
    ] = Counter()

    initial_final_negative_combinations: Counter[
        tuple[int, tuple[int, ...], tuple[int, ...]]
    ] = Counter()

    num_events = 0
    num_negative_weighted_events = 0
    for event in lhefile.events:
        num_events += 1

        initial = []
        final = []

        for particle in event.particles:
            if particle.status == -1:  # Incoming particles
                initial.append(particle.id)
            elif particle.status == 1:  # Outgoing particles
                final.append(particle.id)

        # Count initial particles
        initial_tuple = tuple(sorted(initial))

        # Count final particles
        final_tuple = tuple(sorted(final))

        # Count initial -> final combinations
        combination = (event.eventinfo.pid, initial_tuple, final_tuple)
        initial_final_combinations[combination] += 1
        if event.eventinfo.weight < 0:
            num_negative_weighted_events += 1
            initial_final_negative_combinations[combination] += 1

    return LHEInfo(
        filepath=file_display_name,
        beamA=init_info.beamA,
        pdfA=init_info.PDFsetA,
        energyA=init_info.energyA,
        beamB=init_info.beamB,
        energyB=init_info.energyB,
        pdfB=init_info.PDFsetB,
        weight_groups={
            name: len(wg.weights) for name, wg in lhefile.init.weightgroup.items()
        },
        num_events=num_events,
        negative_weighted_events=num_negative_weighted_events,
        process_info=[
            LHEProcess(
                procId=proc.procId,
                xSection=proc.xSection,
                error=proc.error,
                channels=[
                    LHEChannel(
                        incoming_pdgid=list(incoming_pdgid),
                        outgoing_pdgid=list(outgoing_pdgid),
                        num_events=count,
                        num_negative_events=initial_final_negative_combinations.get(
                            (pid, incoming_pdgid, outgoing_pdgid), 0
                        ),
                    )
                    for (
                        pid,
                        incoming_pdgid,
                        outgoing_pdgid,
                    ), count in initial_final_combinations.items()
                    if pid == proc.procId
                ],
            )
            for proc in lhefile.init.procInfo
        ],
    )


def get_lhesummary(
    filepaths_or_fileobjs: list[Union[str, TextIO]],
) -> LHEAccumulatedInfo:
    lheacc = LHEAccumulatedInfo(
        total_events=0,
        total_negative_weighted_events=0,
        total_channels=[],
    )
    # Analyze all files
    for filepath_or_fileobj in filepaths_or_fileobjs:
        lheinfo = get_lheinfo(filepath_or_fileobj)
        lheacc += lheinfo.print()

    return lheacc


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Display information about LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheinfo file.lhe                      # Analyze single file (plain format)
  cat file.lhe | lheinfo                # Read from stdin
  lheinfo *.lhe                         # Analyze multiple files
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE file(s) to analyze (or read from stdin if not provided)",
    )

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

    get_lhesummary(file_inputs).print()


if __name__ == "__main__":
    main()
