#!/usr/bin/env python3
"""
CLI tool to compare and diff two LHE files.

This tool compares two Les Houches Event (LHE) files and reports differences
in their initialization sections, event counts, and optionally event contents.
"""

import argparse
import math
import signal
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Any

import pylhe
from typing_extensions import Self

from lheutils.cli.util import create_base_parser

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def diff_lhe_event_infos(
    lheei1: pylhe.LHEEventInfo, lheei2: pylhe.LHEEventInfo
) -> pylhe.LHEEventInfo:
    """
    Compare LHEEventInfo objects from two LHE files and report differences.

    Args:
        lheei1: LHEEventInfo from first file
        lheei2: LHEEventInfo from second file
    """
    return pylhe.LHEEventInfo(
        nparticles=lheei1.nparticles - lheei2.nparticles,
        pid=lheei1.pid - lheei2.pid,
        weight=lheei1.weight - lheei2.weight,
        scale=lheei1.scale - lheei2.scale,
        aqed=lheei1.aqed - lheei2.aqed,
        aqcd=lheei1.aqcd - lheei2.aqcd,
    )


def diff_lhe_particles(
    p1: pylhe.LHEParticle, p2: pylhe.LHEParticle
) -> pylhe.LHEParticle:
    """
    Compare two LHEParticle objects and report differences.

    Args:
        p1: First LHEParticle
        p2: Second LHEParticle
    Returns:
        Dictionary of differing attributes with their values
    """
    return pylhe.LHEParticle(
        id=p1.id - p2.id,
        status=p1.status - p2.status,
        mother1=p1.mother1 - p2.mother1,
        mother2=p1.mother2 - p2.mother2,
        color1=p1.color1 - p2.color1,
        color2=p1.color2 - p2.color2,
        px=p1.px - p2.px,
        py=p1.py - p2.py,
        pz=p1.pz - p2.pz,
        e=p1.e - p2.e,
        m=p1.m - p2.m,
        lifetime=p1.lifetime - p2.lifetime,
        spin=p1.spin - p2.spin,
    )


