from __future__ import annotations

import json
import time
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from bikesharegpt.gbfs.snapshot import GBFSSnapshot


def _is_local_path(url_or_path: str) -> bool:
    # allow: file:///abs/path, /abs/path, relative/path
    if url_or_path.startswith("file://"):
        return True
    # urlparse treats a Windows drive letter as a URI scheme (for example D:).
    # Check absolute filesystem paths before deciding to make an HTTP request.
    if Path(url_or_path).is_absolute() or PureWindowsPath(url_or_path).is_absolute():
        return True
    parsed = urlparse(url_or_path)
    return parsed.scheme == "" and (url_or_path.endswith(".json") or Path(url_or_path).exists())


def _read_local_json(url_or_path: str) -> Any:
    if url_or_path.startswith("file://"):
        path = url_or_path[len("file://") :]
    else:
        path = url_or_path
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch_json(url: str, *, timeout: int = 30) -> Any:
    """Fetch JSON from URL (or local file path)."""
    if _is_local_path(url):
        return _read_local_json(url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def resolve_feeds(auto_discovery_url: str, *, language: str = "en", timeout: int = 30) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """Resolve an auto-discovery URL (gbfs.json) to concrete feed endpoint URLs.

    Returns:
        chosen_language: the language key actually used
        feeds: dict mapping endpoint name -> url
        meta: best-effort metadata (last_updated, ttl, version, available_languages)
    """
    discovery = fetch_json(auto_discovery_url, timeout=timeout)
    data = discovery.get("data", {}) if isinstance(discovery, dict) else {}
    available_langs = list(data.keys())
    chosen_lang = language if language in data else (available_langs[0] if available_langs else language)
    feeds_list = data.get(chosen_lang, {}).get("feeds", [])
    feeds: Dict[str, str] = {}
    for f in feeds_list:
        if not isinstance(f, dict):
            continue
        name = f.get("name")
        url = f.get("url")
        if not name or not url:
            continue
        feeds[str(name)] = str(url)

    # If the auto-discovery URL is a local file, resolve any *relative* local feed URLs
    # relative to the directory that contains the gbfs.json file. This makes it easy
    # to ship self-contained snapshot bundles on disk.
    if _is_local_path(auto_discovery_url):
        base_path = auto_discovery_url[len("file://") :] if auto_discovery_url.startswith("file://") else auto_discovery_url
        base_dir = Path(base_path).parent
        for k, url in list(feeds.items()):
            if not isinstance(url, str):
                continue
            if url.startswith("file://"):
                continue
            if _is_local_path(url):
                p = Path(url)
                if not p.is_absolute():
                    feeds[k] = str(base_dir / p)

    meta = {
        "last_updated": discovery.get("last_updated") if isinstance(discovery, dict) else None,
        "ttl": discovery.get("ttl") if isinstance(discovery, dict) else None,
        "version": discovery.get("version") if isinstance(discovery, dict) else None,
        "available_languages": available_langs,
        "chosen_language": chosen_lang,
    }
    return chosen_lang, feeds, meta


def download_snapshot(
    system_id: str,
    auto_discovery_url: str,
    *,
    language: str = "en",
    timeout: int = 30,
    sleep_seconds: float = 0.0,
) -> GBFSSnapshot:
    """Download one GBFS snapshot and parse key endpoints."""
    chosen_lang, feeds, meta = resolve_feeds(auto_discovery_url, language=language, timeout=timeout)

    raw: Dict[str, Any] = {}
    # Always store the discovery itself
    raw["gbfs"] = fetch_json(auto_discovery_url, timeout=timeout)

    for name, url in feeds.items():
        try:
            raw[name] = fetch_json(url, timeout=timeout)
        except Exception as e:
            # Keep a structured error so downstream code can skip missing endpoints
            raw[name] = {"_download_error": str(e), "_url": url}
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    snap = GBFSSnapshot(system_id=system_id, auto_discovery_url=auto_discovery_url, language=chosen_lang, raw=raw, meta=meta)
    snap.build_frames()
    return snap


def download_multi_snapshot(
    system_id: str,
    auto_discovery_url: str,
    *,
    language: str = "en",
    timeout: int = 30,
    snapshots: int = 2,
    interval_seconds: int = 120,
) -> list[GBFSSnapshot]:
    """Download multiple snapshots spaced out in time."""
    out: list[GBFSSnapshot] = []
    for i in range(snapshots):
        out.append(download_snapshot(system_id, auto_discovery_url, language=language, timeout=timeout))
        if i < snapshots - 1:
            time.sleep(interval_seconds)
    return out
