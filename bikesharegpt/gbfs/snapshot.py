from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def _to_frame(obj: Any) -> Optional[pd.DataFrame]:
    """Best-effort conversion of a GBFS endpoint payload to a DataFrame.

    GBFS endpoints usually follow: {"data": {"stations": [...]}} or {"data": {"bikes": [...]}}
    or {"data": {"vehicles": [...]}}. Some endpoints have different shapes (dicts, lists).
    """
    if not isinstance(obj, dict):
        return None
    data = obj.get("data")
    if not isinstance(data, dict):
        return None
    for key in ("stations", "bikes", "vehicles", "vehicle_types", "regions", "pricing_plans", "alerts"):
        val = data.get(key)
        if isinstance(val, list):
            try:
                return pd.json_normalize(val)
            except Exception:
                return pd.DataFrame(val)
    return None


@dataclass
class GBFSSnapshot:
    """A single GBFS snapshot downloaded from a system's auto-discovery URL."""

    system_id: str
    auto_discovery_url: str
    language: str = "en"

    # Raw JSON payloads by endpoint name, e.g. "station_information" -> dict
    raw: Dict[str, Any] = field(default_factory=dict)

    # Parsed tables by endpoint name, where applicable
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)

    # Free-form metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    def build_frames(self) -> "GBFSSnapshot":
        frames: Dict[str, pd.DataFrame] = {}
        for name, payload in self.raw.items():
            df = _to_frame(payload)
            if df is not None:
                frames[name] = df
        self.frames = frames
        return self

    @property
    def station_information(self) -> pd.DataFrame:
        return self.frames.get("station_information", pd.DataFrame())

    @property
    def station_status(self) -> pd.DataFrame:
        return self.frames.get("station_status", pd.DataFrame())

    @property
    def free_bike_status(self) -> pd.DataFrame:
        # GBFS v2.3 uses free_bike_status; v3 uses vehicle_status
        return self.frames.get("free_bike_status", self.frames.get("vehicle_status", pd.DataFrame()))

    @property
    def vehicle_types(self) -> pd.DataFrame:
        return self.frames.get("vehicle_types", pd.DataFrame())

    @property
    def system_information(self) -> pd.DataFrame:
        return self.frames.get("system_information", pd.DataFrame())

    @property
    def system_regions(self) -> pd.DataFrame:
        return self.frames.get("system_regions", pd.DataFrame())

    @property
    def system_pricing_plans(self) -> pd.DataFrame:
        return self.frames.get("system_pricing_plans", pd.DataFrame())

    @property
    def system_hours(self) -> pd.DataFrame:
        return self.frames.get("system_hours", pd.DataFrame())

    @property
    def gbfs(self) -> Dict[str, Any]:
        payload = self.raw.get("gbfs")
        if isinstance(payload, dict):
            return payload
        return {}

    @property
    def attributes(self) -> "GBFSSnapshot":
        """Compatibility alias for older prompt/code patterns."""
        return self

    def __getattr__(self, name: str) -> Any:
        """Compatibility fallback for endpoint-style attribute access.

        Many generated snippets use feed.<endpoint_name> directly. If the
        endpoint is tabular we return its parsed DataFrame; otherwise we return
        the raw JSON payload.
        """
        # Use __dict__ directly so unpickling (where attributes are populated
        # incrementally) does not recurse through __getattr__.
        frames = self.__dict__.get("frames") or {}
        raw = self.__dict__.get("raw") or {}
        if name in frames:
            return frames[name]
        if name in raw:
            return raw[name]
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def merged_stations(self) -> pd.DataFrame:
        """Convenience join of station_information + station_status on station_id."""
        info = self.station_information
        status = self.station_status
        if info.empty:
            return status.copy()
        if status.empty:
            return info.copy()
        # Ensure station_id exists and is comparable
        if "station_id" not in info.columns or "station_id" not in status.columns:
            return info.merge(status, how="outer", left_index=True, right_index=True)
        return info.merge(status, on="station_id", how="left", suffixes=("_info", "_status"))

    def save(self, out_dir: str | Path) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        # Save raw payloads
        raw_dir = out / "raw"
        raw_dir.mkdir(exist_ok=True)
        import json
        for name, payload in self.raw.items():
            (raw_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Save a light CSV export of parsed frames (useful for debugging)
        frames_dir = out / "tables"
        frames_dir.mkdir(exist_ok=True)
        for name, df in self.frames.items():
            try:
                df.to_csv(frames_dir / f"{name}.csv", index=False)
            except Exception:
                # Some tables may contain nested structures; skip export
                pass