@dataclass
class LHEAccumulatedDiff:
    ndiff: int

    def __add__(self, other: "LHEAccumulatedDiff") -> "LHEAccumulatedDiff":
        """Add two LHEAccumulatedDiff objects together."""
        return LHEAccumulatedDiff(ndiff=self.ndiff + other.ndiff)

    def __iadd__(self, other: "LHEAccumulatedDiff") -> Self:
        """In-place addition for LHEAccumulatedDiff objects."""
        self.ndiff += other.ndiff
        return self

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print the number of differences."""
        print(f"Total differences: {self.ndiff}", *args, **kwargs)


@dataclass
class LHEDiff:
    """Generic dataclass to store differences between old and new values."""

    old: Any
    new: Any

    def print(self, *args: Any, **kwargs: Any) -> LHEAccumulatedDiff:
        print(f"{self.old} -> {self.new}", *args, **kwargs)
        return LHEAccumulatedDiff(ndiff=1)


@dataclass
class LHEInitDiff:
    """Dataclass to store differences in LHE initialization sections."""

    diffs: dict[str, LHEDiff]

    def print(self, *args: Any, end: str = "\n", **kwargs: Any) -> LHEAccumulatedDiff:
        lhead = LHEAccumulatedDiff(ndiff=0)
        for key, diff in self.diffs.items():
            print(f"{key}: ", *args, end="", **kwargs)
            lhead += diff.print(*args, end=end, **kwargs)
        return lhead


def diff_lhe_init(
    lhei1: pylhe.LHEInit,
    lhei2: pylhe.LHEInit,
    lheh1: pylhe.LHEHeader | None,
    lheh2: pylhe.LHEHeader | None,
    version1: str,
    version2: str,
    check_init: bool,
    check_weights: bool,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> LHEInitDiff:
    """
    Compare LHEInitInfo objects from two LHE files and report differences.

    Args:
        lheii1: LHEInitInfo from first file
        lheii2: LHEInitInfo from second file
        check_init: Whether to check initialization section
        check_weights: Whether to check weight groups and weights
        absolute_tolerance: Absolute tolerance for numeric comparisons
        relative_tolerance: Relative tolerance for numeric comparisons
    """
    diffs = {}

    def _diff_attributes(
        prefix: str,
        attributes1: dict[str, str],
        attributes2: dict[str, str],
    ) -> None:
        if attributes1 == attributes2:
            return

        if len(attributes1) != len(attributes2):
            diffs[f"{prefix}_num_attrib"] = LHEDiff(
                old=len(attributes1), new=len(attributes2)
            )

        for key in sorted(set(attributes1) | set(attributes2)):
            in_attributes1 = key in attributes1
            in_attributes2 = key in attributes2

            if not in_attributes1 or not in_attributes2:
                diffs[f"{prefix}_attrib_key_{key}"] = LHEDiff(
                    old=key if in_attributes1 else None,
                    new=key if in_attributes2 else None,
                )
                diffs[f"{prefix}_attrib_value_{key}"] = LHEDiff(
                    old=attributes1.get(key), new=attributes2.get(key)
                )
                continue

            if attributes1[key] != attributes2[key]:
                diffs[f"{prefix}_attrib_value_{key}"] = LHEDiff(
                    old=attributes1[key], new=attributes2[key]
                )

    def _weight_group_name(
        weight_group: pylhe.LHEInitRWGTWeightGroup,
        index: int,
    ) -> str:
        return weight_group.name or weight_group.attributes.get(
            "type", f"group_{index}"
        )

    def _diff_weight_list(
        prefix: str,
        weights1: list[pylhe.LHEInitRWGTWeight],
        weights2: list[pylhe.LHEInitRWGTWeight],
    ) -> None:
        if len(weights1) != len(weights2):
            diffs[f"{prefix}_num_weights"] = LHEDiff(
                old=len(weights1), new=len(weights2)
            )
        for index, (weight1, weight2) in enumerate(zip(weights1, weights2), start=1):
            weight_key = weight1.id or f"weight_{index}"
            if weight1.id != weight2.id:
                diffs[f"{prefix}_weight_key_{weight_key}"] = LHEDiff(
                    old=weight1.id, new=weight2.id
                )
            if weight1.name != weight2.name:
                diffs[f"{prefix}_weight_{weight_key}_name"] = LHEDiff(
                    old=weight1.name, new=weight2.name
                )
            _diff_attributes(
                f"{prefix}_weight_{weight_key}",
                weight1.attributes,
                weight2.attributes,
            )

    def _diff_initrwgt() -> None:
        entries1 = [] if lheh1 is None else lheh1.initrwgt.entries
        entries2 = [] if lheh2 is None else lheh2.initrwgt.entries

        weight_groups1 = [
            entry
            for entry in entries1
            if isinstance(entry, pylhe.LHEInitRWGTWeightGroup)
        ]
        weight_groups2 = [
            entry
            for entry in entries2
            if isinstance(entry, pylhe.LHEInitRWGTWeightGroup)
        ]
        if len(weight_groups1) != len(weight_groups2):
            diffs["num_weight_groups"] = LHEDiff(
                old=len(weight_groups1), new=len(weight_groups2)
            )

        for index, (wg1, wg2) in enumerate(
            zip(weight_groups1, weight_groups2), start=1
        ):
            group_name = _weight_group_name(wg1, index)
            group_name2 = _weight_group_name(wg2, index)
            if group_name != group_name2:
                diffs[f"weight_group_key_{group_name}"] = LHEDiff(
                    old=group_name, new=group_name2
                )
            _diff_attributes(
                f"weight_group_{group_name}", wg1.attributes, wg2.attributes
            )
            _diff_weight_list(f"weight_group_{group_name}", wg1.weights, wg2.weights)

        direct_weights1 = [
            entry for entry in entries1 if isinstance(entry, pylhe.LHEInitRWGTWeight)
        ]
        direct_weights2 = [
            entry for entry in entries2 if isinstance(entry, pylhe.LHEInitRWGTWeight)
        ]
        if len(direct_weights1) != len(direct_weights2):
            diffs["num_initrwgt_weights"] = LHEDiff(
                old=len(direct_weights1), new=len(direct_weights2)
            )
        _diff_weight_list("initrwgt", direct_weights1, direct_weights2)

    if check_init:
        if lhei1.initInfo.beamA != lhei2.initInfo.beamA:
            diffs["beamA"] = LHEDiff(old=lhei1.initInfo.beamA, new=lhei2.initInfo.beamA)
        if not math.isclose(
            lhei1.initInfo.energyA,
            lhei2.initInfo.energyA,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            diffs["energyA"] = LHEDiff(
                old=lhei1.initInfo.energyA, new=lhei2.initInfo.energyA
            )
        if lhei1.initInfo.beamB != lhei2.initInfo.beamB:
            diffs["beamB"] = LHEDiff(old=lhei1.initInfo.beamB, new=lhei2.initInfo.beamB)
        if not math.isclose(
            lhei1.initInfo.energyB,
            lhei2.initInfo.energyB,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            diffs["energyB"] = LHEDiff(
                old=lhei1.initInfo.energyB, new=lhei2.initInfo.energyB
            )
        if lhei1.initInfo.PDFgroupA != lhei2.initInfo.PDFgroupA:
            diffs["PDFgroupA"] = LHEDiff(
                old=lhei1.initInfo.PDFgroupA, new=lhei2.initInfo.PDFgroupA
            )
        if lhei1.initInfo.PDFgroupB != lhei2.initInfo.PDFgroupB:
            diffs["PDFgroupB"] = LHEDiff(
                old=lhei1.initInfo.PDFgroupB, new=lhei2.initInfo.PDFgroupB
            )
        if lhei1.initInfo.PDFsetA != lhei2.initInfo.PDFsetA:
            diffs["PDFsetA"] = LHEDiff(
                old=lhei1.initInfo.PDFsetA, new=lhei2.initInfo.PDFsetA
            )
        if lhei1.initInfo.PDFsetB != lhei2.initInfo.PDFsetB:
            diffs["PDFsetB"] = LHEDiff(
                old=lhei1.initInfo.PDFsetB, new=lhei2.initInfo.PDFsetB
            )
        if lhei1.initInfo.weightingStrategy != lhei2.initInfo.weightingStrategy:
            diffs["weightingStrategy"] = LHEDiff(
                old=lhei1.initInfo.weightingStrategy,
                new=lhei2.initInfo.weightingStrategy,
            )
        if lhei1.initInfo.numProcesses != lhei2.initInfo.numProcesses:
            diffs["numProcesses"] = LHEDiff(
                old=lhei1.initInfo.numProcesses, new=lhei2.initInfo.numProcesses
            )

        for proc1, proc2 in zip(lhei1.procInfo, lhei2.procInfo):
            if not math.isclose(
                proc1.xSection,
                proc2.xSection,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_xSection"] = LHEDiff(
                    old=proc1.xSection, new=proc2.xSection
                )
            if not math.isclose(
                proc1.error,
                proc2.error,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_error"] = LHEDiff(
                    old=proc1.error, new=proc2.error
                )
            if not math.isclose(
                proc1.unitWeight,
                proc2.unitWeight,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_unitWeight"] = LHEDiff(
                    old=proc1.unitWeight, new=proc2.unitWeight
                )
            if proc1.procId != proc2.procId:
                diffs[f"process_{proc1.procId}_procId"] = LHEDiff(
                    old=proc1.procId, new=proc2.procId
                )

        if check_weights:
            _diff_initrwgt()

        if version1 != version2:
            diffs["LHEVersion"] = LHEDiff(old=version1, new=version2)

    return LHEInitDiff(diffs=diffs)


@dataclass
class LHEEventDiff:
    """Dataclass to store differences in LHE initialization sections."""

    event_index: int
    diffs: dict[str, LHEDiff]

    def print(self, *args: Any, end: str = "\n", **kwargs: Any) -> LHEAccumulatedDiff:
        lhead = LHEAccumulatedDiff(ndiff=0)
        for key, diff in self.diffs.items():
            print(f"{key}: ", *args, end="", **kwargs)
            lhead += diff.print(*args, end=end, **kwargs)
        return lhead


def diff_lhe_events(
    events1: Iterable[pylhe.LHEEvent],
    events2: Iterable[pylhe.LHEEvent],
    check_events: bool,
    abs_tol: float,
    rel_tol: float,
) -> Iterable[LHEEventDiff]:
    for j, (event1, event2) in enumerate(zip_longest(events1, events2), start=1):
        diffs = {}
        if event1 is None:
            diffs[f"event_{j}"] = LHEDiff(old="missing", new="present")
            yield LHEEventDiff(event_index=j, diffs=diffs)
            continue
        if event2 is None:
            diffs[f"event_{j}"] = LHEDiff(old="present", new="missing")
            yield LHEEventDiff(event_index=j, diffs=diffs)
            continue
        if check_events:
            if event1.eventinfo.nparticles != event2.eventinfo.nparticles:
                diffs[f"event_{j}_eventinfo_nparticles"] = LHEDiff(
                    old=event1.eventinfo.nparticles, new=event2.eventinfo.nparticles
                )
            if event1.eventinfo.pid != event2.eventinfo.pid:
                diffs[f"event_{j}_eventinfo_pid"] = LHEDiff(
                    old=event1.eventinfo.pid, new=event2.eventinfo.pid
                )
            if not math.isclose(
                event1.eventinfo.weight,
                event2.eventinfo.weight,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_weight"] = LHEDiff(
                    old=event1.eventinfo.weight, new=event2.eventinfo.weight
                )
            if not math.isclose(
                event1.eventinfo.scale,
                event2.eventinfo.scale,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_scale"] = LHEDiff(
                    old=event1.eventinfo.scale, new=event2.eventinfo.scale
                )
            if not math.isclose(
                event1.eventinfo.aqed,
                event2.eventinfo.aqed,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_aqed"] = LHEDiff(
                    old=event1.eventinfo.aqed, new=event2.eventinfo.aqed
                )
            if not math.isclose(
                event1.eventinfo.aqcd,
                event2.eventinfo.aqcd,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_aqcd"] = LHEDiff(
                    old=event1.eventinfo.aqcd, new=event2.eventinfo.aqcd
                )

            if len(event1.particles) != len(event2.particles):
                diffs[f"event_{j}_num_particles"] = LHEDiff(
                    old=len(event1.particles), new=len(event2.particles)
                )
            for i, (p1, p2) in enumerate(
                zip(event1.particles, event2.particles), start=1
            ):
                if p1.id != p2.id:
                    diffs[f"event_{j}_particle_{i}_id"] = LHEDiff(old=p1.id, new=p2.id)
                if p1.status != p2.status:
                    diffs[f"event_{j}_particle_{i}_status"] = LHEDiff(
                        old=p1.status, new=p2.status
                    )
                if p1.mother1 != p2.mother1:
                    diffs[f"event_{j}_particle_{i}_mother1"] = LHEDiff(
                        old=p1.mother1, new=p2.mother1
                    )
                if p1.mother2 != p2.mother2:
                    diffs[f"event_{j}_particle_{i}_mother2"] = LHEDiff(
                        old=p1.mother2, new=p2.mother2
                    )
                if p1.color1 != p2.color1:
                    diffs[f"event_{j}_particle_{i}_color1"] = LHEDiff(
                        old=p1.color1, new=p2.color1
                    )
                if p1.color2 != p2.color2:
                    diffs[f"event_{j}_particle_{i}_color2"] = LHEDiff(
                        old=p1.color2, new=p2.color2
                    )
                if not math.isclose(p1.px, p2.px, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_px"] = LHEDiff(old=p1.px, new=p2.px)
                if not math.isclose(p1.py, p2.py, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_py"] = LHEDiff(old=p1.py, new=p2.py)
                if not math.isclose(p1.pz, p2.pz, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_pz"] = LHEDiff(old=p1.pz, new=p2.pz)
                if not math.isclose(p1.e, p2.e, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_e"] = LHEDiff(old=p1.e, new=p2.e)
                if not math.isclose(p1.m, p2.m, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_m"] = LHEDiff(old=p1.m, new=p2.m)
                if not math.isclose(
                    p1.lifetime, p2.lifetime, abs_tol=abs_tol, rel_tol=rel_tol
                ):
                    diffs[f"event_{j}_particle_{i}_lifetime"] = LHEDiff(
                        old=p1.lifetime, new=p2.lifetime
                    )
                if not math.isclose(p1.spin, p2.spin, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_spin"] = LHEDiff(
                        old=p1.spin, new=p2.spin
                    )

        if diffs:
            yield LHEEventDiff(event_index=j, diffs=diffs)


@dataclass
class LHEFileDiff:
    """Dataclass to store differences between two LHE files."""

    lheinitdiff: LHEInitDiff
    lheeventdiffs: Iterable[LHEEventDiff]

    def print(self, *args: Any, **kwargs: Any) -> LHEAccumulatedDiff:
        ret = LHEAccumulatedDiff(ndiff=0)
        ret += self.lheinitdiff.print(*args, **kwargs)
        for event_diff in self.lheeventdiffs:
            ret += event_diff.print(*args, **kwargs)
        return ret


def diff_lhe_files(
    file1: str,
    file2: str,
    init: bool = True,
    weights: bool = True,
    events: bool = True,
    abs_tol: float = 0.0,
    rel_tol: float = 0.0,
) -> LHEFileDiff:
    """
    Compare two LHE files and report differences.

    Args:
        file1: Path to first LHE file
        file2: Path to second LHE file
        abs_tol: Absolute tolerance for numeric comparisons
        rel_tol: Relative tolerance for numeric comparisons
    """
    # Read initialization sections
    lhefile1 = pylhe.LHEFile.fromfile(file1)
    lhefile2 = pylhe.LHEFile.fromfile(file2)

    lheinitdiff = diff_lhe_init(
        lhefile1.init,
        lhefile2.init,
        lhefile1.header,
        lhefile2.header,
        lhefile1.version,
        lhefile2.version,
        init,
        weights,
        abs_tol,
        rel_tol,
    )
    lheeventdiff = diff_lhe_events(
        lhefile1.events, lhefile2.events, events, abs_tol, rel_tol
    )

    return LHEFileDiff(lheinitdiff, lheeventdiff)


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Compare and diff two LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhediff file1.lhe file2.lhe                                 # Basic comparison (init + event counts)
  lhediff file1.lhe file2.lhe --abs-tol 1e-10                 # Allow small absolute differences
  lhediff file1.lhe file2.lhe --rel-tol 1e-6 --abs-tol 1e-12  # Use both relative and absolute tolerance
  lhediff original.lhe merged.lhe --rel-tol 1e-10             # Check merge with numeric tolerance
        """,
    )

    parser.add_argument("file1", help="First LHE file to compare")

    parser.add_argument("file2", help="Second LHE file to compare")

    parser.add_argument(
        "--abs",
        "-a",
        type=float,
        default=1e-6,
        help="Absolute tolerance for numeric comparisons (default: 1e-6)",
    )

    parser.add_argument(
        "--rel",
        "-r",
        type=float,
        default=1e-6,
        help="Relative tolerance for numeric comparisons (default: 1e-6)",
    )

    parser.add_argument(
        "--init",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Don't compare initialization sections (default: True)",
    )

    parser.add_argument(
        "--events",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Don't compare events (default: True)",
    )

    parser.add_argument(
        "--weights",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Don't compare weight groups and weights in detail (default: True)",
    )

    args = parser.parse_args()

    # Validate arguments
    for file_path in [args.file1, args.file2]:
        path = Path(file_path)
        if not path.exists():
            print(f"Error: File '{file_path}' does not exist", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(f"Error: '{file_path}' is not a file", file=sys.stderr)
            sys.exit(1)

    # Compare the files
    lhefilediff = diff_lhe_files(
        args.file1,
        args.file2,
        init=args.init,
        weights=args.weights,
        events=args.events,
        abs_tol=args.abs,
        rel_tol=args.rel,
    )

    lhead = lhefilediff.print()

    if lhead.ndiff != 0:
        print("=" * 60)
        lhead.print()

    # We terminate based on printed string being empty, since that means no differences and events can only be looped once
    sys.exit(0 if lhead.ndiff == 0 else 1)


if __name__ == "__main__":
    main()
