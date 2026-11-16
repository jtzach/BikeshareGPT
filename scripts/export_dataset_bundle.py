#!/usr/bin/env python3
"""
Export a self-contained benchmark bundle (tasks + snapshots) from a BikeshareGPT run directory.

This is useful if you:
  1) run "live mode" once (download real GBFS snapshots + generate tasks), then
  2) want to publish a frozen dataset that others can run without downloads.

Example:
  python scripts/export_dataset_bundle.py \
      --run_dir outputs/gbfs_benchmark_2026-01-01_12-00-00 \
      --out_dir benchmarks/gbfs_bench_nextbike_de_2026_01_01
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from bikesharegpt.utils.io import ensure_dir


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def export_dataset_bundle(run_dir: Path, out_dir: Path) -> None:
    run_dir = run_dir.resolve()
    out_dir = out_dir.resolve()

    if not (run_dir / "benchmark" / "tasks.jsonl").exists():
        raise FileNotFoundError(f"Missing tasks.jsonl under: {run_dir / 'benchmark'}")
    if not (run_dir / "snapshots").exists():
        raise FileNotFoundError(f"Missing snapshots/ under: {run_dir}")

    ensure_dir(out_dir)
    ensure_dir(out_dir / "snapshots")

    # 1) Copy tasks
    shutil.copy2(run_dir / "benchmark" / "tasks.jsonl", out_dir / "tasks.jsonl")

    # 2) Convert each saved snapshot (raw/*.json) into a portable "gbfs.json + <lang>/<feed>.json" bundle.
    systems = []
    for sys_dir in sorted((run_dir / "snapshots").iterdir()):
        if not sys_dir.is_dir():
            continue
        raw_dir = sys_dir / "raw"
        if not raw_dir.exists():
            continue

        gbfs_raw = raw_dir / "gbfs.json"
        if not gbfs_raw.exists():
            # Some runs may not have stored gbfs under raw/; skip defensively.
            continue

        gbfs = _read_json(gbfs_raw)
        data = gbfs.get("data", {})
        langs = list(data.keys()) if isinstance(data, dict) else []
        lang = langs[0] if langs else "en"
        feeds = data.get(lang, {}).get("feeds", []) if isinstance(data.get(lang, {}), dict) else []

        # Rewrite feed URLs to local relative paths so the bundle is self-contained.
        new_feeds = []
        for f in feeds:
            if not isinstance(f, dict):
                continue
            name = f.get("name")
            if not name:
                continue
            new_feeds.append({"name": str(name), "url": f"{lang}/{name}.json"})
        if isinstance(data.get(lang, {}), dict):
            data[lang]["feeds"] = new_feeds
        gbfs["data"] = data

        out_sys = out_dir / "snapshots" / sys_dir.name
        ensure_dir(out_sys)
        ensure_dir(out_sys / lang)

        _write_json(out_sys / "gbfs.json", gbfs)

        # Copy each endpoint payload we have.
        for f in new_feeds:
            name = f["name"]
            src = raw_dir / f"{name}.json"
            if src.exists():
                shutil.copy2(src, out_sys / lang / f"{name}.json")

        systems.append(sys_dir.name)

    # 3) Write a minimal manifest
    manifest = {
        "name": out_dir.name,
        "exported_at": int(time.time()),
        "source_run_dir": str(run_dir),
        "systems": systems,
        "notes": "This bundle was exported from a BikeshareGPT run directory. It contains frozen snapshots + the tasks.jsonl used in that run.",
    }
    _write_json(out_dir / "manifest.json", manifest)

    # 4) Dataset license stub (user can edit)
    lic = out_dir / "LICENSE_DATASET.txt"
    if not lic.exists():
        lic.write_text(
            "\"Dataset license\"\n\n"
            "Fill in the license you want to apply to tasks + snapshots in this exported bundle.\n"
            "A common choice for open benchmark bundles is CC0-1.0.\n",
            encoding="utf-8",
        )

    # 5) Small README stub
    readme = out_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {out_dir.name}\n\n"
            "Self-contained BikeshareGPT benchmark bundle.\n\n"
            "Contents:\n"
            "- tasks.jsonl\n"
            "- snapshots/<system_id>/gbfs.json + <lang>/<feed>.json\n"
            "- manifest.json\n\n"
            "To run:\n"
            "  ./run.sh configs/gbfs_bench_v1.yaml  (or point dataset_path to this folder)\n",
            encoding="utf-8",
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True, help="Path to a BikeshareGPT run directory under outputs/.")
    ap.add_argument("--out_dir", required=True, help="Where to write the exported benchmark bundle.")
    args = ap.parse_args()

    export_dataset_bundle(Path(args.run_dir), Path(args.out_dir))
    print(f"[OK] Exported dataset bundle to: {args.out_dir}")


if __name__ == "__main__":
    main()
