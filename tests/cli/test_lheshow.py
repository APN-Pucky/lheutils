import doctest

import pylhe
import skhep_testdata

from lheutils.cli.lheshow import _format_event_pretty, show_event, show_init


def _assert_matches_with_ellipsis(actual: str, expected: str) -> None:
    checker = doctest.OutputChecker()
    assert checker.check_output(expected, actual, doctest.ELLIPSIS), actual


def test_show_event_pretty_prints_human_readable_summary(capsys):
    show_event(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        1,
        output_format="pretty",
    )

    output = capsys.readouterr().out
    assert "Event Summary" in output
    assert "Process ID:" in output
    assert "npLO: -1" in output
    assert "npNLO: 1" in output
    assert "XML attributes: None" in output
    assert "Scales:" in output
    assert "lifetime=0" in output
    assert "Incoming PDG IDs:" in output
    assert "Particles:" in output


def test_show_event_repr_prints_python_repr(capsys):
    show_event(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        1,
        output_format="repr",
    )

    output = capsys.readouterr().out
    assert output.startswith("LHEEvent(")


def test_show_event_lhe_prints_raw_block(capsys):
    show_event(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        1,
        output_format="lhe",
    )

    output = capsys.readouterr().out
    assert output.startswith("<event")


def test_show_init_pretty_prints_human_readable_summary(capsys):
    show_init(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        output_format="pretty",
    )

    output = capsys.readouterr().out
    beam_lines = "\n".join(
        line for line in output.splitlines() if line.startswith("  Beam ")
    )

    assert "Init Summary" in output
    assert "Number of Generators:" in output
    assert "Processes:" in output
    _assert_matches_with_ellipsis(
        beam_lines,
        "\n".join(
            [
                "  Beam A: p (2212) @ 4000 GeV (PDF group -1, set ...21100))",
                "  Beam B: p (2212) @ 4000 GeV (PDF group -1, set ...21100))",
            ]
        ),
    )


def test_show_init_repr_prints_python_repr(capsys):
    show_init(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        output_format="repr",
    )

    output = capsys.readouterr().out
    assert output.startswith("LHEInit(")


def test_show_init_lhe_prints_raw_block(capsys):
    show_init(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        output_format="lhe",
    )

    output = capsys.readouterr().out
    assert output.startswith("<init>")


def test_format_event_pretty_shows_none_for_missing_nplo_and_npnlo():
    event = pylhe.LHEEvent(
        eventinfo=pylhe.LHEEventInfo(
            nparticles=0,
            pid=1,
            weight=1.0,
            scale=2.0,
            aqed=3.0,
            aqcd=4.0,
        ),
        particles=[],
        attributes={},
    )

    output = _format_event_pretty(event)
    assert "npLO: None" in output
    assert "npNLO: None" in output
    assert "XML attributes: None" in output
    assert "Number of weights: 0" in output
    assert "Scales: None" in output


def test_format_event_pretty_shows_extra_xml_attributes():
    event = pylhe.LHEEvent(
        eventinfo=pylhe.LHEEventInfo(
            nparticles=0,
            pid=1,
            weight=1.0,
            scale=2.0,
            aqed=3.0,
            aqcd=4.0,
        ),
        particles=[],
        attributes={"trials": "149994.0", "npLO": " 1 "},
    )

    output = _format_event_pretty(event)
    assert "npLO: 1" in output
    assert "npNLO: None" in output
    assert "XML attributes: trials=149994.0" in output


def test_format_event_pretty_shows_scales():
    event = pylhe.LHEEvent(
        eventinfo=pylhe.LHEEventInfo(
            nparticles=0,
            pid=1,
            weight=1.0,
            scale=2.0,
            aqed=3.0,
            aqcd=4.0,
        ),
        particles=[],
        scales={"fscale": 544.3741211297681, "rscale": 544.3741211297681},
    )

    output = _format_event_pretty(event)
    assert "Number of weights: 0" in output
    assert "Scales: fscale=544.374, rscale=544.374" in output
