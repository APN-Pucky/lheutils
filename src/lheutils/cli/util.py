import argparse
from typing import Any, Literal

import pylhe

import lheutils

WEIGHT_FORMAT_CHOICES = tuple(
    weight_format.value for weight_format in pylhe.LHEWeightFormat
)
FILE_FORMAT_CHOICES = ("xml", "hdf5")
LHEFileFormatName = Literal["xml", "hdf5"]


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


def add_file_format_argument(
    parser: argparse.ArgumentParser,
    *flags: str,
    help_text: str = "File format to use in output (default: xml)",
) -> None:
    """Add the shared file-format CLI argument."""
    parser.add_argument(
        *(flags or ("--file-format",)),
        choices=FILE_FORMAT_CHOICES,
        default="xml",
        help=help_text,
    )


def parse_file_format(
    file_format: str,
) -> LHEFileFormatName:
    """Normalize a CLI file-format value to the supported names."""
    if file_format not in FILE_FORMAT_CHOICES:
        err = f"Unsupported file format: {file_format}"
        raise ValueError(err)
    return file_format


def create_output_format(
    weight_format: pylhe.LHEWeightFormat,
    file_format: LHEFileFormatName = "xml",
    compress: bool | None = None,
) -> pylhe.LHEOutputFormat:
    """Build a pylhe output-format object for writers."""
    if file_format == "hdf5":
        return pylhe.LHEHDF5Format(compress=compress is True)
    return pylhe.LHEXMLFormat(
        weights=weight_format,
        compress=compress is True,
    )
