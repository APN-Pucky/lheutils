import xml.etree.ElementTree as ET
from itertools import islice

import pylhe
import pytest
import skhep_testdata

from lheutils.cli.lhe2lhe import convert_lhe_file


def _read_lhe_root(output_file: str) -> ET.Element:
    return ET.fromstring(output_file)


def _get_event_central_weight(event: ET.Element) -> float:
    assert event.text is not None
    event_lines = [line.strip() for line in event.text.splitlines() if line.strip()]
    return float(event_lines[0].split()[2])


def test_convert_lhe_file_add_initrwgt_adds_init_weight(tmp_path):
    input_file = skhep_testdata.data_path(
        "pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz"
    )
    output_file = tmp_path / "add_initrwgt.lhe"

    retcode, message = convert_lhe_file(
        input_file,
        str(output_file),
        weight_format=pylhe.LHEWeightFormat.WEIGHTS,
        add_initrwgt=[("newgroup", "9001", "new weight")],
    )

    assert retcode == 0
    assert message == "Conversion successful"

    root = _read_lhe_root(output_file.read_text())
    new_group = root.find("./header/initrwgt/weightgroup[@name='newgroup']")
    assert new_group is not None

    new_weight = new_group.find("./weight[@id='9001']")
    assert new_weight is not None
    assert new_weight.text == "new weight"

    first_event = root.find("./event")
    assert first_event is not None
    assert first_event.find("./weights") is None


def test_convert_lhe_file_append_lhe_weight_copies_central_weight(tmp_path):
    input_file = skhep_testdata.data_path(
        "pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz"
    )
    output_file = tmp_path / "append_lhe_weight.lhe"

    retcode, message = convert_lhe_file(
        input_file,
        str(output_file),
        weight_format=pylhe.LHEWeightFormat.WEIGHTS,
        append_lhe_weight=("newgroup", "9002", "copied central weight"),
    )

    assert retcode == 0
    assert message == "Conversion successful"

    root = _read_lhe_root(output_file.read_text())
    new_group = root.find("./header/initrwgt/weightgroup[@name='newgroup']")
    assert new_group is not None

    new_weight = new_group.find("./weight[@id='9002']")
    assert new_weight is not None
    assert new_weight.text == "copied central weight"

    for event in islice(root.findall("./event"), 3):
        weights = event.find("./weights")
        assert weights is not None
        assert float(weights.text.strip()) == pytest.approx(
            _get_event_central_weight(event)
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"add_initrwgt": [("scale_variation", "1001", "duplicate weight")]},
        {"append_lhe_weight": ("scale_variation", "1001", "duplicate weight")},
    ],
)
def test_convert_lhe_file_rejects_duplicate_weight_ids(tmp_path, kwargs):
    output_file = tmp_path / "duplicate_weight.lhe"

    retcode, message = convert_lhe_file(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        str(output_file),
        weight_format=pylhe.LHEWeightFormat.WEIGHTS,
        **kwargs,
    )

    assert retcode == 1
    assert "Weight ID '1001' already exists" in message


def test_convert_lhe_file_only_weight_id_filters_initrwgt_and_events(tmp_path):
    input_file = skhep_testdata.data_path("pylhe-testlhef3.lhe")
    output_file = tmp_path / "only_weight_id.lhe"
    expected_weights = [
        event.weights["1002"]
        for event in islice(pylhe.LHEFile.fromfile(input_file).events, 3)
    ]

    retcode, message = convert_lhe_file(
        input_file,
        str(output_file),
        weight_format=pylhe.LHEWeightFormat.WEIGHTS,
        only_weight_id="1002",
    )

    assert retcode == 0
    assert message == "Conversion successful"

    root = _read_lhe_root(output_file.read_text())
    kept_weights = root.findall("./header/initrwgt/weightgroup/weight")
    assert [weight.attrib["id"] for weight in kept_weights] == ["1002"]

    for event, expected_weight in zip(
        islice(root.findall("./event"), 3),
        expected_weights,
        strict=True,
    ):
        weights = event.find("./weights")
        assert weights is not None
        assert float(weights.text.strip()) == pytest.approx(expected_weight)
        assert _get_event_central_weight(event) == pytest.approx(expected_weight)


def test_convert_lhe_file_supports_hdf5_output(tmp_path):
    input_file = skhep_testdata.data_path("pylhe-testlhef3.lhe")
    output_file = tmp_path / "converted.h5"

    retcode, message = convert_lhe_file(
        input_file,
        str(output_file),
        file_format=pylhe.LHEFileFormat.HDF5,
    )

    assert retcode == 0
    assert message == "Conversion successful"

    converted = pylhe.LHEFile.fromfile(output_file)
    first_event = next(iter(converted.events))
    assert output_file.exists()
    assert len(converted.init.procInfo) == 1
    assert first_event.eventinfo.pid == 66


@pytest.mark.parametrize(
    "file_format",
    [pylhe.LHEFileFormat.GZIP, pylhe.LHEFileFormat.HDF5],
)
def test_convert_lhe_file_rejects_non_plain_stdout(file_format):
    retcode, message = convert_lhe_file(
        skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        file_format=file_format,
    )

    assert retcode == 1
    assert f"File format '{file_format.value}' requires an output file" in message
