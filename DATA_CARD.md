# GBFSBench MV-Rad data card

The current release is [v1.1](benchmarks/gbfs_mv_rad_v1_1/). The original v1 bundle and historical outputs are preserved byte-for-byte.

## Versions and units

| Property | Original v1 | Corrected v1.1 |
| --- | ---: | ---: |
| Tasks | 300 | 290 |
| Semantics / retrieval / synthesis | 100 / 100 / 100 | 100 / 100 / 90 |
| Correct semantic options A / B / C / D | 84 / 14 / 2 / 0 | 25 / 25 / 25 / 25 |
| Plot tasks | 10, existence-only | 0, retired |
| Saved model-task records | 2,100 | No new evaluation |

A task is a benchmark item, not an independent mobility observation. Fixed public examples and repeated task patterns do not constitute a held-out generalization study. The old 290 nonvisual tasks are not the corrected 290-task benchmark: contracts, options, inputs and grading changed.

## Source and provenance

The MV-Rad / Nextbike bundle has source identifier `nextbike_um`, GBFS 2.3, and discovery address `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_um/gbfs.json`. It includes 64 station-information rows, 64 station-status rows, 11 vehicle types, two regions and 335 derived bike rows. Endpoint update times span 28 February 2026, 12:47:24–12:53:26 UTC; verified acquisition time is unavailable, and the bundle is not an atomic network capture.

Source-labelled endpoints include discovery, system information, vehicle types, station information/status, hours, regions and pricing. Local discovery rewrites URLs. Derived bike rows expand station/type availability into constructed identifiers, offsets and optional range fields. They represent the station bikes and must not be added to station totals as independent vehicles. Their positions and battery values are not independently observed measurements.

A search of 41 archives recovered an older byte-identical snapshot but no historical acquisition log or complete construction program. The newly inferred `scripts/reconstruct_derived_bikes.py` reproduces all 335 retained rows exactly. This is reproducible reconstruction, not recovered acquisition history. See [provenance evidence](validation/PROVENANCE.md).

The v1.1 copy normalizes `time_zone` to required `timezone`; original bytes remain in v1. One station lacks capacity, and one reports 12 bikes against capacity 11. Missing capacity is not imputed and ratios above one are retained.

## Query and reference construction

The author confirmed on 20 November 2026 that queries and reference answers were constructed together: LLM-generated reference programs calculated the data-dependent answers deterministically from the frozen snapshot. The evaluated models must generate code that reproduces those results. Their prompts contain the question, the data interface and five fixed code examples, but omit the item-specific reference program and expected answer. These examples cover some of the same operations as benchmark tasks, so this is a fixed few-shot protocol.

The 100 specification questions use source-grounded answer choices; the 190 retrieval and synthesis references are checked by separate Python calculations. The complete historical program archive remains unrecovered. The author-confirmed construction account and the retained code evidence are distinguished in the [provenance update](validation/PROVENANCE.md#author-confirmation-on-20-november-2026). See [reference-answer methods](docs/reference_answers.md) for examples and validation details.

## Records and contracts

| Field/file | Meaning |
| --- | --- |
| `tasks.jsonl` | One task per line; strict JSON in v1.1 |
| `id`, `category`, `query` | Stable ID, track and model instruction |
| `expected`, `grader`, `tolerance` | Reference answer, comparison rule and absolute tolerance |
| `meta` | Version, task fingerprint and task-specific metadata |
| `manifest.json`, `migration.json` | Counts, source hashes, contracts, retired IDs and change/option mappings |
| `validation_report.json` | Per-task computational and semantic-contract evidence |
| `snapshots/mv_rad/normalization.json` | Explicit snapshot normalization |
| `outputs/models/*/predictions/` | Historical final responses, execution status, attempts, usage, grades and summaries |

v1.1 uses 244 exact, 36 numeric and ten set graders. Unknown regional capacity and empty-population utilization return explicit null. Null credit requires successful execution and an explicit answer key; failed execution, missing answers, strings and NaN fail. Integer answers cannot match by truncating fractions or equating Boolean and numeric values.

Reported-capacity sums exclude missing values when specified. Occupancy uses the same eligible positive-capacity stations in numerator and denominator. Rankings break ties by ascending lexicographic station ID. Spherical distances use radius 6,371,000 m and task-specific absolute tolerances. Distance tolerance describes numerical agreement, not physical position accuracy.

All 100 semantic option sets are deterministically permuted to balance positions. Three definitions clarify rental/return flags and backend report time. Balancing removes the earlier always-A advantage but does not establish difficulty or eliminate other shortcuts.

## Validation and interpretation

The original audit identified two unsupported targets, 25 ambiguous questions and ten plots without substantive references. v1.1 implements all 27 nonvisual corrections and retires the plots. The [migration](benchmarks/gbfs_mv_rad_v1_1/migration.json) records every change.

Independent Python recalculation and source-grounded model-assisted semantic contracts yield 290/290 reference matches and 369/369 checks. This is not independent human annotation; semantic meaning still involves judgment, and historical authoring records remain incomplete.

Nine of ten normalized payloads pass pinned official individual schemas, with one intentional local relative-URL deviation and zero unexpected failures. This does not certify all cross-file/conditional specification rules. [Schema report](validation/v1_1/schema_validation.json).

Historical outputs retain final attempts and counts, not complete repair conversations. Their scores remain v1 results. [Reproduction notes](REPRODUCIBILITY.md) explain the original artifact-routing defect and separate existence-only arithmetic without rewriting grades. No active v1.1 task measures chart semantics.

Three [scientific figures](paper/README.md) describe data composition, station geography/availability and the framework. The dataset supports fixed-input error analysis and versioned comparisons; it provides no temporal sequence or cross-operator generalization evidence.

## Availability and terms

The [corrected tasks and snapshot](https://github.com/jtzach/BikeshareGPT/tree/3f69fb4b0d2fcf9ee1860ff0e6d2b836150db223/benchmarks/gbfs_mv_rad_v1_1) and [original v1 snapshot](https://github.com/jtzach/BikeshareGPT/tree/3f69fb4b0d2fcf9ee1860ff0e6d2b836150db223/benchmarks/gbfs_mv_rad_v1/snapshots/mv_rad) are publicly available at the pinned GitHub revision. These links provide the released source files, normalized copy, derived rows and reference answers. No archival DOI is currently assigned.

Software is MIT. Frozen source metadata declares CC0-1.0. On 20 November 2026, the author confirmed retaining the existing research-use and attribution terms for authored questions and derived records. Those terms remain copied unchanged into v1.1; this documentation update grants no additional permissions and introduces no replacement license.
