# Reference answers and deterministic evaluation

Queries and reference answers were constructed together. As confirmed by the author on 20 November 2026, LLM-generated reference programs calculated the data-dependent answers by executing deterministic operations on the frozen GBFS snapshot. The benchmark asks evaluated models to generate executable code that reproduces those results.

Each main-model prompt contains the question, the data-interface instructions and five fixed code examples. It omits the item-specific reference program and expected answer. The examples cover some benchmark operations; the protocol does not claim that every operation is unseen. Reference programs are withheld from prompts, not protected by filesystem isolation.

| Track | v1.1 items | Reference method |
| --- | ---: | --- |
| Semantics | 100 | Source-grounded GBFS definition and option review; Python verifies option mappings |
| Retrieval | 100 | Direct field lookups, filtering, counts and rankings over the frozen JSON |
| Synthesis | 90 | Deterministic sums, means, ratios, joins, groupings and spatial calculations |

For example, station-status counts sum to **335 available bikes**; the average across **64 stations** is **335 / 64 = 5.234375**. The 335 derived bike rows represent those same station bikes and are not added again. Missing capacity and an empty eligible population produce explicit `null` where the query requires it. Ranking ties and spherical-distance conventions are stated in the task.

The v1.1 release retains supported original references and corrects the identified targets and ambiguities. Its [separate validator](../scripts/validate_v1_1.py) yields **290/290 reference matches and 369/369 checks**, with per-item values and methods in the [validation report](../benchmarks/gbfs_mv_rad_v1_1/validation_report.json). Calculations do not use benchmark-model predictions. The semantic review was model-assisted and not blinded to the published labels; it is not independent human annotation.

The [dated provenance update](../validation/PROVENANCE.md#author-confirmation-on-20-november-2026) separates the author's construction account from recovered artifacts. The complete original program archive remains unrecovered. Source feed records and derived vehicle rows are available in the [released dataset](../benchmarks/gbfs_mv_rad_v1_1/), together with its [data card](../DATA_CARD.md).
