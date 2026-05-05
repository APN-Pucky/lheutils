#!/usr/bin/env python3
"""
CLI tool to validate LHE files against XSD schema.
"""

import argparse
import gzip
import io
import re
import sys
import warnings
from io import StringIO
from pathlib import Path
from typing import TextIO, Union

import pylhe
from lxml import etree

from lheutils.cli.util import create_base_parser

XSD_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}


def _is_gzipped(filepath: Union[str, Path]) -> bool:
    """Check if a file is gzip compressed by reading its magic number.

    Args:
        filepath: Path to the file to check

    Returns:
        True if file is gzip compressed, False otherwise
    """
    try:
        with open(filepath, "rb") as f:
            header = f.read(2)
        return header == b"\x1f\x8b"  # gzip magic number
    except OSError:
        return False


def _open_file(filepath: Union[str, Path]) -> io.TextIOWrapper:
    """Open a file, automatically handling gzip compression.

    Args:
        filepath: Path to the file to open

    Returns:
        Text file object
    """
    if _is_gzipped(filepath):
        return gzip.open(filepath, "rt", encoding="utf-8")
    return open(filepath, encoding="utf-8")


def validate_lhe_file(
    file_input: Union[str, TextIO],
    schema_path: str,
    enable_xsd: bool = True,
    enable_pylhe: bool = True,
) -> bool:
    """Validate an LHE file against the XSD schema and/or pylhe parsing.

    Args:
        file_input: File path or file object to validate
        schema_path: Path to the XSD schema file
        enable_xsd: Whether to perform XSD validation
        enable_pylhe: Whether to perform pylhe parsing validation

    Returns:
        True if valid, False otherwise
    """
    try:
        # Handle different input types
        if isinstance(file_input, str):
            # File path - we can read multiple times
            return _validate_file_path(
                file_input, schema_path, enable_xsd, enable_pylhe
            )
        # stdin/file object - read once and validate buffer
        content = file_input.read()
        return _validate_buffer(content, schema_path, enable_xsd, enable_pylhe)

    except Exception as e:
        print(f"  ❌ Error processing file: {e}", file=sys.stderr)
        return False


def _validate_file_path(
    file_path: str, schema_path: str, enable_xsd: bool, enable_pylhe: bool
) -> bool:
    """Validate a file by path."""
    if enable_xsd:
        print("  Checking XSD schema compliance...")
        xsd, schema_doc = _load_schema_resources(schema_path)

        # Handle both compressed and uncompressed files by magic number
        with _open_file(file_path) as f:
            xml_payload = _extract_xml_payload(f.read())
        xml = etree.parse(StringIO(xml_payload))

        if not xsd.validate(xml):
            print("  ❌ XSD validation failed!")
            print(xsd.error_log)
            return False
        print("  ✓ XSD validation passed")

        if not _validate_mixed_block_text(xml, schema_doc):
            return False

    if enable_pylhe:
        print("  Checking LHE format and structure...")
        lhefile = pylhe.LHEFile.fromfile(file_path)
        return _validate_lhe_structure(lhefile)

    return True


def _validate_buffer(
    content: str, schema_path: str, enable_xsd: bool, enable_pylhe: bool
) -> bool:
    """Validate content from buffer/stdin."""
    if enable_xsd:
        print("  Checking XSD schema compliance...")
        xsd, schema_doc = _load_schema_resources(schema_path)

        xml = etree.parse(StringIO(_extract_xml_payload(content)))

        if not xsd.validate(xml):
            print("  ❌ XSD validation failed!")
            print(xsd.error_log)
            return False
        print("  ✓ XSD validation passed")

        if not _validate_mixed_block_text(xml, schema_doc):
            return False

    if enable_pylhe:
        print("  Checking LHE format and structure...")
        lhefile = pylhe.LHEFile.frombuffer(StringIO(content))
        return _validate_lhe_structure(lhefile)

    return True


def _load_schema_resources(
    schema_path: str,
) -> tuple[etree.XMLSchema, etree._ElementTree]:
    """Load the schema and its XML document."""
    with open(schema_path) as schema_file:
        schema_doc = etree.parse(schema_file)
    return etree.XMLSchema(schema_doc), schema_doc


def _get_text_pattern(
    schema_doc: etree._ElementTree, type_name: str
) -> re.Pattern[str]:
    """Extract a named supplemental text pattern from the schema."""
    matches = schema_doc.xpath(
        "/xs:schema/xs:simpleType[@name=$type_name]/xs:restriction/xs:pattern/@value",
        namespaces=XSD_NS,
        type_name=type_name,
    )
    if len(matches) != 1:
        err = f"Expected exactly one pattern for schema type {type_name!r}"
        raise ValueError(err)
    return re.compile(matches[0])


