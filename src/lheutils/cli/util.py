import argparse
from typing import Any

import pylhe

import lheutils


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
