from pathlib import Path

import pylhe
import skhep_testdata

from lheutils.cli.lhereplaceid import parse_id_map, replace_ids, replace_ids_in_file


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
