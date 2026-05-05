import subprocess

import pytest
import skhep_testdata

path = "./src/lheutils/cli/"

# List of LHE files available in skhep_testdata
LHE_FILES = [
    "pylhe-testfile-madgraph-2.0.0-wbj.lhe",
    "pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz",
    "pylhe-testfile-madgraph-2.2.1-Z-fxfx.lhe.gz",
    "pylhe-testfile-madgraph-2.2.1-Z-mlm.lhe.gz",
    # POWHEG is excluded for now since it includes trailing random state information which are not XML compatible see
    # https://gitlab.com/POWHEG-BOX/RES/POWHEG-BOX-RES/-/merge_requests/20
    # https://gitlab.com/POWHEG-BOX/V2/POWHEG-BOX-V2/-/merge_requests/18
    #   "pylhe-testfile-powheg-box-v2-directphoton.lhe",
    #   "pylhe-testfile-powheg-box-v2-hvq.lhe",
    #   "pylhe-testfile-powheg-box-v2-trijet.lhe",
    #   "pylhe-testfile-powheg-box-v2-W.lhe",
    #   "pylhe-testfile-powheg-box-v2-Z.lhe",
    #   "pylhe-testfile-powheg-box-v2-Zj.lhe",
    "pylhe-testfile-pr180.lhe",
    "pylhe-testfile-pr29.lhe",
    "pylhe-testfile-pythia-6.413-ttbar.lhe",
    "pylhe-testfile-pythia-8.3.14-weakbosons.lhe",
    "pylhe-testfile-sherpa-3.0.1-eejjj.lhe",
    "pylhe-testfile-whizard-3.1.4-eeWW.lhe",
    "pylhe-testlhef3.lhe",
]


@pytest.mark.parametrize("lhe_filename", LHE_FILES)
def test_lhevalidate_good(lhe_filename):
    """Test lhevalidate on all available LHE and LHE.gz files."""
    try:
        file_path = skhep_testdata.data_path(lhe_filename)
    except Exception:
        pytest.skip(f"File {lhe_filename} not available in skhep_testdata")

    # run the executable and capture output
    result = subprocess.run(
        [
            f"{path}lhevalidate.py",
            file_path,
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 0, (
        f"lhevalidate failed for {lhe_filename}: {result.stderr}"
    )
    assert "✓ File is valid!" in result.stdout
