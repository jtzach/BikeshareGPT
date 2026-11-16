# GBFSBench MV-Rad v1 data card

Code and data repository: https://github.com/jtzach/BikeshareGPT

This card describes `benchmarks/gbfs_mv_rad_v1/` and its associated saved model outputs. It separates source data, author-derived data, and evaluation records.

## Purpose and units

The dataset contains 300 English-language items: 100 semantics, 100 retrieval, and 100 synthesis/code-generation tasks. A task is a benchmark item, not a participant or an independent mobility observation. Seven saved model runs contain 300 predictions and grades each (2,100 model-task records). The data support inspection of structured-data questions, output conventions, error patterns, and fixed-input evaluation methods.

## Source and provenance

- System: MV-Rad / Nextbike; source identifier `nextbike_um`; GBFS 2.3.
- Original discovery URL: `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_um/gbfs.json`.
- Frozen feed `last_updated`: `1772282844`, or 2026-02-28 12:47:24 UTC. Exact acquisition time and collection environment require author confirmation; this is a feed update timestamp.
- Raw files declared by the existing manifest: `gbfs_source.json`, `system_information.json`, `vehicle_types.json`, `station_information.json`, `station_status.json`, `system_hours.json`, `system_regions.json`, and `system_pricing_plans.json`.
- Derived files: `gbfs.json` rewrites discovery links for local use; `free_bike_status.json` expands station availability/vehicle-type information into benchmark vehicle records.
- Verified counts: 64 station-information rows, 64 station-status rows, 11 vehicle types, 335 derived bike rows, and two regions.

The bundle is not an atomic observation of one instant: endpoint `last_updated` values span 2026-02-28 12:47:24 to 12:53:26 UTC. Station status and derived bike data use 12:51:24 UTC; hours, pricing, and regions use 12:53:26 UTC. The audit enumerates every file timestamp. Do not substitute the discovery timestamp for all endpoints.

Derived bike records contain constructed identifiers (for example `65937_bike_1`), vehicle types, station identifiers, booleans, and coordinates. Their coordinates and flags must not be treated as independently observed live vehicle positions/statuses. The exact original derivation script, coordinate-offset rules, and any random seed were not located in the submitted release. They require confirmation and a versioned method before a complete provenance claim can be made.

## Files and schema

A subsequent search of 41 archives recovered an older byte-identical snapshot but no historical construction script or acquisition log. The new `scripts/reconstruct_derived_bikes.py` independently reconstructs the complete 335-row JSON object exactly from source station/type data. The inferred coordinate and battery rules, their limited scope, and source hashes are documented in [validation/PROVENANCE.md](validation/PROVENANCE.md). Exact reconstruction does not establish the original collection or authoring history.

| File or field | Meaning |
| --- | --- |
| `tasks.jsonl` | One JSON object per task |
| `id` | Unique identifier joining tasks, predictions, and grades |
| `category` | `semantics`, `retrieval`, or `synthesis` |
| `query` | English instruction supplied to the model |
| `system_id` | Local snapshot key when applicable |
| `expected` | Reference answer or artifact expectation; type varies by task |
| `grader` | Rule: 243 `exact`, 37 `numeric`, 10 `set`, and 10 `artifact_exists` tasks |
| `tolerance` | Numeric tolerance when applicable |
| `meta` | Optional metadata; some records have an empty object |
| `snapshots/mv_rad/manifest.json` | Source/derived inventory, URL, timestamp, counts |
| `snapshots/mv_rad/SHA256SUMS.txt` | Checksums of 12 original snapshot documentation/data files |
| `outputs/models/*/predictions/predictions.jsonl` | Final returned text/code, result, execution status, attempt count, aggregate token/time use, optional summary |
| `outputs/models/*/predictions/grades.jsonl` | Original task-level grades and expected/predicted values |
| `outputs/models/*/artifacts/` | Retained model-generated figures |

Logs retain the final attempt and an attempt count; they are not complete per-attempt conversations. `grades_sanity.jsonl` is separate adjudication data, not the primary deterministic score.

## Construction and validation

The release includes generic generators and semantics questions, but an exact construction/verification workflow for every static MV-Rad reference answer has not been established from the supplied files. The offline audit checks structural completeness and file integrity; it does not certify every answer or formulation. Author review of answer generation, independent checking, selection, duplicate templates, and few-shot overlap remains necessary.

The five fixed prompt examples cover station counts, maximum availability, total availability, nearest-station lookup, and histogram production. This is a fixed few-shot protocol, not a held-out train/test study. Keep these examples with the baseline and assess overlap before claiming generalization.

The semantics reference labels are strongly imbalanced: A=84, B=14, C=2, D=0. An always-A response scores 84% on that track without reading a question. This weakens interpretation of high semantics accuracy. The frozen labels have not been changed. A future version should randomize/balance choices, retain an explicit mapping, verify answer correctness after shuffling, and rerun all affected evaluations.

## Grading and limits

The new [per-task validation](validation/README.md) supports 263 references, flags two unsupported targets and 25 formulation ambiguities, and identifies ten plotting tasks without substantive correctness references. The two unsupported targets are a missing regional capacity reported as zero and an undefined utilization stored as non-standard JSON `NaN`. The review combines source-grounded Astra adjudication and independent Python calculations; it is not independent human annotation. Corrections are proposals for a new version, not silent edits to v1.

The official-schema check also identifies a missing required `timezone` field in system information (`time_zone` is present instead). The local discovery document intentionally uses relative file URLs and therefore fails URI-format checks. Eight other endpoint payloads pass their individual schemas; cross-file and conditional specification rules need separate evaluation. See [validation/schema_validation.json](validation/schema_validation.json).

The submitted runner dropped top-level `artifacts` before `artifact_exists`, producing `no_artifacts` for every plot task. The updated runner routes the full result for future runs; original grades remain unchanged. The audit separately reconciles file existence, explaining the headline arithmetic without certifying semantic chart correctness. Some saved GPT-5 outputs explicitly describe zero-point plots.

Other limitations: one frozen system, limited optional-endpoint coverage, no temporal sequence, derived vehicle records, and no independent validation of all references. The executor has a subprocess timeout but does not isolate network/filesystem access at operating-system level.

The `exact` grader includes coercion rather than strict type-aware equality: for integer reference answers, extracted numeric values are converted with `int`, so a fractional value such as 64.9 can match an expected 64. An offline inspection of all 511 saved model-task records for the 73 integer-exact tasks found no accepted fractional value differing from its reference. The rule remains a limitation for new outputs and should be tightened and regression-tested in a separately versioned evaluator. The existing records and grader semantics have not been silently changed.

## Reuse

- Inspect metadata, identifier normalization, joins, aggregation, and formatting errors using final predictions and references.
- Compare evaluators or prompting protocols using fixed IDs and inputs, saving new results under a new release/run identifier.
- Develop a semantic chart grader checking selected rows, values, labels, and structure; report it as a new metric version.
- Construct additional operator/snapshot bundles with separate provenance and validated references.

## Terms and remaining release metadata

Code is MIT. Frozen source metadata declares `CC0-1.0`; original dataset terms state research use and attribution. This card does not replace those terms or grant additional permissions. Authors must confirm licensing for authored tasks and derived data, redistribution, and generated outputs, and provide final contributor information. An archival repository, DOI, release citation, and contact details require completion before journal submission.
