import subprocess
from pathlib import Path

import pytest
import skhep_testdata

path = "./src/lheutils/cli/"
CLOSING_TAG = "</LesHouchesEvents>"

LHE_FILES = [
    "pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz",
    "pylhe-testfile-madgraph-2.2.1-Z-fxfx.lhe.gz",
    "pylhe-testfile-madgraph-2.2.1-Z-mlm.lhe.gz",
    "pylhe-testfile-pr180.lhe",
    "pylhe-testfile-pr29.lhe",
    "pylhe-testfile-pythia-6.413-ttbar.lhe",
    "pylhe-testfile-pythia-8.3.14-weakbosons.lhe",
    "pylhe-testfile-sherpa-3.0.1-eejjj.lhe",
    "pylhe-testfile-whizard-3.1.4-eeWW.lhe",
]
LHE_FILES_BAD = [
    (
        "pylhe-testfile-madgraph-2.0.0-wbj.lhe",
        "missing required attribute 'name'",
    ),
    (
        "pylhe-testlhef3.lhe",
        "assertion test is false",
    ),
]

POWHEG_LHE_FILES = [
    "pylhe-testfile-powheg-box-v2-trijet.lhe",
    "pylhe-testfile-powheg-box-v2-Z.lhe",
    "pylhe-testfile-powheg-box-v2-Zj.lhe",
]

POWHEG_LHE_FILES_BAD = [
    (
        "pylhe-testfile-powheg-box-v2-directphoton.lhe",
        "attribute combine='None'",
    ),
]

# Other POWHEG fixtures still have schema differences unrelated to the trailing
# footer: directphoton, hvq, and W. The dedicated test below only covers the
# samples that become valid once the random-state footer is trimmed.


def _run_lhevalidate(file_path):
    return subprocess.run(
        [
            f"{path}lhevalidate.py",
            str(file_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_trimmed_powheg_copy(source_path: str, target_path: Path) -> None:
    content = Path(source_path).read_text(encoding="utf-8")
    end_index = content.rfind(CLOSING_TAG)
    assert end_index != -1, f"Missing {CLOSING_TAG} in {source_path}"
    target_path.write_text(
        content[: end_index + len(CLOSING_TAG)] + "\n",
        encoding="utf-8",
    )


def _assert_validation_passed(result, lhe_filename):
    assert result.returncode == 0, (
        f"lhevalidate failed for {lhe_filename}: {result.stderr}"
    )
    assert "✓ File is valid!" in result.stdout


def _assert_validation_failed(result, lhe_filename, expected_message):
    assert result.returncode != 0, f"lhevalidate unexpectedly passed for {lhe_filename}"
    assert "❌ File validation failed!" in result.stdout
    assert expected_message in result.stdout
    assert "✓ File is valid!" not in result.stdout


@pytest.mark.parametrize("lhe_filename", LHE_FILES)
def test_lhevalidate_good(lhe_filename):
    """Test lhevalidate on all available LHE and LHE.gz files."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    result = _run_lhevalidate(file_path)
    _assert_validation_passed(result, lhe_filename)


@pytest.mark.parametrize(("lhe_filename", "expected_message"), LHE_FILES_BAD)
def test_lhevalidate_bad(lhe_filename, expected_message):
    """Test lhevalidate rejects invalid reference files."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    result = _run_lhevalidate(file_path)
    _assert_validation_failed(result, lhe_filename, expected_message)


@pytest.mark.parametrize("lhe_filename", POWHEG_LHE_FILES)
def test_lhevalidate_powheg_good(lhe_filename, tmp_path):
    """Test lhevalidate on POWHEG files after trimming the trailing footer."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    trimmed_file = tmp_path / lhe_filename
    _write_trimmed_powheg_copy(file_path, trimmed_file)

    result = _run_lhevalidate(trimmed_file)
    _assert_validation_passed(result, f"trimmed {lhe_filename}")


@pytest.mark.parametrize(("lhe_filename", "expected_message"), POWHEG_LHE_FILES_BAD)
def test_lhevalidate_powheg_bad(lhe_filename, expected_message, tmp_path):
    """Test lhevalidate still rejects trimmed POWHEG files with schema issues."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    trimmed_file = tmp_path / lhe_filename
    _write_trimmed_powheg_copy(file_path, trimmed_file)

    result = _run_lhevalidate(trimmed_file)
    _assert_validation_failed(result, f"trimmed {lhe_filename}", expected_message)
