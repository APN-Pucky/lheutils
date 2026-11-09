import sys
from pathlib import Path

import pylhe
import pytest
import skhep_testdata

from lheutils.cli.lhereplaceid import (
    main,
    parse_id_map,
    replace_ids,
    replace_ids_in_file,
)


def test_parse_id_map():
    assert parse_id_map(["15->13", "-15->-13"]) == {15: 13, -15: -13}


def test_replace_ids_swaps_simultaneously_without_double_replacement():
    event = pylhe.LHEEvent(
        eventinfo=pylhe.LHEEventInfo(
            nparticles=2, pid=1, weight=1.0, scale=0.0, aqed=0.0, aqcd=0.0
        ),
        particles=[
            pylhe.LHEParticle(
                id=13,
                status=1,
                mother1=0,
                mother2=0,
                color1=0,
                color2=0,
                px=0.0,
                py=0.0,
                pz=0.0,
                e=0.0,
                m=0.0,
                lifetime=0.0,
                spin=0.0,
            ),
            pylhe.LHEParticle(
                id=15,
                status=1,
                mother1=0,
                mother2=0,
                color1=0,
                color2=0,
                px=0.0,
                py=0.0,
                pz=0.0,
                e=0.0,
                m=0.0,
                lifetime=0.0,
                spin=0.0,
            ),
        ],
    )

    replace_ids(event, {13: 15, 15: 13})

    assert [p.id for p in event.particles] == [15, 13]


def test_replace_ids_in_file_remaps_particle_ids(tmp_path):
    input_file = Path(skhep_testdata.data_path("pylhe-testlhef3.lhe"))
    output_file = tmp_path / "output.lhe"

    original = pylhe.LHEFile.fromfile(input_file)
    original_ids = [p.id for event in original.events for p in event.particles]
    assert 6 in original_ids

    replace_ids_in_file(
        input_file=str(input_file),
        id_map={6: 999},
        output_file=str(output_file),
    )

    result = pylhe.LHEFile.fromfile(output_file)
    result_ids = [p.id for event in result.events for p in event.particles]
    assert 6 not in result_ids
    assert result_ids.count(999) == original_ids.count(6)


def test_replace_ids_in_file_edits_in_place_when_no_output_given(tmp_path):
    input_file = tmp_path / "input.lhe"
    input_file.write_text(
        Path(skhep_testdata.data_path("pylhe-testlhef3.lhe")).read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    original = pylhe.LHEFile.fromfile(input_file)
    original_ids = [p.id for event in original.events for p in event.particles]
    assert 6 in original_ids

    replace_ids_in_file(
        input_file=str(input_file),
        id_map={6: 999},
    )

    assert input_file.exists()
    result = pylhe.LHEFile.fromfile(input_file)
    result_ids = [p.id for event in result.events for p in event.particles]
    assert 6 not in result_ids
    assert result_ids.count(999) == original_ids.count(6)


def test_replace_ids_in_file_output_gz_is_actually_compressed(tmp_path):
    input_file = Path(skhep_testdata.data_path("pylhe-testlhef3.lhe"))
    output_file = tmp_path / "output.lhe.gz"

    replace_ids_in_file(
        input_file=str(input_file),
        id_map={6: 999},
        output_file=str(output_file),
    )

    with output_file.open("rb") as f:
        assert f.read(2) == b"\x1f\x8b"  # gzip magic bytes

    result = pylhe.LHEFile.fromfile(output_file)
    result_ids = [p.id for event in result.events for p in event.particles]
    assert 999 in result_ids


def test_replace_ids_in_file_in_place_keeps_gz_compressed(tmp_path):
    plain_source = Path(skhep_testdata.data_path("pylhe-testlhef3.lhe"))
    original = pylhe.LHEFile.fromfile(plain_source)
    gz_file = tmp_path / "input.lhe.gz"
    original.tofile(gz_file, lheformat=pylhe.GZ_FORMAT)

    with gz_file.open("rb") as f:
        assert f.read(2) == b"\x1f\x8b"

    replace_ids_in_file(input_file=str(gz_file), id_map={6: 999})

    with gz_file.open("rb") as f:
        assert f.read(2) == b"\x1f\x8b"  # still gzip-compressed after in-place edit

    result = pylhe.LHEFile.fromfile(gz_file)
    result_ids = [p.id for event in result.events for p in event.particles]
    assert 999 in result_ids


def test_main_edits_multiple_files_in_place(tmp_path, monkeypatch):
    source = Path(skhep_testdata.data_path("pylhe-testlhef3.lhe")).read_text(
        encoding="utf-8"
    )
    file1 = tmp_path / "a.lhe"
    file2 = tmp_path / "b.lhe"
    file1.write_text(source, encoding="utf-8")
    file2.write_text(source, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["lhereplaceid", str(file1), str(file2), "6->999"])
    main()

    for f in (file1, file2):
        result = pylhe.LHEFile.fromfile(f)
        result_ids = [p.id for event in result.events for p in event.particles]
        assert 6 not in result_ids
        assert 999 in result_ids


def test_main_rejects_output_with_multiple_files(tmp_path, monkeypatch, capsys):
    file1 = tmp_path / "a.lhe"
    file2 = tmp_path / "b.lhe"
    file1.write_text("", encoding="utf-8")
    file2.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["lhereplaceid", str(file1), str(file2), "6->999", "-o", "out.lhe"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2

    assert "single input file" in capsys.readouterr().err


def test_replace_ids_in_file_swap_is_simultaneous(tmp_path):
    input_file = Path(skhep_testdata.data_path("pylhe-testlhef3.lhe"))
    output_file = tmp_path / "output.lhe"

    original = pylhe.LHEFile.fromfile(input_file)
    original_ids = [p.id for event in original.events for p in event.particles]
    assert 5 in original_ids
    assert 6 in original_ids

    replace_ids_in_file(
        input_file=str(input_file),
        id_map={5: 6, 6: 5},
        output_file=str(output_file),
    )

    result = pylhe.LHEFile.fromfile(output_file)
    result_ids = [p.id for event in result.events for p in event.particles]
    assert result_ids.count(6) == original_ids.count(5)
    assert result_ids.count(5) == original_ids.count(6)
