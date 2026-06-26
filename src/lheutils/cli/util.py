import argparse
from pathlib import Path
from typing import Any, Literal

import pylhe
from particle import Particle

import lheutils

try:
    import lhapdf  # type: ignore[import-not-found]

    LHAPDF_BASE_PATHS = lhapdf.paths()
except ImportError:
    LHAPDF_BASE_PATHS = [
        "/usr/share/lhapdf",
        "/usr/local/share/lhapdf",
        "/opt/local/share/lhapdf",
        "/opt/share/lhapdf",
        str(Path.home() / ".local/share/lhapdf"),
        str(Path.home() / ".lhapdf"),
    ]

WEIGHT_FORMAT_CHOICES = tuple(
    weight_format.value for weight_format in pylhe.LHEWeightFormat
)
OUTPUT_FORMAT_CHOICES = (
    "default",
    "gz",
    "rwgt",
    "weights",
    "rwgt-gz",
    "weights-gz",
    "no-weights",
    "hdf5",
    "hdf5-gz",
)
LHEOutputFormatName = Literal[
    "default",
    "gz",
    "rwgt",
    "weights",
    "rwgt-gz",
    "weights-gz",
    "no-weights",
    "hdf5",
    "hdf5-gz",
]
OUTPUT_FORMAT_PRESETS: dict[LHEOutputFormatName, pylhe.LHEOutputFormat] = {
    "default": pylhe.DEFAULT_FORMAT,
    "gz": pylhe.GZ_FORMAT,
    "rwgt": pylhe.RWGT_FORMAT,
    "weights": pylhe.WEIGHTS_FORMAT,
    "rwgt-gz": pylhe.RWGT_GZ_FORMAT,
    "weights-gz": pylhe.WEIGHTS_GZ_FORMAT,
    "no-weights": pylhe.NO_WEIGHTS_FORMAT,
    "hdf5": pylhe.HDF5_FORMAT,
    "hdf5-gz": pylhe.HDF5_GZ_FORMAT,
}


def lhapdf_name(pdf_id: int) -> str:

    for base in LHAPDF_BASE_PATHS:
        index = Path(base) / "pdfsets.index"
        if not index.exists():
            continue

        with index.open() as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                first_id_str, set_name, nmem_str = line.split()[:3]
                first_id = int(first_id_str)
                nmem = int(nmem_str)

                if first_id <= pdf_id < first_id + nmem:
                    return set_name

    return str(pdf_id)


def lhapdf_name_and_id(pdf_id: int) -> str:
    name = lhapdf_name(pdf_id)
    return f"{name} ({pdf_id})" if name != str(pdf_id) else f"({pdf_id})"


def pdg_name(pdgid: int) -> str:
    try:
        return str(Particle.from_pdgid(pdgid).name)
    except LookupError:
        return str(pdgid)


def pdg_name_and_id(pdgid: int) -> str:
    name = pdg_name(pdgid)
    return f"{name} ({pdgid})" if name != str(pdgid) else f"({pdgid})"


def create_base_parser(**kwargs: Any) -> argparse.ArgumentParser:
    """Create a base argument parser with common options."""
    parser = argparse.ArgumentParser(**kwargs)
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s "
        + lheutils.__version__
        + " using pylhe "
        + pylhe.__version__,
    )
    return parser


def add_weight_format_argument(
    parser: argparse.ArgumentParser,
    *flags: str,
    help_text: str = "Weight format to use in output (default: rwgt)",
) -> None:
    """Add the shared weight-format CLI argument."""
    parser.add_argument(
        *(flags or ("--weight-format",)),
        choices=WEIGHT_FORMAT_CHOICES,
        default=pylhe.LHEWeightFormat.RWGT.value,
        help=help_text,
    )


def parse_weight_format(
    weight_format: str | pylhe.LHEWeightFormat,
) -> pylhe.LHEWeightFormat:
    """Normalize a CLI weight-format value to the pylhe enum."""
    if isinstance(weight_format, pylhe.LHEWeightFormat):
        return weight_format
    return pylhe.LHEWeightFormat(weight_format)


def add_output_format_argument(
    parser: argparse.ArgumentParser,
    *flags: str,
    help_text: str = "Output format preset to use (default: default)",
) -> None:
    """Add the shared output-format CLI argument."""
    parser.add_argument(
        *(flags or ("--output-format",)),
        choices=OUTPUT_FORMAT_CHOICES,
        default="default",
        help=help_text,
    )


def parse_output_format(
    output_format: str | pylhe.LHEOutputFormat,
) -> pylhe.LHEOutputFormat:
    """Normalize a CLI output-format value to the corresponding pylhe preset."""
    if isinstance(output_format, (pylhe.LHEXMLFormat, pylhe.LHEHDF5Format)):
        return output_format
    if output_format not in OUTPUT_FORMAT_PRESETS:
        err = f"Unsupported output format: {output_format}"
        raise ValueError(err)
    return OUTPUT_FORMAT_PRESETS[output_format]


def create_output_format(
    weight_format: pylhe.LHEWeightFormat,
    compress: bool = False,
) -> pylhe.LHEXMLFormat:
    """Build an XML pylhe output-format object for writers."""
    return pylhe.LHEXMLFormat(
        weights=weight_format,
        compress=compress,
    )
