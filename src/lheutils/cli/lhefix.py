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
from copy import deepcopy
from pathlib import Path

import pylhe

from lheutils.cli.util import (
    add_weight_format_argument,
    create_base_parser,
    create_output_format,
    parse_weight_format,
)


def fix_file(
    filepath: str | None = None,
    compress: bool = False,
    suffix: str | None = None,
    weight_format: pylhe.LHEWeightFormat = pylhe.LHEWeightFormat.RWGT,
) -> None:
    """Fix an LHE file from filepath or stdin.

    Args:
        filepath: Path to the LHE file to fix, or None to read from stdin.
        compress: Whether to gzip-compress the output file (ignored for stdin).
        suffix: Suffix to add to the output filename (ignored for stdin).
        weight_format: How to serialize event weights in output
    """
    try:
        # Read the input
        if filepath is None:
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
        else:
            lhefile = pylhe.LHEFile.fromfile(filepath)

        # Determine output path for file mode
        output_path = ""
        if filepath is not None:
            filepath_obj = Path(filepath)
            if suffix is None:
                output_path = filepath
                suffix = filepath_obj.suffix
            else:
                output_path = str(filepath_obj.parent / f"{filepath_obj.stem}{suffix}")

        # Create unified event generator with error handling
        def _generator() -> Iterable[pylhe.LHEEvent]:
            event_count = 0
            try:
                for event in lhefile.events:
                    event_count += 1
                    # This is where per-event fixes could be applied in the future
                    yield event
            except Exception as e:
                if filepath is not None:
                    print(
                        f"{filepath} terminating LHE file at event {event_count} due to: {e}"
                    )
                # For stdin, terminate silently for chaining compatibility
                return
            finally:
                if filepath is not None:
                    print(
                        f"{filepath} fixed: processed {event_count} events -> {output_path}"
                    )

        fixed_lhefile = pylhe.LHEFile(
            init=lhefile.init,
            events=_generator(),
            header=deepcopy(lhefile.header),
            comment=lhefile.comment,
            version=lhefile.version,
            extra_attributes=lhefile.extra_attributes.copy(),
        )

        # Handle output
        if filepath is None:
            # Write to stdout
            fixed_lhefile.write(
                sys.stdout,
                lheformat=create_output_format(weight_format),
            )
        else:
            # Write to file with atomic replacement
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp" + (suffix if suffix is not None else ""),
                prefix=filepath_obj.stem + "_",
                dir=filepath_obj.parent,
            )

            try:
                # Close the file descriptor since pylhe will open its own
                os.close(temp_fd)
                # Get original file permissions if replacing the file
                original_stat = os.stat(filepath)
                # Set temporary file permissions to match original
                os.chmod(temp_path, original_stat.st_mode)

                # Write to temporary file
                fixed_lhefile.tofile(
                    temp_path,
                    lheformat=create_output_format(weight_format, compress=compress),
                )

                # Atomically replace/create output file with temporary file
                os.replace(temp_path, output_path)

            except Exception as e:
                # Clean up temporary file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

    except Exception as e:
        if filepath is None:
            print(f"Error processing stdin: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Error fixing {filepath}: {e}", file=sys.stderr)


def main() -> None:
    """Main entry point for lhefix CLI."""
    parser = create_base_parser(
        prog="lhefix",
        description="Fix broken LHE files. Reads from stdin by default or fixes multiple files in place. "
        "For parallel processing, use GNU parallel: 'parallel -j 8 lhefix ::: *.lhe'.",
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
        help="Compress output files.",
        default=False,
    )

    add_weight_format_argument(
        parser,
        help_text="Weight format to use in output files (default: rwgt).",
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE files to fix in place. If no files provided, reads from stdin.",
    )

    args = parser.parse_args()

    weight_format = parse_weight_format(args.weight_format)

    if not args.files:
        # No files provided, read from stdin
        fix_file(None, args.compress, args.suffix, weight_format)
    else:
        # Fix multiple files in place
        for filepath in args.files:
            if not Path(filepath).exists():
                print(f"Error: File not found: {filepath}", file=sys.stderr)
                continue
            fix_file(filepath, args.compress, args.suffix, weight_format)


if __name__ == "__main__":
    main()
