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
