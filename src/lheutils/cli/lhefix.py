#!/usr/bin/env python3
"""
CLI tool to fix broken LHE files.

This tool can read from stdin or fix multiple files in place by iterating through
them as a generator until completion or exception.
"""

import argparse
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pylhe

from lheutils.cli.util import create_base_parser


def fix_file_inplace(
    filepath: str, compress: bool = False, suffix: Optional[str] = None
) -> None:
    """Fix an LHE file in place using temporary file for safety.

    Args:
        filepath: Path to the LHE file to fix.
        compress: Whether to gzip-compress the output file.
        suffix: Suffix to add to the output filename (None means replace original).
    """
    try:
        # Read the original file
        lhefile = pylhe.LHEFile.fromfile(filepath)

        # Determine output filename
        filepath_obj = Path(filepath)
        if suffix is None:
            # Replace original file
            output_path = filepath
        else:
            # Create new filename with prefix/suffix
            new_name = f"{filepath_obj.stem}{suffix}"
            output_path = str(filepath_obj.parent / new_name)

        # Create temporary file in same directory as original
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".tmp", prefix=filepath_obj.stem + "_", dir=filepath_obj.parent
        )

        try:
            # Close the file descriptor since pylhe will open its own
            os.close(temp_fd)

            # Filter events and write to temporary file
            def _generator() -> Iterable[pylhe.LHEEvent]:
                event_count = 0
                try:
                    for event in lhefile.events:
                        event_count += 1
                        yield event
                except Exception as e:
                    print(
                        f"{filepath} terminating LHE file at event {event_count} due to: {e}"
                    )
                    return
                finally:
                    print(
                        f"{filepath} fixed: processed {event_count} events -> {output_path}"
                    )

            # Write to temporary file
            pylhe.LHEFile(init=lhefile.init, events=_generator()).tofile(
                temp_path, gz=compress
            )

            # Atomically replace/create output file with temporary file
            os.replace(temp_path, output_path)

        except Exception as e:
            # Clean up temporary file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    except Exception as e:
        print(f"Error fixing {filepath}: {e}", file=sys.stderr)


def fix_from_stdin() -> None:
    """Fix LHE content from stdin and output to stdout."""
    try:
        lhefile = pylhe.LHEFile.frombuffer(sys.stdin)

        # Create generator that handles exceptions gracefully
        def _generator() -> Iterable[pylhe.LHEEvent]:
            try:
                yield from lhefile.events
            except Exception:
                # Terminate silently on exception for chaining compatibility
                return

        # Write fixed LHE to stdout
        pylhe.LHEFile(init=lhefile.init, events=_generator()).write(sys.stdout)

    except Exception as e:
        print(f"Error processing stdin: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for lhefix CLI."""
    parser = create_base_parser(
        prog="lhefix",
        description="Fix broken LHE files. Reads from stdin by default or fixes multiple files in place.",
    )

    parser.add_argument(
        "--suffix",
        default=".fix.lhe.gz",
        help="Suffix to add to use for filenames (default: '.fix.lhe.gz').",
    )

    parser.add_argument(
        "--compress",
        "-c",
        action=argparse.BooleanOptionalAction,
        help="Compress output (if fixing in place, original files will be replaced with compressed versions).",
        default=False,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE files to fix in place. If no files provided, reads from stdin.",
    )

    args = parser.parse_args()

    if not args.files:
        # No files provided, read from stdin
        fix_from_stdin()
    else:
        # Fix multiple files in place
        for filepath in args.files:
            if not Path(filepath).exists():
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                continue
            fix_file_inplace(filepath, args.compress, args.suffix)


if __name__ == "__main__":
    main()
