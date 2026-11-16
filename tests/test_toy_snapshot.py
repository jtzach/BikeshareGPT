from bikesharegpt.gbfs.downloader import download_snapshot
from bikesharegpt.benchmark.generators import generate_retrieval_tasks, generate_synthesis_tasks


def test_toy_snapshot_loading():
    snap = download_snapshot("toy", "data/toy_snapshot/gbfs.json", language="en", timeout=10)
    assert snap.station_information.shape[0] == 3
    assert snap.station_status.shape[0] == 3


def test_task_generation():
    snap = download_snapshot("toy", "data/toy_snapshot/gbfs.json", language="en", timeout=10)
    ret = generate_retrieval_tasks(snap, 10, seed=42)
    syn = generate_synthesis_tasks(snap, 10, seed=42)
    assert len(ret) > 0
    assert len(syn) > 0
