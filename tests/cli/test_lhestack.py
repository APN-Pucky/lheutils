from pathlib import Path

import pylhe
import skhep_testdata

from lheutils.cli.lhestack import check_init_consistency, stack_lhe_files


def test_check_init_consistency_accepts_matching_initrwgt():
    lhefiles = [
        pylhe.LHEFile.fromfile(skhep_testdata.data_path("pylhe-testlhef3.lhe")),
        pylhe.LHEFile.fromfile(skhep_testdata.data_path("pylhe-testlhef3.lhe")),
    ]

    assert check_init_consistency(lhefiles) is True


def test_check_init_consistency_rejects_different_initrwgt(tmp_path, capsys):
    modified = tmp_path / "modified_weights.lhe"
    modified.write_text(
        Path(skhep_testdata.data_path("pylhe-testlhef3.lhe"))
        .read_text()
        .replace(
            "muR=0.10000E+01 muF=0.20000E+01",
            "changed initrwgt weight",
            1,
        )
    )

    lhefiles = [
        pylhe.LHEFile.fromfile(skhep_testdata.data_path("pylhe-testlhef3.lhe")),
        pylhe.LHEFile.fromfile(modified),
    ]

    assert check_init_consistency(lhefiles) is False
    captured = capsys.readouterr()
    assert "different weight group configuration" in captured.err


def test_stack_lhe_files_preserves_initrwgt_header(tmp_path):
    first = tmp_path / "first.lhe"
    second = tmp_path / "second.lhe"
    first.write_text(Path(skhep_testdata.data_path("pylhe-testlhef3.lhe")).read_text())
    second.write_text(Path(skhep_testdata.data_path("pylhe-testlhef3.lhe")).read_text())

    output_file = tmp_path / "stacked.lhe"
    stack_lhe_files([str(first), str(second)], str(output_file), new_ids=True)

    stacked = pylhe.LHEFile.fromfile(output_file)
    assert stacked.header is not None
    assert len(stacked.header.initrwgt.entries) == 1
    entry = stacked.header.initrwgt.entries[0]
    assert isinstance(entry, pylhe.LHEInitRWGTWeightGroup)
    assert entry.attributes["type"] == "scale_variation"
    assert len(entry.weights) == 9
    assert len(stacked.init.procInfo) == 2
