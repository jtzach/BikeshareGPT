# GBFSBench MV-Rad v1

This folder contains a static benchmark bundle for GBFS evaluation.

## Contents
- `tasks.jsonl`: the complete benchmark (`300` tasks)
- `manifest.json`: dataset metadata and task counts
- `snapshots/mv_rad/`: the frozen MV-Rad snapshot

## Snapshot summary
- Stations: 64
- Station status rows: 64
- Vehicle types: 11
- Free-bike rows: 335
- Regions: 2

## Task counts
- Semantics: 100
- Retrieval: 100
- Synthesis / code generation: 100

## Notes
- The benchmark is designed to be loaded directly by `configs/mv_rad_gem_v1.yaml`.
- `gbfs.json` uses local relative file paths so the benchmark can run offline.
- `gbfs_source.json` preserves the original source discovery document.
- `free_bike_status.json` is shipped with the frozen bundle and should be described in the paper as a derived augmentation used to widen retrieval and synthesis coverage.
- The released suite is intentionally single-system but benchmark-scale: it supports specification understanding, direct factual lookup, multi-step aggregation, geospatial reasoning, and artifact-producing code-generation tasks.

## Task format
Each task contains: `id`, `category`, `query`, `system_id`, `expected`, `grader`, `tolerance`, and `meta`.
