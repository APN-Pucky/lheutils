#!/usr/bin/env python3
"""
Convert HepMC files to LHE format.
"""

import argparse
import signal
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

import pyhepmc  # type: ignore[import-untyped]
import pylhe

from lheutils.cli.util import create_base_parser

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def _attribute_text(event: Any, name: str) -> str | None:
    """Return a HepMC attribute as text without mutating pyhepmc's lazy parser."""
    if name not in event.attributes:
        return None
    return str(event.attributes[name])


def _attribute_int(event: Any, name: str, default: int) -> int:
    text = _attribute_text(event, name)
    if text is None:
        return default
    try:
        return int(float(text.split()[0]))
    except (IndexError, ValueError):
        return default


def _attribute_float(event: Any, name: str, default: float) -> float:
    text = _attribute_text(event, name)
    if text is None:
        return default
    try:
        return float(text.split()[0])
    except (IndexError, ValueError):
        return default


def _momentum_components(particle: Any) -> tuple[float, float, float, float]:
    momentum = particle.momentum
    if all(hasattr(momentum, attr) for attr in ("px", "py", "pz", "e")):
        return (
            float(momentum.px),
            float(momentum.py),
            float(momentum.pz),
            float(momentum.e),
        )
    return (
        float(momentum[0]),
        float(momentum[1]),
        float(momentum[2]),
        float(momentum[3]),
    )


def _generated_mass(particle: Any) -> float:
    if hasattr(particle, "generated_mass"):
        return float(particle.generated_mass)

    momentum = particle.momentum
    return float(momentum.m()) if hasattr(momentum, "m") else 0.0


def _pdf_info(event: Any) -> Any | None:
    try:
        return event.pdf_info
    except (AttributeError, RuntimeError):
        return None


def _event_scale(event: Any) -> float:
    pdf_info = _pdf_info(event)
    if pdf_info is not None:
        return float(pdf_info.scale)

    text = _attribute_text(event, "GenPdfInfo")
    if text is None:
        return 0.0

    values = text.split()
    try:
        return float(values[4]) if len(values) > 4 else 0.0
    except ValueError:
        return 0.0


def _event_weight(event: Any) -> float:
    weights = list(event.weights)
    if weights:
        return float(weights[0])

    try:
        return float(event.weight())
    except (IndexError, RuntimeError):
        return 1.0


def _mother_pair(particle: Any, particle_indices: dict[int, int]) -> tuple[int, int]:
    production_vertex = particle.production_vertex
    if production_vertex is None:
        return 0, 0

    mothers = sorted(
        particle_indices[parent.id]
        for parent in production_vertex.particles_in
        if parent.id in particle_indices
    )
    if not mothers:
        return 0, 0
    if len(mothers) == 1:
        return mothers[0], mothers[0]
    return mothers[0], mothers[-1]


def _parent_ids(particle: Any) -> set[int]:
    production_vertex = particle.production_vertex
    if production_vertex is None:
        return set()
    return {parent.id for parent in production_vertex.particles_in}


def _ordered_particles(event: Any) -> list[Any]:
    particles = list(event.particles)
    event_order = {particle.id: index for index, particle in enumerate(particles)}
    ordered: list[Any] = []
    seen: set[int] = set()
    expanded: set[int] = set()

    def append(particle: Any) -> None:
        if particle.id not in seen:
            ordered.append(particle)
            seen.add(particle.id)

    def expand(particle: Any) -> None:
        if particle.id in expanded:
            return
        expanded.add(particle.id)

        end_vertex = particle.end_vertex
        if end_vertex is None:
            return

        children = sorted(
            end_vertex.particles_out, key=lambda child: event_order.get(child.id, -1)
        )
        for child in children:
            if not _parent_ids(child).issubset(seen):
                continue
            append(child)
            expand(child)

    roots = [particle for particle in particles if not _parent_ids(particle)]
    for particle in roots:
        append(particle)
    for particle in roots:
        expand(particle)
    for particle in particles:
        append(particle)
        expand(particle)

    return ordered


def _lhe_status(particle: Any) -> int:
    if int(particle.status) == 4:
        return -1
    return int(particle.status)


def _lhe_particle(particle: Any, particle_indices: dict[int, int]) -> pylhe.LHEParticle:
    mother1, mother2 = _mother_pair(particle, particle_indices)
    px, py, pz, energy = _momentum_components(particle)

    return pylhe.LHEParticle(
        id=int(particle.pid),
        status=_lhe_status(particle),
        mother1=mother1,
        mother2=mother2,
        color1=0,
        color2=0,
        px=px,
        py=py,
        pz=pz,
        e=energy,
        m=_generated_mass(particle),
        lifetime=0.0,
        spin=9.0,
    )


