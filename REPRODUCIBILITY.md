# Reproduction and historical-result audit

Repository: https://github.com/jtzach/BikeshareGPT

## Preserved submission

This repository was prepared from the submitted Software ZIP. Benchmark data, original outputs, and license files are unchanged. The Data and Software ZIPs are byte-identical (SHA-256 `527d99331bd17b5eabbbeef615d6e8cff9b4b962e5e21b8f1f3fb020e85e0547`). The submitted Bash script is retained with its default configuration updated to the seven-model suite.

## Evaluation protocol

Use `configs/mv_rad_gemma_ministral_gpt5_suite.yaml`: Gemma 3 (4B/12B/27B), Ministral 3 (3B/8B/14B), GPT-5; configured temperature 0, seed 42, timeout 30 seconds, and at most two repair retries (up to three main calls). Seed 42 is a configuration value, not evidence of deterministic provider sampling. Inspect archived `model_spec.json` and `outputs/config.json` for the historical resolved setup.

The GPT-5 adapter omits the temperature parameter from its API request, despite the common configuration value. Do not interpret the configuration as proof that every provider used temperature zero.

The exact system prompt is `bikesharegpt/llm/prompts.py`; five fixed examples are in `data/few_shot_gbfs.yaml`. Every model receives the same examples. Each retry sends the latest execution error in a fresh main request; it does not send the complete prior conversation or previous generated code. Successful execution stops repair even when an answer is wrong. This is bounded execution repair, not an open-ended agent. An optional natural-language summary is not the deterministic graded output.

The runner also contains optional GPT-5 sanity adjudication of selected failures. Set environment variable `BSGPT_SANITY_MAX_CHECKS=0` to disable additional adjudication calls during a benchmark run; primary scores are deterministic grades. Rerunning a completed model can otherwise invoke finalization again.

`requirements.txt` gives lower bounds, not a locked historical environment. Provider model aliases/revisions, hardware/service setup, and exact dependency versions need author-supplied records for full provenance. These historical details have not been inferred or invented.

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

## Offline audit

Run `python scripts/audit_release.py`. Its report checks counts, original checksums, saved input equality, all 300 prediction/grade IDs for each model, original summary arithmetic, per-task artifact diagnostics, and SHA-256 hashes for data/results assets. It uses no network and executes no model code. Frozen output: `audit/release_audit.json`.

Passing establishes structural integrity and accounting consistency, not correct ground truth, valid charts, complete provenance, or broad generalization.

An additional offline inspection checked all 511 saved records for the 73 tasks using integer `exact` references. No accepted fractional numeric answer differed from its reference. The implementation nevertheless coerces extracted numbers with `int` (for example, 64.9 can be accepted for 64). Treat this as an evaluator limitation for future outputs, and version any stricter rule separately rather than overwriting frozen scores.

## Versioning and further validation

The [reference validation report](validation/reference_validation.json) and [semantic evidence](validation/semantic_review_v1.json) add a new audit of all 300 items: 263 supported, two unsupported targets, 25 ambiguities, and ten plotting targets without semantic references. Run `python scripts/validate_references.py` without network access. Its Python calculations do not import the original graders or task generators; semantic judgments are frozen source-grounded Astra annotations, not Python verification of meaning or independent human review.

Run `python scripts/reconstruct_derived_bikes.py --check` to reproduce all 335 derived bike records from station/type inputs. This newly inferred method matches the archived whole JSON object and does not recover original acquisition history. [Provenance evidence](validation/PROVENANCE.md) records the search scope and limitations.

Optional `python scripts/validate_gbfs_schema.py` uses the pinned official schemas and the dependency in `validation/schema_requirements.txt`. It reports known legacy deviations rather than modifying payloads. Its zero exit status indicates that the audit ran, not that every payload conforms. The report separates intentional local discovery URLs from the missing required `timezone` field.

Keep original inputs/scores frozen. Assign a new version to changes in tasks, references, graders, coverage, or prompts. Resume checks task IDs rather than content hashes; use a fresh run name/output directory for any changed protocol.

Before journal release: document/recover derived-data construction; independently review reference answers; clarify authored-data licensing; archive a DOI/citation; retain archive, code revision, environment, and configuration together. Semantic chart grading and extra operators/timestamps should be separate improvements with new validation results.