def _normalize_block_text(text: str) -> str:
    """Normalize line endings before regex validation."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_xml_payload(content: str) -> str:
    """Trim non-XML footer text that may follow the closing root tag.

    Some LHE files, notably POWHEG samples, append plain-text footer lines
    after ``</LesHouchesEvents>``. Those lines are not part of the XML
    document, so we exclude them before XSD parsing.
    """
    closing_tag = "</LesHouchesEvents>"
    end_index = content.rfind(closing_tag)
    if end_index == -1:
        return content
    return content[: end_index + len(closing_tag)]


def _validate_mixed_block_text(
    xml: etree._ElementTree, schema_doc: etree._ElementTree
) -> bool:
    """Apply supplemental regex checks to the leading text in init/event blocks."""
    print("  Checking init/event text patterns...")

    patterns = {
        "init": _get_text_pattern(schema_doc, "InitTextType"),
        "event": _get_text_pattern(schema_doc, "EventTextType"),
    }

    for tag_name, pattern in patterns.items():
        for element in xml.getroot().iter(tag_name):
            text = _normalize_block_text(element.text or "")
            if pattern.fullmatch(text) is None:
                line_info = (
                    f" at line {element.sourceline}"
                    if element.sourceline is not None
                    else ""
                )
                print(f"  ❌ {tag_name} text validation failed{line_info}!")
                return False

    print("  ✓ init/event text patterns passed")
    return True


def _validate_lhe_structure(lhefile: pylhe.LHEFile) -> bool:
    """Validate LHE file structure using pylhe."""
    # Iterate through events to validate structure
    event_count = 0
    try:
        for event_index, event in enumerate(lhefile.events, start=1):
            event_count += 1
            # Basic event validation - check if particles exist
            if not event.particles:
                print(f"  ❌ Event {event_index} has no particles")
                return False

            # Check if we can access basic particle properties
            for particle in event.particles:
                _ = (
                    particle.id,
                    particle.status,
                    particle.px,
                    particle.py,
                    particle.pz,
                    particle.e,
                )

        print(f"  ✓ Successfully parsed {event_count} events")
        return True

    except Exception as e:
        print(f"  ❌ Error parsing events: {e}")
        return False


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Validate LHE files against XSD schema and/or LHE format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhevalidate file.lhe                     # Validate with both XSD and pylhe (default)
  lhevalidate --no-pylhe file.lhe          # XSD validation only (faster)
  lhevalidate --no-xsd file.lhe            # pylhe parsing validation only
  lhevalidate file1.lhe file2.lhe          # Validate multiple files
  cat file.lhe | lhevalidate               # Read from stdin

Validation levels:
  1. XSD schema validation - checks XML structure and format compliance
  2. LHE format validation - uses pylhe to parse init/event blocks
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE file(s) to validate (or read from stdin if not provided)",
    )

    parser.add_argument(
        "--no-xsd",
        action="store_true",
        help="Skip XSD schema validation (only perform pylhe parsing validation)",
    )

    parser.add_argument(
        "--no-pylhe",
        action="store_true",
        help="Skip pylhe parsing validation (only perform XSD schema validation)",
    )

    args = parser.parse_args()

    # Validate options
    if args.no_xsd and args.no_pylhe:
        print("Error: Cannot disable both XSD and pylhe validation", file=sys.stderr)
        sys.exit(1)

    enable_xsd = not args.no_xsd
    enable_pylhe = not args.no_pylhe

    # Find schema file
    schema_path = Path(__file__).parent.parent / "schema" / "lhe.xsd"
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[Union[str, TextIO]] = []
    if use_stdin:
        # Read from stdin
        file_inputs.append(sys.stdin)
    else:
        # Expand file paths
        for pattern in args.files:
            path = Path(pattern)
            if path.exists():
                if path.is_file():
                    file_inputs.append(str(path))
                else:
                    warnings.warn(f"{pattern} is not a file", UserWarning, stacklevel=2)
            else:
                warnings.warn(f"{pattern} not found", UserWarning, stacklevel=2)

        if not file_inputs:
            print("Error: No valid files found and no stdin data", file=sys.stderr)
            sys.exit(1)

    # Validate all files
    all_valid = True
    for file_input in file_inputs:
        if isinstance(file_input, str):
            print(f"Validating {file_input}:")
        else:
            print("Validating stdin input:")

        valid = validate_lhe_file(
            file_input, str(schema_path), enable_xsd, enable_pylhe
        )
        if valid:
            print("✓ File is valid!")
        else:
            print("❌ File validation failed!")
        print()  # Add blank line between files

        all_valid = all_valid and valid

    # Exit with appropriate code
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
