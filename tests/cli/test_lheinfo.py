from pathlib import Path

import skhep_testdata

from lheutils.cli.lheinfo import get_lheinfo


def test_get_lheinfo_reports_initrwgt_weight_groups():
    info = get_lheinfo(skhep_testdata.data_path("pylhe-testlhef3.lhe"))

    assert info.weight_groups == {"scale_variation": 9}


def test_get_lheinfo_reports_no_weight_groups_for_unweighted_file():
    info = get_lheinfo(
        skhep_testdata.data_path("pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz")
    )

    assert info.weight_groups == {}


def _set_event_weights(
    source_path: str,
    destination_path: Path,
    event_weights: dict[int, str],
) -> None:
    lines = Path(source_path).read_text().splitlines()
    updated_lines: list[str] = []
    next_event_header = False
    event_index = 0

    for line in lines:
        if next_event_header:
            event_index += 1
            if event_index in event_weights:
                parts = line.split()
                parts[2] = event_weights[event_index]
                line = "  " + " ".join(parts)
            next_event_header = False

        if line.strip() == "<event>":
            next_event_header = True

        updated_lines.append(line)

    destination_path.write_text("\n".join(updated_lines) + "\n")


def test_get_lheinfo_reports_zero_weighted_events(tmp_path, capsys):
    input_file = skhep_testdata.data_path("pylhe-testlhef3.lhe")
    output_file = tmp_path / "zero_weighted.lhe"
    _set_event_weights(
        input_file,
        output_file,
        {
            1: "0.00000000E+00",
            2: "0.00000000E+00",
        },
    )

    info = get_lheinfo(str(output_file), channels=True)

    assert info.zero_weighted_events == 2
    assert info.zero_weighted_events_ratio == 2 / info.num_events
    assert (
        sum(
            channel.num_zero_events
            for process in info.process_info
            for channel in process.channels
        )
        == 2
    )

    acc = info.print()
    printed = capsys.readouterr().out
    assert f"zero: {info.zero_weighted_events_ratio:.2%}" in printed
    assert acc.total_zero_weighted_events == 2

    acc.print()
    summary = capsys.readouterr().out
    assert f"zero: {acc.total_zero_weighted_events / acc.total_events:.2%}" in summary
