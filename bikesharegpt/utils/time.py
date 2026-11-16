from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_timestamp() -> str:
    """UTC timestamp safe for paths."""
    return utc_now().strftime("%Y%m%d_%H%M%SZ")
