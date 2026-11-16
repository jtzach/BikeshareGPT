from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - pandas is an install dependency, but keep IO helper standalone
    pd = None  # type: ignore


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def to_jsonable(obj: Any) -> Any:
    """Recursively convert common scientific-Python objects to JSON-safe values.

    Model outputs frequently contain numpy scalars, pandas timestamps, sets,
    pathlib paths, or tuples. Without sanitization, writing predictions or
    metrics can fail mid-run and prevent resumable outputs from being saved.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, Path):
        return str(obj)

    if is_dataclass(obj):
        return to_jsonable(asdict(obj))

    if isinstance(obj, np.generic):
        return obj.item()

    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]

    if pd is not None:
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Timedelta):
            return str(obj)
        if isinstance(obj, pd.Series):
            return {str(k): to_jsonable(v) for k, v in obj.to_dict().items()}

    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]

    if hasattr(obj, "tolist"):
        try:
            return to_jsonable(obj.tolist())
        except Exception:
            pass

    if hasattr(obj, "item"):
        try:
            return to_jsonable(obj.item())
        except Exception:
            pass

    return str(obj)


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(to_jsonable(obj), ensure_ascii=False, indent=indent), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(to_jsonable(row), ensure_ascii=False))
            f.write("\n")


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # Keep resume behavior robust if the previous process was interrupted
                # during a write and left behind a truncated final line.
                if idx == 1:
                    raise
                continue
    return rows


def atomic_write_text(path: str | Path, text: str) -> None:
    """Write a file atomically (best-effort)."""
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
