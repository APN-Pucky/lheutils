#!/usr/bin/env python3
"""
CLI tool to validate LHE and LHEH5 files.
"""

import argparse
import gzip
import io
import re
import sys
import warnings
from functools import cache
from io import StringIO
from pathlib import Path
from typing import TextIO

import h5py
import pylhe
import xmlschema

from lheutils.cli.util import create_base_parser

SCHEMA_FILENAMES = ("lhe-v1.xsd", "lhe-v2.xsd", "lhe-v3.xsd")
SCHEMA_VERSIONS = {
    "lhe-v1.xsd": "1.0",
    "lhe-v2.xsd": "2.0",
    "lhe-v3.xsd": "3.0",
}
LHE_VERSION_RE = re.compile(r"<LesHouchesEvents\b[^>]*\bversion=['\"]([^'\"]+)['\"]")
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
LHEH5_REQUIRED_DATASETS: dict[str, tuple[int | None, ...]] = {
    "version": (3,),
    "init": (10,),
    "procInfo": (None, 6),
    "events": (None, 10),
    "particles": (None, 13),
}
LHEH5_OPTIONAL_DATASETS: dict[str, tuple[int | None, ...]] = {
    "ctevents": (None, 9),
    "ctparticles": (None, 4),
}


def _is_hdf5(filepath: str | Path) -> bool:
    """Check if a file is HDF5 by reading its magic number."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(len(HDF5_SIGNATURE))
        return header == HDF5_SIGNATURE
    except OSError:
        return False


def _is_gzipped(filepath: str | Path) -> bool:
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


def _open_file(filepath: str | Path) -> io.TextIOWrapper:
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
    file_input: str | Path | TextIO,
    schema_path: str,
    enable_xsd: bool = True,
    enable_pylhe: bool = True,
) -> bool:
    """Validate an LHE/LHEH5 file against schema/layout checks and pylhe parsing.

    Args:
        file_input: File path or file object to validate
        schema_path: Path to an XSD schema file or schema directory
        enable_xsd: Whether to perform XSD or LHEH5 layout validation
        enable_pylhe: Whether to perform pylhe parsing validation

    Returns:
        True if valid, False otherwise
    """
    try:
        # Handle different input types
        if isinstance(file_input, (str, Path)):
            # File path - we can read multiple times
            return _validate_file_path(
                str(file_input), schema_path, enable_xsd, enable_pylhe
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
    if _is_hdf5(file_path):
        return _validate_hdf5_file_path(file_path, enable_xsd, enable_pylhe)

    if enable_xsd:
        print("  Checking XSD schema compliance...")
        # Handle both compressed and uncompressed files by magic number
        with _open_file(file_path) as f:
            xml_payload = _extract_xml_payload(f.read())

        if not _validate_xsd_payload(xml_payload, schema_path):
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
        if not _validate_xsd_payload(_extract_xml_payload(content), schema_path):
            return False

    if enable_pylhe:
        print("  Checking LHE format and structure...")
        lhefile = pylhe.LHEFile.frombuffer(StringIO(content))
        return _validate_lhe_structure(lhefile)

    return True


def _validate_hdf5_file_path(
    file_path: str,
    enable_xsd: bool,
    enable_pylhe: bool,
) -> bool:
    """Validate an LHEH5 file by path."""
    if enable_xsd:
        print("  Checking LHEH5 dataset compatibility...")
        if not _validate_lheh5_dataset_compatibility(file_path):
            return False

    if enable_pylhe:
        print("  Checking LHE format and structure...")
        lhefile = pylhe.LHEFile.fromfile(file_path)
        return _validate_lhe_structure(lhefile)

    return True


def _discover_schema_paths(schema_path: str | Path) -> tuple[Path, ...]:
    """Discover the versioned LHE schema files to use for validation."""
    path = Path(schema_path)
    schema_dir = path if path.is_dir() else path.parent
    versioned_paths = tuple(
        candidate
        for candidate in (schema_dir / name for name in SCHEMA_FILENAMES)
        if candidate.exists()
    )
    if versioned_paths:
        return versioned_paths
    if path.exists():
        return (path,)
    msg = f"No schema files found at {path}"
    raise FileNotFoundError(msg)


def _schema_version(schema_path: Path) -> str | None:
    """Return the LHE version associated with a schema filename."""
    return SCHEMA_VERSIONS.get(schema_path.name)


def _extract_lhe_version(xml_payload: str) -> str | None:
    """Extract the LesHouchesEvents version attribute from the XML payload."""
    match = LHE_VERSION_RE.search(xml_payload)
    if match is None:
        return None
    return match.group(1)


def _order_schema_paths(
    schema_paths: tuple[Path, ...], lhe_version: str | None
) -> tuple[Path, ...]:
    """Try the matching schema version first, then the remaining ones."""
    return tuple(
        sorted(
            schema_paths,
            key=lambda path: (_schema_version(path) != lhe_version, path.name),
        )
    )


def _select_failure_to_report(
    failures: list[tuple[Path, list[object]]], lhe_version: str | None
) -> tuple[Path, list[object]]:
    """Pick the most relevant schema failure to report to the user."""
    if lhe_version is not None:
        for schema_path, errors in failures:
            if _schema_version(schema_path) == lhe_version:
                return schema_path, errors
    return min(failures, key=lambda item: len(item[1]))


@cache
def _load_xsd11_schema(schema_path: str) -> xmlschema.XMLSchema11:
    """Load the XSD 1.1 schema."""
    return xmlschema.XMLSchema11(schema_path)


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


def _validate_xsd_payload(
    xml_payload: str,
    schema_path: str,
) -> bool:
    """Validate an XML payload against the available LHE XSD schemas."""
    lhe_version = _extract_lhe_version(xml_payload)
    schema_paths = _order_schema_paths(_discover_schema_paths(schema_path), lhe_version)
    failures: list[tuple[Path, list[object]]] = []

    for candidate in schema_paths:
        schema = _load_xsd11_schema(str(candidate))
        errors = list(schema.iter_errors(xml_payload))
        if not errors:
            print(f"  ✓ XSD validation passed ({candidate.name})")
            return True
        failures.append((candidate, errors))

    print("  ❌ XSD validation failed!")
    reported_schema, reported_errors = _select_failure_to_report(
        failures,
        lhe_version,
    )
    if len(schema_paths) > 1:
        print(f"  Schema: {reported_schema.name}")
    for error in reported_errors:
        print(f"  Path: {error.path}")
        print(f"  Reason: {error.reason}")
    return False


def _format_expected_shape(expected_shape: tuple[int | None, ...]) -> str:
    """Render an expected dataset shape for user-facing messages."""
    return (
        "("
        + ", ".join("*" if dim is None else str(dim) for dim in expected_shape)
        + ")"
    )


def _validate_lheh5_dataset_shape(
    dataset_name: str,
    actual_shape: tuple[int, ...],
    expected_shape: tuple[int | None, ...],
) -> bool:
    """Validate a single LHEH5 dataset shape."""
    if len(actual_shape) != len(expected_shape):
        print(
            "  ❌ "
            f"Dataset '{dataset_name}' has shape {actual_shape}, "
            f"expected {_format_expected_shape(expected_shape)}"
        )
        return False

    if any(
        expected is not None and actual != expected
        for actual, expected in zip(actual_shape, expected_shape, strict=True)
    ):
        print(
            "  ❌ "
            f"Dataset '{dataset_name}' has shape {actual_shape}, "
            f"expected {_format_expected_shape(expected_shape)}"
        )
        return False

    return True


def _validate_lheh5_row_multiple(
    dataset_name: str,
    row_count: int,
    reference_name: str,
    reference_count: int,
) -> bool:
    """Validate that one row count is a clean multiple of another."""
    if reference_count == 0:
        if row_count == 0:
            return True
        print(
            "  ❌ "
            f"Dataset '{dataset_name}' has {row_count} rows, "
            f"but '{reference_name}' has 0 rows"
        )
        return False

    if row_count % reference_count != 0:
        print(
            "  ❌ "
            f"Dataset '{dataset_name}' has {row_count} rows, "
            f"which is not a multiple of '{reference_name}' row count {reference_count}"
        )
        return False

    return True


def _validate_lheh5_dataset_compatibility(file_path: str) -> bool:
    """Validate the dataset layout of an LHEH5 file."""
    with h5py.File(file_path, "r") as h5file:
        missing_datasets = [
            dataset_name
            for dataset_name in LHEH5_REQUIRED_DATASETS
            if dataset_name not in h5file
        ]
        if missing_datasets:
            print(
                "  ❌ Missing required dataset(s): "
                + ", ".join(sorted(missing_datasets))
            )
            return False

        for dataset_name, expected_shape in LHEH5_REQUIRED_DATASETS.items():
            actual_shape = tuple(int(dim) for dim in h5file[dataset_name].shape)
            if not _validate_lheh5_dataset_shape(
                dataset_name,
                actual_shape,
                expected_shape,
            ):
                return False

        has_ctevents = "ctevents" in h5file
        has_ctparticles = "ctparticles" in h5file
        if has_ctevents != has_ctparticles:
            print(
                "  ❌ Counterterm datasets must appear together: "
                "expected both 'ctevents' and 'ctparticles'"
            )
            return False

        for dataset_name, expected_shape in LHEH5_OPTIONAL_DATASETS.items():
            if dataset_name not in h5file:
                continue
            actual_shape = tuple(int(dim) for dim in h5file[dataset_name].shape)
            if not _validate_lheh5_dataset_shape(
                dataset_name,
                actual_shape,
                expected_shape,
            ):
                return False

        event_count = int(h5file["events"].shape[0])
        particle_count = int(h5file["particles"].shape[0])
        if not _validate_lheh5_row_multiple(
            "particles",
            particle_count,
            "events",
            event_count,
        ):
            return False

        expected_process_count = float(h5file["init"][9])
        if not expected_process_count.is_integer():
            print(
                "  ❌ "
                "Dataset 'init' stores a non-integer numProcesses value "
                f"({expected_process_count})"
            )
            return False

        procinfo_count = int(h5file["procInfo"].shape[0])
        if int(expected_process_count) != procinfo_count:
            print(
                "  ❌ "
                f"Dataset 'procInfo' has {procinfo_count} rows, "
                f"but init numProcesses is {int(expected_process_count)}"
            )
            return False

        if has_ctevents and has_ctparticles:
            ctevent_count = int(h5file["ctevents"].shape[0])
            ctparticle_count = int(h5file["ctparticles"].shape[0])

            if ctevent_count != event_count:
                print(
                    "  ❌ "
                    f"Dataset 'ctevents' has {ctevent_count} rows, "
                    f"but 'events' has {event_count} rows"
                )
                return False

            if not _validate_lheh5_row_multiple(
                "ctparticles",
                ctparticle_count,
                "ctevents",
                ctevent_count,
            ):
                return False

            event_stride = 0 if event_count == 0 else particle_count // event_count
            ctevent_stride = (
                0 if ctevent_count == 0 else ctparticle_count // ctevent_count
            )
            if event_stride != ctevent_stride:
                print(
                    "  ❌ "
                    "Datasets 'particles' and 'ctparticles' do not use the same "
                    f"per-event row count ({event_stride} vs {ctevent_stride})"
                )
                return False

    print("  ✓ LHEH5 dataset validation passed")
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


def _get_default_schema_dir() -> Path:
    """Return the directory that contains the LHE XSD schema files."""
    return Path(__file__).parent.parent / "schema"


def main() -> None:
    """Main CLI function."""
    parser = create_base_parser(
        description="Validate LHE/LHEH5 files against schema and/or format rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhevalidate file.lhe                     # Validate with both XSD and pylhe (default)
  lhevalidate --no-pylhe file.lhe          # XSD validation only (faster)
  lhevalidate --no-xsd file.lhe            # pylhe parsing validation only
  lhevalidate file.hdf5                    # Validate LHEH5 dataset layout and pylhe parsing
  lhevalidate file1.lhe file2.lhe          # Validate multiple files
  cat file.lhe | lhevalidate               # Read from stdin

Validation levels:
  1. Schema/layout validation - XSD for XML LHE, dataset compatibility for LHEH5
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

    # Find schema files
    schema_path = _get_default_schema_dir()
    try:
        _discover_schema_paths(schema_path)
    except FileNotFoundError:
        print(f"Error: Schema files not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[str | TextIO] = []
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
