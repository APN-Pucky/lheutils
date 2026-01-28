#!/usr/bin/env python3
"""
Convert HepMC files to LHE format.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO, Union

import pyhepmc  # type: ignore[import-untyped]
import pylhe

from lheutils.cli.util import create_base_parser


def convert_hepmc_to_lhe(
    input_file: Union[str, TextIO],
    output_file: Union[str, TextIO, None] = None,
    format: str = "HepMC3",
) -> None:
    """Convert HepMC file to LHE format.

    Args:
        input_file: Path to the input HepMC file or file object (stdin)
        output_file: Path to the output LHE file or file object (stdout), None for stdout
    """
    try:
        # Determine display name for error messages
        input_display_name = input_file if isinstance(input_file, str) else "<stdin>"

        # TODO setup LHEInit from hepmc file
        init = pylhe.LHEInit(
            initInfo=pylhe.LHEInitInfo(
                beamA=-1,
                beamB=-1,
                energyA=0.0,
                energyB=0.0,
                PDFgroupA=0,
                PDFgroupB=0,
                PDFsetA=0,
                PDFsetB=0,
                weightingStrategy=1,
                numProcesses=1,
            ),
            procInfo=[],
            weightgroup={},
            LHEVersion="3.0",
        )

        def _generator() -> Iterable[pylhe.LHEEvent]:
            with pyhepmc.open(input_file, format=format) as f:
                for event in f:
                    particles = []
                    for p in event.particles:
                        particles.append(
                            pylhe.LHEParticle(
                                id=p.pid,
                                status=p.status,
                                mother1=p.mother1,
                                mother2=p.mother2,
                                color1=p.color[0],
                                color2=p.color[1],
                                px=p.momentum.x,
                                py=p.momentum.y,
                                pz=p.momentum.z,
                                e=p.momentum.t,
                                m=p.mass,
                                lifetime=p.lifetime,
                                spin=p.spin,
                            )
                        )
                    yield pylhe.LHEEvent(
                        eventinfo=pylhe.LHEEventInfo(
                            nparticles=len(particles),
                            pid=event.event_number,
                            weight=event.weight,
                            scale=event.scale,
                            aqed=event.alpha_qed,
                            aqcd=event.alpha_qcd,
                        ),
                        particles=particles,
                    )

        lhefile = pylhe.LHEFile(init=init, events=_generator())
        # Write output LHE file
        # if output_file is a string
        if isinstance(output_file, str):
            lhefile.tofile(output_file)
        else:
            lhefile.write(sys.stdout)
    except FileNotFoundError:
        print(f"Error: Input file '{input_display_name}' not found", file=sys.stderr)
        sys.exit(1)
    # except Exception as e:
    #    print(f"Error converting {input_display_name}: {e}", file=sys.stderr)
    #    sys.exit(1)


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
