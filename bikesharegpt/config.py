from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Literal

import yaml
from pydantic import BaseModel, Field, ConfigDict


class FeedConfig(BaseModel):
    """A single GBFS system (identified by its auto-discovery URL)."""

    id: str
    city: Optional[str] = None
    country: Optional[str] = None
    auto_discovery_url: str = Field(..., description="GBFS auto-discovery URL (gbfs.json)")
    language: str = "en"
    # Optional local path override (useful for offline / toy runs)
    snapshot_path: Optional[str] = None


class RunConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str = "run"
    output_root: str = "outputs"

    # Models
    provider: Literal["openai", "ollama"] = "openai"
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    model_main: str = "gpt-4o"
    model_summary: str = "gpt-4o-mini"
    model_moderation: str = "gpt-4o-mini"
    summary_enabled: bool = True

    temperature: float = 0.0
    max_retries: int = 2
    timeout_seconds: int = 30
    parallelism: int = 1
    seed: int = 42


class ModelSpec(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    """A single model configuration in a benchmark suite.

    The repo supports OpenAI-compatible backends. In practice this means the
    same execution pipeline can target both OpenAI and Ollama Cloud by changing
    the provider, base URL, and API key environment variable.
    """

    name: str
    provider: Literal["openai", "ollama"] = "openai"
    model_main: str
    model_summary: Optional[str] = None
    model_moderation: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    size_label: Optional[str] = None
    notes: Optional[str] = None
    temperature: Optional[float] = None
    max_retries: Optional[int] = None
    summary_enabled: Optional[bool] = None


class BenchmarkConfig(BaseModel):
    """Benchmark configuration.

    If `dataset_path` is provided, BikeshareGPT will run in *dataset mode*:
    it will load `tasks.jsonl` and snapshots from that directory and will
    **skip** any network downloads and task generation.
    """

    dataset_path: Optional[str] = None

    semantics: bool = True
    retrieval: bool = True
    synthesis: bool = True

    # How many tasks to generate per feed (retrieval / synthesis)
    retrieval_tasks_per_feed: int = 25
    synthesis_tasks_per_feed: int = 25

    # Multi-snapshot (optional)
    multi_snapshot: bool = False
    snapshots_per_feed: int = 2
    snapshot_interval_seconds: int = 120


class AppConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    run: RunConfig = RunConfig()
    feeds: List[FeedConfig] = Field(default_factory=list)
    benchmark: BenchmarkConfig = BenchmarkConfig()
    model_suite: List[ModelSpec] = Field(default_factory=list)


def load_config(path: str | Path) -> AppConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    # accept both top-level "data.feeds" and top-level "feeds"
    if "feeds" not in data and "data" in data and isinstance(data["data"], dict):
        data["feeds"] = data["data"].get("feeds", [])
    return AppConfig.model_validate(data)
