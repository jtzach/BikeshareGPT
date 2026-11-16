import pytest

from bikesharegpt.gbfs.downloader import _is_local_path


@pytest.mark.parametrize("value", [
    r"C:\snapshot\gbfs.json", "D:/snapshot/gbfs.json", "/snapshot/gbfs.json",
    "benchmarks/snapshot/gbfs.json", "file:///snapshot/gbfs.json",
])
def test_filesystem_inputs_are_not_sent_to_http(value):
    assert _is_local_path(value)


def test_remote_json_stays_remote():
    assert not _is_local_path("https://example.org/gbfs.json")
