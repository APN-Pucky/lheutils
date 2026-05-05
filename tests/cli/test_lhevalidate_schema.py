from io import StringIO
from pathlib import Path

import pytest

from lheutils.cli.lhevalidate import validate_lhe_file

SCHEMA_PATH = Path("src/lheutils/schema/lhe.xsd")
REFERENCE_FILES = [
    Path("references/files/pylhe-testfile-madgraph-2.0.0-wbj.lhe"),
    Path("references/files/pylhe-testfile-pr180.lhe"),
    Path("references/files/pylhe-testfile-whizard-3.1.4-eeWW.lhe"),
    Path("references/files/pylhe-testlhef3.lhe"),
]


@pytest.mark.parametrize("lhe_path", REFERENCE_FILES)
def test_reference_files_validate_against_xsd(lhe_path: Path) -> None:
    assert validate_lhe_file(
        str(lhe_path),
        str(SCHEMA_PATH),
        enable_xsd=True,
        enable_pylhe=False,
    )


def test_validate_lhe_file_honors_disabled_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lhe_path = Path("references/files/pylhe-testfile-whizard-3.1.4-eeWW.lhe")

    assert validate_lhe_file(
        str(lhe_path),
        str(SCHEMA_PATH),
        enable_xsd=True,
        enable_pylhe=False,
    )
    stdout = capsys.readouterr().out
    assert "Checking XSD schema compliance..." in stdout
    assert "Checking init/event text patterns..." in stdout
    assert "Checking LHE format and structure..." not in stdout

    assert validate_lhe_file(
        str(lhe_path),
        str(SCHEMA_PATH),
        enable_xsd=False,
        enable_pylhe=True,
    )
    stdout = capsys.readouterr().out
    assert "Checking XSD schema compliance..." not in stdout
    assert "Checking init/event text patterns..." not in stdout
    assert "Checking LHE format and structure..." in stdout


def test_regex_text_validation_rejects_bad_event_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad_content = """<LesHouchesEvents version="1.0">
<init>
  2212 2212 4.000000e+03 4.000000e+03 0 0 0 0 3 1
  4.876776e+01 2.195044e+00 1.000000e+00 9999
</init>
<event>
this is not a valid event block
</event>
</LesHouchesEvents>
"""

    assert not validate_lhe_file(
        StringIO(bad_content),
        str(SCHEMA_PATH),
        enable_xsd=True,
        enable_pylhe=False,
    )
    stdout = capsys.readouterr().out
    assert "Checking init/event text patterns..." in stdout
    assert "event text validation failed" in stdout
