# GBFSBench and BikeshareGPT

GBFSBench MV-Rad v1 is a frozen, single-system dataset of 300 tasks for GBFS semantics, snapshot retrieval, and executable code generation. BikeshareGPT loads the data, prompts a model to produce Python, executes it in a subprocess, and grades the structured result. The release preserves predictions and grades for seven models (2,100 model-task records).

Repository: https://github.com/jtzach/BikeshareGPT

Read [DATA_CARD.md](DATA_CARD.md) for provenance, data fields, reuse, and limitations, and [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the evaluation protocol and historical score discrepancy.

The [reference audit](validation/README.md) covers all 300 items: 263 are supported, two have unsupported targets, 25 are ambiguous or underspecified, and ten plotting tasks lack substantive correctness references. This is a new Astra-assisted review and independent Python recalculation, not historical or independent human validation. Original tasks and results remain unchanged; [correction proposals](validation/correction_proposals_v1_1.json) are recorded separately.

## Inspect and validate without model calls

Python 3.10 or newer is sufficient for the standard-library audit:

```bash
python scripts/audit_release.py
```

The independent reference check and the reconstructed augmentation are also offline and use the standard library:

```bash
python scripts/validate_references.py
python scripts/reconstruct_derived_bikes.py --check
```

The reconstruction exactly reproduces all 335 derived records. It was inferred from retained data on 16 November 2026; the original acquisition logs and construction script were not recovered. See [provenance evidence](validation/PROVENANCE.md).

For the additional check against pinned official GBFS 2.3 schemas:

```bash
python -m pip install -r validation/schema_requirements.txt
python scripts/validate_gbfs_schema.py
```

Eight of ten endpoint payloads pass their individual schemas. The source system-information payload lacks required `timezone` (it uses `time_zone`); the derived local discovery document deliberately uses relative URLs that fail URI-format checks. The original discovery document passes. See [schema report](validation/schema_validation.json). Completing an audit does not mean all data pass it, and individual-schema checks do not establish complete GBFS conformance.

To save a new report (existing files are never overwritten):

```bash
python scripts/audit_release.py --output audit/my_audit.json
```

The audit verifies task counts, snapshot checksums, saved record completeness, and stored summary arithmetic. It checks referenced artifact files without executing saved model code. A frozen report is in [audit/release_audit.json](audit/release_audit.json).

## Contents

| Path | Contents |
| --- | --- |
| `benchmarks/gbfs_mv_rad_v1/` | The 300-task dataset, manifests, source/derived snapshot files, and original terms |
| `outputs/shared/` | Snapshot and task inputs saved with the released model run |
| `outputs/models/` | Predictions, original grades, summaries, and figures for seven models |
| `data/few_shot_gbfs.yaml` | Five fixed prompt examples |
| `bikesharegpt/` | Loaders, prompts, runner, subprocess executor, and graders |
| `configs/mv_rad_gemma_ministral_gpt5_suite.yaml` | The seven-model configuration associated with the paper |
| `benchmarks/gbfs_bench_v1/`, `data/toy_snapshot/` | Separate example bundles; not extra systems in the 300-task MV-Rad evaluation |
| `tests/` | Offline loader, output, runner, and grading regressions |
| `validation/` | Per-task reference evidence, correction proposals, provenance reconstruction, and official-schema checks |

## Run the seven-model configuration

Install dependencies in a virtual environment, copy `.env.example` to `.env`, and configure credentials for the chosen providers. This command calls external model APIs and may incur charges:

```bash
python -m pip install -r requirements.txt
python -m bikesharegpt.cli --config configs/mv_rad_gemma_ministral_gpt5_suite.yaml
```

On systems with Bash, `./run.sh` uses that same configuration. Python is the portable entry point on Windows. The suite selects Gemma 3 (4B, 12B, 27B), Ministral 3 (3B, 8B, 14B), and GPT-5. Provider availability and mutable model aliases may differ from the original experiment; no new run is claimed to reproduce a historical response exactly.

The previous mixed nine-model configuration remains available as `configs/mv_rad_gem_full_suite.yaml`. It is a separate experiment. `configs/toy.yaml` uses local data but still invokes a model API; use the audit or tests for an offline check.

New suite runs normally write under `outputs/mv_rad_gemma_ministral_gpt5_suite/`. Original submission outputs are preserved separately at `outputs/models/`. Use a fresh run name/output directory after changing tasks, prompts, models, or graders because the runner resumes by task ID.

## Run offline tests

```bash
python -m pip install pytest
python -m pytest -q
```

Tests use fake clients and do not require API keys. The executor is a timeout-controlled Python subprocess, not an operating-system security sandbox. Do not execute untrusted saved model code merely to inspect the dataset.

## Interpretation limits

- Source snapshot: 64 stations, 64 station-status rows, 11 vehicle types, and two regions. The 335 free-bike rows are **derived benchmark records**, not independently observed vehicle positions.
- Feed timestamp: 28 February 2026, 12:47:24 UTC. This does not independently prove acquisition time.
- Endpoint updates span 12:47:24-12:53:26 UTC; the bundle is not an atomic snapshot of one instant.
- Semantics answer labels are A=84, B=14, C=2, D=0; always selecting A scores 84% on that track. Labels are preserved, and this bias must be considered when interpreting accuracy.
- Ten tasks use artifact existence; file production does not establish correct chart data, labels, or meaning.
- Historical grades contain an artifact-routing defect. The updated runner fixes it for future runs. The audit separately reports original scores and an existence-only reconciliation, without rewriting results.
- This release does not establish temporal, cross-operator, or production-agent generalization.

## Licensing and citation status

The original `LICENSE` covers software under MIT. Frozen `system_information.json` reports `license_id: CC0-1.0`. The original `LICENSE_DATASET.txt` files say research use and attribution; they do not specify a standard open license for authored tasks or derived records. These terms are preserved. Authors must clarify the scope and terms for an archival data release. A data DOI, final release identifier, and citation have not yet been assigned in this repository.
