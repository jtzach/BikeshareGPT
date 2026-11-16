# GBFSBench MV-Rad v1.1

This corrected release contains **290 active tasks**: 100 semantics, 100 retrieval and 90 synthesis tasks. The ten existence-only plotting tasks are retired from this version. They remain unchanged in archival v1, together with its original 300 tasks and historical model outputs.

## Contracts

- Unknown total regional capacity returns explicit JSON `null` if any station's capacity is missing. An empty eligible population for mean utilization also returns explicit `null`; missing output or an execution failure is not a valid null answer.
- Reported-capacity sums explicitly exclude unknown capacities. Utilization uses reported positive capacity; occupancy uses the same eligible stations in numerator and denominator. Ratios above one are retained, not clipped.
- Derived bike rows represent the station bikes and are not added as independent vehicles.
- Rankings use ascending lexicographic station IDs to break ties. Spherical distances use radius 6,371,000 m. Distance tolerances describe numerical agreement, not physical location accuracy.
- All 100 semantic items have deterministically permuted options, with exactly 25 correct answers in each position. Three definitions clarify operating flags and backend report time. The public balancing procedure is reproducible; this is not a hidden test set.
- The copied snapshot normalizes `time_zone` to `timezone`; original payloads remain in v1. Derived records, unknown collection history and single-system/snapshot scope remain limitations.

`migration.json` records every retained/retired ID, content change, option mapping and source/output fingerprint. `manifest.json` identifies the grading and version contracts. JSON output is strict and contains no NaN.

## Reproduce and validate

From the repository root:

```bash
python scripts/build_v1_1.py --check
python scripts/validate_v1_1.py
```

The builder never writes v1. The independent validator calculates snapshot answers separately from the builder and checks option meaning against the frozen semantic review plus the three source-grounded wording corrections. It is model-assisted/computational validation, not independent human annotation.

No new LLM benchmark runs have been performed for v1.1. Historical v1 model scores must not be relabelled as v1.1 results, because questions, choices, inputs and the active task set changed. Explanatory manuscript figures are generated from data separately from model evaluation.

The original dataset license wording is preserved in `LICENSE_DATASET.txt`; this version does not invent a replacement license or acquisition history.
