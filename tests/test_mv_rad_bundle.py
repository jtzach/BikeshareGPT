from pathlib import Path

from bikesharegpt.gbfs.downloader import download_snapshot
from bikesharegpt.utils.io import read_jsonl


def test_mv_rad_bundle_loads():
    root = Path(__file__).resolve().parents[1]
    gbfs = root / 'benchmarks' / 'gbfs_mv_rad_v1' / 'snapshots' / 'mv_rad' / 'gbfs.json'
    snap = download_snapshot('mv_rad', str(gbfs), language='en', timeout=5)
    assert snap.station_information.shape[0] == 64
    assert snap.station_status.shape[0] == 64
    assert snap.vehicle_types.shape[0] == 11
    assert snap.free_bike_status.shape[0] == 335


def test_mv_rad_tasks_exist():
    root = Path(__file__).resolve().parents[1]
    tasks = read_jsonl(root / 'benchmarks' / 'gbfs_mv_rad_v1' / 'tasks.jsonl')
    assert len(tasks) == 300
    cats = {t['category'] for t in tasks}
    assert cats == {'semantics', 'retrieval', 'synthesis'}


def test_mv_rad_task_counts_by_category():
    root = Path(__file__).resolve().parents[1]
    tasks = read_jsonl(root / 'benchmarks' / 'gbfs_mv_rad_v1' / 'tasks.jsonl')
    counts = {}
    for t in tasks:
        counts[t['category']] = counts.get(t['category'], 0) + 1
    assert counts == {'semantics': 100, 'retrieval': 100, 'synthesis': 100}
