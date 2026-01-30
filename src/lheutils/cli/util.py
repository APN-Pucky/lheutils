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


def get_max_weight_index(init: pylhe.LHEInit) -> int:
    """Get the maximum weight index from the init section."""
    max_index = 0
    for wg in init.weightgroup.values():
        for w in wg.weights.values():
            max_index = max(max_index, w.index)
    return max_index
