# GBFS-Bench v1 (bundled dataset)

This folder contains a **self-contained** benchmark bundle for GBFS (General Bikeshare Feed Specification).
It is designed so that anyone can run the benchmark **without downloading snapshots** and **without generating tasks**.

## Contents

- `tasks.jsonl` — the complete benchmark (Semantics + Retrieval + Synthesis), with ground truth.
- `manifest.json` — dataset metadata (systems, counts, version).
- `snapshots/` — frozen GBFS snapshot bundles (auto-discovery `gbfs.json` + endpoint JSON files).

Snapshot bundles in this version are **synthetic but spec-conformant**. They are intentionally small so the repo runs out-of-the-box.

## Task format (`tasks.jsonl`)

Each line is a JSON object with the fields:

- `id` (string): unique task id
- `category` (one of): `semantics`, `retrieval`, `synthesis`
- `query` (string): natural-language task prompt
- `system_id` (string|null): which snapshot to use (null for semantics)
- `expected` (any JSON): ground truth answer
- `grader` (string): `exact` | `set` | `numeric` | `contains` | `artifact_exists`
- `tolerance` (float): numeric tolerance (if `grader=="numeric"`)
- `meta` (object): optional extra metadata

## How this is used

The BikeshareGPT runner will:

1) Load `tasks.jsonl`
2) Load snapshots from `snapshots/<system_id>/gbfs.json`
3) Ask an LLM to generate Python code that answers each task
4) Execute the code in a sandbox
5) Grade the returned `result["answer"]` against `expected`

## Adding your own GBFS snapshot

You can add a new folder under `snapshots/<your_system_id>/` containing:

- `gbfs.json` (auto-discovery)
- one or more endpoint JSON files referenced by `gbfs.json` (e.g., `en/station_information.json`, ...)

For local bundles, **relative feed URLs** inside `gbfs.json` are supported and are resolved relative to the directory containing `gbfs.json`.

