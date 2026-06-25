import argparse
from typing import Any

import pylhe

import lheutils

WEIGHT_FORMAT_CHOICES = tuple(
    weight_format.value for weight_format in pylhe.LHEWeightFormat
)


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


def create_output_format(
    weight_format: pylhe.LHEWeightFormat,
    compress: bool = False,
) -> pylhe.LHEOutputFormat:
    """Build a pylhe output-format object for writers."""
    file_format = pylhe.LHEFileFormat.GZIP if compress else pylhe.LHEFileFormat.PLAIN
    return pylhe.LHEOutputFormat(weights=weight_format, file=file_format)
