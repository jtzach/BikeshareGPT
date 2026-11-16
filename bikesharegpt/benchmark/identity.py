"""Bind resumable runs to their dataset, configuration, prompts and software."""
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path

from bikesharegpt.llm.openai_client import resolve_base_url

REPO = Path(__file__).resolve().parents[2]


def run_identity(cfg):
    hashes = {}
    if cfg.benchmark.dataset_path:
        dataset = Path(cfg.benchmark.dataset_path)
        paths = [dataset / "tasks.jsonl", dataset / "manifest.json"]
        paths += sorted((dataset / "snapshots").rglob("*.json"))
        for path in paths:
            if path.is_file():
                hashes["dataset/" + path.relative_to(dataset).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if not (dataset / "tasks.jsonl").is_file():
            raise FileNotFoundError(dataset / "tasks.jsonl")
    else:
        # The feed configuration is recorded; a live feed still changes over time.
        hashes["live_input_notice"] = "Mutable live data; use a frozen dataset for reproducible evaluation."
    for path in sorted((REPO / "bikesharegpt").rglob("*.py")):
        hashes[path.relative_to(REPO).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    examples = Path(cfg.run.few_shot_path) if cfg.run.few_shot_path else REPO / "data/few_shot_gbfs.yaml"
    hashes["few_shot_examples"] = hashlib.sha256(examples.read_bytes()).hexdigest()
    versions = {}
    for name in ("openai", "pandas", "numpy", "pydantic", "PyYAML"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    # Endpoint environment overrides affect the backend even with identical YAML.
    # Store only hashes, since custom URLs may include credentials or query tokens.
    endpoints = [
        {"provider": spec.provider, "model": spec.model_main,
         "base_url_sha256": hashlib.sha256(resolve_base_url(spec.provider, spec.base_url).encode("utf-8")).hexdigest()}
        for spec in (cfg.model_suite or [cfg.run])
    ]
    try:
        sanity_enabled = int(os.getenv("BSGPT_SANITY_MAX_CHECKS", "0")) > 0
    except ValueError:
        sanity_enabled = False
    if sanity_enabled:
        endpoints.append({"provider": "openai", "model": "gpt-5-sanity",
                          "base_url_sha256": hashlib.sha256(resolve_base_url("openai").encode("utf-8")).hexdigest()})
    payload = {"identity_version": 1, "config": cfg.model_dump(), "sha256": hashes, "packages": versions,
               "python_version": platform.python_version(), "effective_endpoints": endpoints,
               "optional_sanity_max_checks": os.getenv("BSGPT_SANITY_MAX_CHECKS", "0")}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return {"fingerprint_sha256": hashlib.sha256(encoded).hexdigest(), "inputs": payload}


def guard_run_identity(cfg, suite_dir):
    suite_dir = Path(suite_dir)
    destination = suite_dir / "run_identity.json"
    current = run_identity(cfg)
    if destination.exists():
        if not cfg.benchmark.dataset_path:
            raise ValueError("Live-input runs cannot safely resume against a changed feed. Use a frozen dataset or a fresh run name.")
        saved = json.loads(destination.read_text(encoding="utf-8"))
        if saved.get("fingerprint_sha256") != current["fingerprint_sha256"]:
            raise ValueError("Run inputs or protocol changed. Choose a fresh run name/output directory; archived results will not be reused.")
        return current
    existing_outputs = [p for p in suite_dir.rglob("*") if p.is_file()]
    if existing_outputs:
        raise ValueError("Existing output directory has no verifiable run identity. Use a new directory; legacy records are preserved.")
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(current, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return current
