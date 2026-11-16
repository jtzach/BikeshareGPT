# Corrected-release validation

Checks completed on 16 November 2026 for GBFSBench MV-Rad v1.1:

| Check | Result |
| --- | --- |
| Deterministic builder, `python scripts/build_v1_1.py --check` | 19 generated files match |
| Independent reference validator, `python scripts/validate_v1_1.py` | 290/290 references; 369/369 checks |
| Full offline regression suite, `python -m pytest -q tests` | 47 passed |
| Pinned official individual schemas, `python scripts/validate_v1_1_schema.py` | 9 pass; 1 expected local relative-URL deviation; 0 unexpected failures |
| Protected original files against published commit `abd9f6defb2874a799ca81cc8159b122d965dc38` | 188 files byte-identical |

Protected files comprise the original MV-Rad v1 bundle, historical outputs, existing licenses and configurations, and original few-shot examples. The corrected bundle is separate; retired tasks remain in v1.

A focused GPT-6-Astra review checked all 27 identified nonvisual corrections, source consistency, null contracts, grading edge cases and resumable-run identity. It found an omitted effective provider endpoint in the run fingerprint. That omission was fixed with a shared endpoint resolver and regression coverage for OpenAI, Ollama and optional sanity adjudication. The follow-up found no remaining material issue within that scope. This is model-assisted review, not independent human annotation or proof that every possible ambiguity has been eliminated.

The frozen per-task report is [validation_report.json](../../benchmarks/gbfs_mv_rad_v1_1/validation_report.json); the complete change mapping is [migration.json](../../benchmarks/gbfs_mv_rad_v1_1/migration.json). [schema_validation.json](schema_validation.json) records individual-payload schema results. Individual schema checks do not certify every cross-file GBFS rule.

No new benchmark-provider API calls or LLM performance evaluation were made for this correction. Historical v1 scores must not be relabelled as v1.1 performance. Semantic plot grading was not introduced: ten inadequately specified visualization tasks were retired, while scientific figures were authored directly from the data and implementation.
