import subprocess
from pathlib import Path

import skhep_testdata

from lheutils.cli.lhediff import diff_lhe_files

path = "./src/lheutils/cli/"


def test_lhediff_same_file():
    # run the executable and capture output
    result = subprocess.run(
        [
            f"{path}lhediff.py",
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 0
    assert result.stdout == ""


def test_lhediff_different_file():
    # run the executable and capture output
    result = subprocess.run(
        [
            f"{path}lhediff.py",
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
            skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 1
    assert result.stdout != ""


def test_lhediff_same_weighted_file_has_no_diffs():
    result = diff_lhe_files(
        "references/files/pylhe-testlhef3.lhe",
        "references/files/pylhe-testlhef3.lhe",
        events=False,
    )

    assert result.lheinitdiff.diffs == {}


def test_lhediff_detects_initrwgt_weight_change(tmp_path):
    original = Path("references/files/pylhe-testlhef3.lhe")
    modified = tmp_path / "modified_weights.lhe"
    modified.write_text(
        original.read_text().replace(
            "muR=0.10000E+01 muF=0.20000E+01",
            "changed initrwgt weight",
            1,
        )
    )

    result = diff_lhe_files(
        str(original),
        str(modified),
        events=False,
    )

    assert "weight_group_scale_variation_weight_1002_name" in result.lheinitdiff.diffs
    diff = result.lheinitdiff.diffs["weight_group_scale_variation_weight_1002_name"]
    assert diff.old == "muR=0.10000E+01 muF=0.20000E+01"
    assert diff.new == "changed initrwgt weight"
