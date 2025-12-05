import argparse
import inspect
from dataclasses import fields, is_dataclass
from typing import Any, Union

import pylhe

import lheutils

def create_base_parser(**kwargs):
    """Create a base argument parser with common options."""
    parser = argparse.ArgumentParser(**kwargs)
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + lheutils.__version__ + " using pylhe " + pylhe.__version__,
    )
    return parser
