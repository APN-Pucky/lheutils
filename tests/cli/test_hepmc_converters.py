from pathlib import Path

import pylhe
import pytest
import skhep_testdata

pyhepmc = pytest.importorskip("pyhepmc")

from lheutils.cli.hepmc2lhe import convert_hepmc_to_lhe  # noqa: E402
from lheutils.cli.lhe2hepmc import convert_lhe_to_hepmc  # noqa: E402

ISSUE_109_110_LHE = """\
<LesHouchesEvents version="3.0">
<init>
   2212   2212  4.0000000e+03  4.0000000e+03    -1    -1    -1    -1    -4     1
 1.3255800e+01  5.9743900e-01  1.0000000e+00  10001
<initrwgt>
  <weightgroup name="default">
    <weight id="default">default</weight>
  </weightgroup>
</initrwgt>
</init>
<event>
  5  10001  1.9892700000e+01  1.9026000000e+01 -1.0000000000e+00  1.6423900000e-01
   21  -1   0   0 501 502  0.00000000e+00  0.00000000e+00  9.59159976e+01  9.59159976e+01  0.00000000e+00  0.0000e+00  9.0000e+00
   -3  -1   0   0   0 511  0.00000000e+00  0.00000000e+00 -2.72494064e+02  2.72494064e+02  0.00000000e+00  0.0000e+00  9.0000e+00
   25   1   1   2   0   0  4.09599828e+01  7.10971103e+00  4.31925771e+01  1.38634178e+02  1.25002274e+02  0.0000e+00  9.0000e+00
   -3   1   1   2   0 502 -3.20825130e+01  1.03220177e+01 -1.96527493e+02  1.99396307e+02  0.00000000e+00  0.0000e+00  9.0000e+00
   21   1   1   2 501 511 -8.87746976e+00 -1.74317287e+01 -2.32431503e+01  3.03795766e+01  4.76837158e-07  0.0000e+00  9.0000e+00
<weights>
 1.9893e+01
</weights>
</event>
</LesHouchesEvents>
"""


def _particle_expected_fields(event: pylhe.LHEEvent) -> list[tuple[object, ...]]:
    return [
        (
            particle.id,
            particle.status,
            particle.mother1,
            particle.mother2,
            particle.px,
            particle.py,
            particle.pz,
            particle.e,
        )
        for particle in event.particles
    ]


def _assert_lhe_events_match_expected_fields(
    actual: pylhe.LHEEvent, expected: pylhe.LHEEvent
) -> None:
    assert actual.eventinfo.nparticles == expected.eventinfo.nparticles
    assert actual.eventinfo.pid == expected.eventinfo.pid
    assert actual.eventinfo.weight == pytest.approx(expected.eventinfo.weight)
    assert actual.eventinfo.scale == pytest.approx(expected.eventinfo.scale)
    assert actual.eventinfo.aqed == pytest.approx(expected.eventinfo.aqed)
    assert actual.eventinfo.aqcd == pytest.approx(expected.eventinfo.aqcd)

    actual_fields = _particle_expected_fields(actual)
    expected_fields = _particle_expected_fields(expected)
    assert len(actual_fields) == len(expected_fields)

    for actual_particle, expected_particle in zip(
        actual_fields, expected_fields, strict=True
    ):
        assert actual_particle[:4] == expected_particle[:4]
        assert actual_particle[4:] == pytest.approx(expected_particle[4:])


def test_lhe2hepmc_git_pyhepmc_issue_109_110_regression(tmp_path: Path) -> None:
    lhe_file = tmp_path / "issue_109_110.lhe"
    hepmc_file = tmp_path / "issue_109_110.hepmc"
    lhe_file.write_text(ISSUE_109_110_LHE)

    convert_lhe_to_hepmc(str(lhe_file), str(hepmc_file))

    event_line = next(
        line for line in hepmc_file.read_text().splitlines() if line.startswith("E ")
    )
    _, _, nvertices, nparticles = event_line.split()[:4]
    assert nvertices == "1"
    assert nparticles == "5"

    with pyhepmc.open(hepmc_file, "r", format="HepMC3") as reader:
        event = reader.read()

    assert event is not None
    assert len(event.vertices) == 1
    assert len(event.particles) == 5
    assert event.pdf_info is not None
    assert event.pdf_info.scale == pytest.approx(19.026)


