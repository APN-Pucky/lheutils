import subprocess
from pathlib import Path
from shutil import copyfile

import h5py
import pytest
import skhep_testdata

path = "./src/lheutils/cli/"
CLOSING_TAG = "</LesHouchesEvents>"

LHE_FILES = [
    "pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz",
    "pylhe-testfile-madgraph-2.2.1-Z-fxfx.lhe.gz",
    "pylhe-testfile-pr180.lhe",
    "pylhe-testfile-pr29.lhe",
    "pylhe-testfile-pythia-6.413-ttbar.lhe",
    "pylhe-testfile-pythia-8.3.14-weakbosons.lhe",
    "pylhe-testfile-sherpa-3.0.1-eejjj.lhe",
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
    (
        "pylhe-testfile-madgraph-2.2.1-Z-mlm.lhe.gz",
        "Unexpected child with tag 'clustering'",
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
LHEH5_FILES = [
    Path("references/files/test.hdf5"),
    Path("references/files/j7_1.hdf5"),
    Path("references/files/l1_0.hdf5"),
]
SKHEP_LHEH5_FILES = [
    ("pylhe-testfile-sherpa.hdf5", (2420, 10), (24200, 13)),
    ("pylhe-testfile-hpcgen.hdf5", (100, 10), (400, 13)),
]

# Other POWHEG fixtures still have schema differences unrelated to the trailing
# footer: directphoton, hvq, and W. The dedicated test below only covers the
# samples that become valid once the random-state footer is trimmed.


def _run_lhevalidate(file_path, *extra_args):
    return subprocess.run(
        [
            f"{path}lhevalidate.py",
            str(file_path),
            *extra_args,
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


def test_lhevalidate_whizard_v2_xsd_only():
    """Test a paper-consistent LHEF v2 sample with XSD-only validation."""
    try:
        file_path = skhep_testdata.data_path("pylhe-testfile-whizard-3.1.4-eeWW.lhe")
    except Exception:
        pytest.skip(
            "File pylhe-testfile-whizard-3.1.4-eeWW.lhe not available in skhep_testdata"
        )

    result = _run_lhevalidate(file_path, "--no-pylhe")
    _assert_validation_passed(result, "pylhe-testfile-whizard-3.1.4-eeWW.lhe")


@pytest.mark.parametrize("lheh5_path", LHEH5_FILES)
def test_lhevalidate_lheh5_good(lheh5_path: Path):
    """Test lhevalidate on known-good LHEH5 reference files."""
    result = _run_lhevalidate(lheh5_path)
    _assert_validation_passed(result, lheh5_path.name)
    assert "LHEH5 dataset validation passed" in result.stdout


@pytest.mark.parametrize(
    ("lhe_filename", "expected_events_shape", "expected_particles_shape"),
    SKHEP_LHEH5_FILES,
)
def test_lhevalidate_lheh5_good_from_skhep_testdata(
    lhe_filename: str,
    expected_events_shape: tuple[int, int],
    expected_particles_shape: tuple[int, int],
):
    """Test lhevalidate on scikit-hep LHEH5 fixtures."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    with h5py.File(file_path, "r") as h5file:
        assert tuple(h5file["version"][...]) == (2, 0, 0)
        assert h5file["events"].shape == expected_events_shape
        assert h5file["particles"].shape == expected_particles_shape
        assert h5file["init"].shape == (10,)
        assert h5file["procInfo"].shape == (1, 6)

    result = _run_lhevalidate(file_path)
    _assert_validation_passed(result, lhe_filename)
    assert "LHEH5 dataset validation passed" in result.stdout


def test_lhevalidate_lheh5_rejects_inconsistent_particle_rows(tmp_path: Path):
    """Test lhevalidate rejects LHEH5 files with inconsistent particle rows."""
    broken_file = tmp_path / "broken_particles.hdf5"
    copyfile("references/files/test.hdf5", broken_file)

    with h5py.File(broken_file, "a") as h5file:
        particles = h5file["particles"][...][:-1]
        particle_attrs = dict(h5file["particles"].attrs)
        del h5file["particles"]
        particle_dataset = h5file.create_dataset("particles", data=particles)
        for key, value in particle_attrs.items():
            particle_dataset.attrs[key] = value

    result = _run_lhevalidate(broken_file)
    _assert_validation_failed(
        result,
        broken_file.name,
        "Dataset 'particles' has 399 rows, which is not a multiple of 'events' row count 100",
    )
