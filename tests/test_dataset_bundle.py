from bikesharegpt.utils.io import read_jsonl
from bikesharegpt.benchmark.task import Task
from bikesharegpt.gbfs.downloader import download_snapshot


def test_gbfs_bench_v1_bundle_loads():
    rows = read_jsonl("benchmarks/gbfs_bench_v1/tasks.jsonl")
    tasks = [Task.from_dict(r) for r in rows]
    sys_ids = sorted({t.system_id for t in tasks if t.system_id})
    assert "munich_sample" in sys_ids
    assert "berlin_sample" in sys_ids

    for sys_id in sys_ids:
        snap = download_snapshot(sys_id, f"benchmarks/gbfs_bench_v1/snapshots/{sys_id}/gbfs.json", language="en", timeout=10)
        # Station-based systems must have station_information + station_status
        assert snap.station_information.shape[0] > 0
        assert snap.station_status.shape[0] > 0