def test_lhe_hepmc_lhe_preserves_expected_event_fields(tmp_path: Path) -> None:
    lhe_file = skhep_testdata.data_path("pylhe-testlhef3.lhe")
    hepmc_file = tmp_path / "events.hepmc"
    converted_lhe_file = tmp_path / "events.lhe"

    convert_lhe_to_hepmc(lhe_file, str(hepmc_file))
    convert_hepmc_to_lhe(str(hepmc_file), str(converted_lhe_file))

    expected_events = pylhe.LHEFile.fromfile(lhe_file, generator=False).events
    actual_events = pylhe.LHEFile.fromfile(converted_lhe_file, generator=False).events
    assert len(actual_events) == len(expected_events)

    for actual, expected in zip(actual_events, expected_events, strict=True):
        _assert_lhe_events_match_expected_fields(actual, expected)


def test_hepmc2lhe_preserves_decay_topology(tmp_path: Path) -> None:
    hepmc_file = tmp_path / "decay.hepmc"
    lhe_file = tmp_path / "decay.lhe"

    event = pyhepmc.GenEvent(pyhepmc.Units.GEV, pyhepmc.Units.MM)
    event.event_number = 42
    event.attributes["IDPRUP"] = 77
    event.attributes["AlphaEM"] = 0.00729927
    event.attributes["AlphaQCD"] = 0.118
    event.weights = [2.5]

    pdf_info = pyhepmc.GenPdfInfo()
    pdf_info.scale = 91.1876
    event.pdf_info = pdf_info

    electron = pyhepmc.GenParticle((0.0, 0.0, 100.0, 100.0), 11, 4)
    positron = pyhepmc.GenParticle((0.0, 0.0, -100.0, 100.0), -11, 4)
    z_boson = pyhepmc.GenParticle((0.0, 0.0, 0.0, 200.0), 23, 2)
    muon = pyhepmc.GenParticle((20.0, 0.0, 30.0, 100.0), 13, 1)
    antimuon = pyhepmc.GenParticle((-20.0, 0.0, -30.0, 100.0), -13, 1)

    for particle in (electron, positron, z_boson, muon, antimuon):
        event.add_particle(particle)

    hard_vertex = pyhepmc.GenVertex()
    hard_vertex.add_particle_in(electron)
    hard_vertex.add_particle_in(positron)
    hard_vertex.add_particle_out(z_boson)
    event.add_vertex(hard_vertex)

    decay_vertex = pyhepmc.GenVertex()
    decay_vertex.add_particle_in(z_boson)
    decay_vertex.add_particle_out(muon)
    decay_vertex.add_particle_out(antimuon)
    event.add_vertex(decay_vertex)
    event.set_beam_particles(electron, positron)

    with pyhepmc.open(hepmc_file, "w", format="HepMC3") as writer:
        writer.write(event)

    convert_hepmc_to_lhe(str(hepmc_file), str(lhe_file))

    lhe_event = pylhe.LHEFile.fromfile(lhe_file, generator=False).events[0]
    assert lhe_event.eventinfo.nparticles == 5
    assert lhe_event.eventinfo.pid == 77
    assert lhe_event.eventinfo.weight == pytest.approx(2.5)
    assert lhe_event.eventinfo.scale == pytest.approx(91.1876)
    assert lhe_event.eventinfo.aqed == pytest.approx(0.00729927)
    assert lhe_event.eventinfo.aqcd == pytest.approx(0.118)

    assert [particle.id for particle in lhe_event.particles] == [11, -11, 23, 13, -13]
    assert [particle.status for particle in lhe_event.particles] == [-1, -1, 2, 1, 1]
    assert [
        (particle.mother1, particle.mother2) for particle in lhe_event.particles
    ] == [
        (0, 0),
        (0, 0),
        (1, 2),
        (3, 3),
        (3, 3),
    ]
    assert [
        (particle.px, particle.py, particle.pz, particle.e)
        for particle in lhe_event.particles
    ] == pytest.approx(
        [
            (0.0, 0.0, 100.0, 100.0),
            (0.0, 0.0, -100.0, 100.0),
            (0.0, 0.0, 0.0, 200.0),
            (20.0, 0.0, 30.0, 100.0),
            (-20.0, 0.0, -30.0, 100.0),
        ]
    )