def _lhe_event(event: Any) -> pylhe.LHEEvent:
    ordered_particles = _ordered_particles(event)
    particle_indices = {
        particle.id: index for index, particle in enumerate(ordered_particles, start=1)
    }
    particles = [
        _lhe_particle(particle, particle_indices) for particle in ordered_particles
    ]

    return pylhe.LHEEvent(
        eventinfo=pylhe.LHEEventInfo(
            nparticles=len(particles),
            pid=_attribute_int(event, "IDPRUP", 1),
            weight=_event_weight(event),
            scale=_event_scale(event),
            aqed=_attribute_float(
                event, "AlphaEM", _attribute_float(event, "AlphaQED", -1.0)
            ),
            aqcd=_attribute_float(event, "AlphaQCD", -1.0),
        ),
        particles=particles,
    )


def _beam_particles(event: Any | None) -> list[Any]:
    if event is None:
        return []

    try:
        beams = list(event.beams)
    except RuntimeError:
        beams = []
    if beams:
        return beams
    return list(event.particles)[:2]


def _lhe_init(event: Any | None) -> pylhe.LHEInit:
    beams = _beam_particles(event)
    beam_a = beams[0] if len(beams) > 0 else None
    beam_b = beams[1] if len(beams) > 1 else None
    energy_a = _momentum_components(beam_a)[3] if beam_a is not None else 0.0
    energy_b = _momentum_components(beam_b)[3] if beam_b is not None else 0.0

    pdf_info = _pdf_info(event) if event is not None else None
    pdf_id1 = int(pdf_info.pdf_id1) if pdf_info is not None else 0
    pdf_id2 = int(pdf_info.pdf_id2) if pdf_info is not None else 0
    pid = _attribute_int(event, "IDPRUP", 1) if event is not None else 1

    return pylhe.LHEInit(
        initInfo=pylhe.LHEInitInfo(
            beamA=int(beam_a.pid) if beam_a is not None else 0,
            beamB=int(beam_b.pid) if beam_b is not None else 0,
            energyA=energy_a,
            energyB=energy_b,
            PDFgroupA=0,
            PDFgroupB=0,
            PDFsetA=pdf_id1,
            PDFsetB=pdf_id2,
            weightingStrategy=1,
            numProcesses=1,
        ),
        procInfo=[
            pylhe.LHEProcInfo(
                xSection=0.0,
                error=0.0,
                unitWeight=max(abs(_event_weight(event)), 1.0)
                if event is not None
                else 1.0,
                procId=pid,
            )
        ],
        generators=[],
    )


def convert_hepmc_to_lhe(
    input_file: str | TextIO,
    output_file: str | TextIO | None = None,
    format: str = "HepMC3",
) -> None:
    """Convert HepMC file to LHE format.

    Args:
        input_file: Path to the input HepMC file or file object (stdin)
        output_file: Path to the output LHE file or file object (stdout), None for stdout
        format: HepMC input format string (for example, "HepMC3")
    """
    try:
        # Determine display name for error messages
        input_display_name = input_file if isinstance(input_file, str) else "<stdin>"

        with pyhepmc.open(input_file or sys.stdin, format=format) as f:
            first_event = f.read()

            def _generator() -> Iterable[pylhe.LHEEvent]:
                if first_event is not None:
                    yield _lhe_event(first_event)
                for event in f:
                    yield _lhe_event(event)

            lhefile = pylhe.LHEFile(init=_lhe_init(first_event), events=_generator())

            if isinstance(output_file, str):
                lhefile.tofile(output_file)
            else:
                lhefile.write(output_file or sys.stdout)
    except FileNotFoundError:
        print(f"Error: Input file '{input_display_name}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error converting {input_display_name}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Convert HepMC files to LHE format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hepmc2lhe --input events.hepmc --output events.lhe    # Convert HepMC to LHE
  hepmc2lhe --input events.hepmc                        # Convert to stdout
  hepmc2lhe --output events.lhe                         # Convert from stdin
  cat events.hepmc | hepmc2lhe                          # Convert stdin to stdout
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Input HepMC file (read from stdin if not provided)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output LHE file (write to stdout if not provided)",
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
    convert_hepmc_to_lhe(input_source, output_destination, format=args.format)


if __name__ == "__main__":
    main()
