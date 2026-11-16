# Evaluation protocol and historical-result audit

The current protocol uses `configs/mv_rad_v1_1_suite.yaml`, the 290-task corrected bundle and `data/few_shot_gbfs_v1_1.yaml`. The original configurations, examples, 300 tasks and historical outputs remain unchanged. No new model-performance evaluation has been run on v1.1.

## Framework

The loader exposes the frozen GBFS arrays as pandas tables. Each task receives the fixed system prompt in `bikesharegpt/llm/prompts.py` and five fixed examples. The model is asked for Python defining a JSON-serializable result with an answer key. v1.1 replaces the old histogram example with a calculation over reported positive capacities and an explicit empty-population null rule.

The executor is a Python subprocess with a 30-second timeout. Execution errors or missing code can trigger two repair retries, for up to three main pipeline requests. Each retry sends the original task/prompt plus the latest error, not the full previous conversation or code. Successful execution ends repair even if the answer is wrong. The adapter may try an alternate API route after a failed request, so pipeline-request count is not necessarily HTTP-attempt count.

When no code is returned, the framework can retain parsed text as an answer. Non-null answers can therefore be correct without successful execution; these outcomes are recorded separately. Explicit-null targets in v1.1 require successful execution and an explicit answer key. Missing results, exceptions, string null and NaN do not earn null credit.

Grading protocol 1.1.0 rejects fractional integer truncation, Boolean counts and nonfinite numeric targets. Numeric tasks use declared absolute tolerances; set tasks ignore order. Ten plotting tasks are absent from v1.1. The legacy artifact rule remains for historical inspection, not as a new chart-quality metric.

An optional summary does not determine the primary grade. Optional GPT-5 sanity adjudication is off by default and runs only if `BSGPT_SANITY_MAX_CHECKS` is positive; its output is secondary to deterministic scoring.

## Configuration and resume

The seven-model suite retains Gemma 3 (4B/12B/27B), Ministral 3 (3B/8B/14B) and GPT-5 aliases. Configuration records temperature 0, seed 42, parallelism 1, timeout 30 seconds and two retries. The GPT-5 adapter omits temperature despite the shared setting. Seed 42 does not establish deterministic provider sampling.

A run's `run_identity.json` fingerprints task/snapshot contents, configuration, prompt examples, package Python code, recorded dependency versions, Python version and effective provider endpoints. Endpoints are hashed to avoid storing environment-derived URL credentials. Changed fingerprints and unverified legacy directories are rejected before rewriting saved inputs or making model requests. Live-feed runs require fresh directories; use frozen inputs for resumable evaluation.

New v1.1 outputs normally go to `outputs/mv_rad_v1_1_gemma_ministral_gpt5_suite/`. Keep the source revision, configuration, fingerprint and provider details with any new results. `requirements.txt` contains lower bounds rather than a historical lockfile, and mutable provider aliases cannot guarantee exact reproduction.

## Preserved submission

The repository was prepared from the submitted Software ZIP. The Data and Software ZIPs have identical SHA-256 `527d99331bd17b5eabbbeef615d6e8cff9b4b962e5e21b8f1f3fb020e85e0547`. Original data, outputs and licenses remain preserved. The launcher default now selects v1.1; the original seven-model configuration is still `configs/mv_rad_gemma_ministral_gpt5_suite.yaml`.

The following results belong exclusively to v1. Even its nonvisual 290-item subset differs from v1.1 because the corrected questions, answer positions, inputs and grading changed.

## Original scores and file-existence reconciliation

The submitted grades and summaries store the values below. All 70 plot grades say `no_artifacts`: the original runner passed `result_obj['answer']` and discarded sibling `result_obj['artifacts']`.

| Model | Original correct / 300 | Referenced saved plots / 10 | Separate existence-only diagnostic correct / 300 | Nonvisual correct / 290 |
| --- | ---: | ---: | ---: | ---: |
| Gemma 3 4B | 167 | 5 | 172 | 167 |
| Gemma 3 12B | 205 | 6 | 211 | 205 |
| Gemma 3 27B | 189 | 9 | 198 | 189 |
| Ministral 3 3B | 181 | 7 | 188 | 181 |
| Ministral 3 8B | 169 | 9 | 178 | 169 |
| Ministral 3 14B | 196 | 8 | 204 | 196 |
| GPT-5 | 251 | 10 | 261 | 251 |

Existence-only reconciliation gives 87.0% for GPT-5, 70.3% for Gemma 3 12B, and 68.0% for Ministral 3 14B, explaining the paper's headline percentages. This uses saved files; it is not evidence of when/how the authors produced the published table. Authors should confirm their analysis procedure. The diagnostic does not replace stored grades and is not a semantic visualization score.

The fix and absolute output paths apply to future runs. The audit relocates historical references by their exact task-directory suffix; original prediction strings remain untouched.

GPT-5's saved `additional_info` reports zero stations/points for `mv_rad_syn_082_plot_hist_docks`, `mv_rad_syn_083_plot_scatter_capacity_bikes`, and `mv_rad_syn_090_plot_box_bikes`. Files count under existence-only scoring even when the underlying plotted dataset is empty.


## Offline verification

`python scripts/audit_release.py` checks original counts, checksums, saved input equality, all prediction/grade IDs, original summary arithmetic and artifact diagnostics without executing model code. Its frozen report is [audit/release_audit.json](audit/release_audit.json).

`python scripts/validate_references.py` retains the original finding: 263 supported references, two unsupported targets, 25 ambiguous formulations and ten plots lacking substantive references. The [original validation](validation/README.md) is not rewritten by v1.1.

For the corrected release, run `python scripts/build_v1_1.py --check`, `python scripts/validate_v1_1.py` and `python -m pytest -q tests`. The recorded results are 19 generated files matching, 290/290 reference matches, 369/369 dataset checks and 47 passing tests. Semantic evidence is source-grounded model-assisted review, not independent human annotation.

`python scripts/reconstruct_derived_bikes.py --check` exactly reproduces the 335 derived rows. It is a newly inferred reconstruction, not a historical acquisition record. See [provenance evidence](validation/PROVENANCE.md).

With the dependency from `validation/schema_requirements.txt`, `python scripts/validate_v1_1_schema.py` reports nine individual payloads passing, one intentional local relative-URL deviation and zero unexpected failures. The original schema audit remains separately available and retains the additional missing-timezone finding. Neither certifies all cross-file GBFS rules.

An earlier inspection of all 511 historical predictions on 73 integer-exact tasks found no accepted fractional value differing from its reference. That observation does not validate the old coercion rule; future v1.1 runs use the corrected rule while frozen scores remain unchanged.

## Remaining publication work

Confirm component-level authored-data licensing, final contributor declarations, archival DOI and release citation. Acquisition and historical task-authoring records remain incomplete. Additional operators, time slices or future semantic chart tasks require separate provenance, references and evaluation. The [scientific figures](paper/README.md) explain the retained data and actual framework without claiming new model performance.
