from pathlib import Path

import pylhe
import skhep_testdata

from lheutils.cli.lheunstack import lhe_unstack


def test_lhe_unstack_preserves_initrwgt_header(tmp_path):
    output_file = tmp_path / "split_proc66.lhe"
    split_files = lhe_unstack("references/files/pylhe-testlhef3.lhe")

    assert len(split_files) == 1

    split_file = split_files[0]
    split_file.tofile(str(output_file))

    reread = pylhe.LHEFile.fromfile(output_file)
    assert reread.header is not None
    assert len(reread.header.initrwgt.entries) == 1
    entry = reread.header.initrwgt.entries[0]
    assert isinstance(entry, pylhe.LHEInitRWGTWeightGroup)
    assert entry.attributes["type"] == "scale_variation"
    assert len(entry.weights) == 9
    assert [proc.procId for proc in reread.init.procInfo] == [66]


def test_lhe_unstack_splits_multi_process_file():
    input_file = skhep_testdata.data_path("pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz")
    split_files = lhe_unstack(input_file)

    proc_ids = [split_file.init.procInfo[0].procId for split_file in split_files]
    assert proc_ids == [3, 2, 1]

    for split_file in split_files:
        target_proc_id = split_file.init.procInfo[0].procId
        assert len(split_file.init.procInfo) == 1
        assert all(
            event.eventinfo.pid == target_proc_id for event in split_file.events
        )
