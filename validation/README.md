# Reference validation, 16 November 2026

This is a new GPT-6-Astra review and independent Python recalculation of all
300 frozen MV-Rad questions. It is **not independent human validation**, was
not blinded to the published labels, and does not establish how the original
authors validated their questions. Published tasks, labels and model results
remain unchanged.

| Track | Independently matches | Mismatch / unsupported target | Ambiguous or underspecified | Not verifiable |
| --- | ---: | ---: | ---: | ---: |
| Semantics | 97 | 0 | 3 | 0 |
| Retrieval | 99 | 0 | 1 | 0 |
| Synthesis | 67 | 2 | 21 | 10 |
| Total | **263** | **2** | **25** | **10** |

“Independently matches” means supported within this review's stated scope,
not a guarantee of real-world truth. Of 290 non-artifact references, 288 agree
with the independent value or the best supplied semantic choice **under the
documented assumptions**. That number includes the 25 ambiguous questions and
must not be reported as 288 unambiguously correct questions. The 190 snapshot
tasks comprise 188 reproducible values and two unsupported targets; no other
arithmetic discrepancy was found. All 100 semantic choices, including their
distractors, were inspected against evidence. Python replays those recorded
adjudications; it does not prove natural-language answers automatically.

## Reproduce offline

From the repository root:

```bash
python scripts/validate_references.py
python scripts/validate_references.py --output validation/my_reference_audit.json
```

The first command only prints counts. The second writes a new strict-JSON
report and refuses to overwrite an existing path. The script also works when
invoked by absolute path from another directory. It uses Python's standard
library, reads raw snapshot JSON directly, and imports no project generators,
graders, models or dataframes. It neither reads prediction archives nor
executes saved model-generated code. There are no network or model API calls.

`reference_validation.json` contains one record per task, calculation results,
agreement under assumptions, question status, issues, evidence pointers and
proposals. Input SHA-256 values bind the report to the actual snapshot and
question files. `semantic_review_v1.json` separately records all semantic
choices, source locators and query hashes. Changed semantic question text is
marked not verifiable until reviewed again. Original nonfinite values are
represented by `null` with a separate `source_reference_nonfinite` flag.

## Main findings and proposals

- **Missing capacity:** station `582784416`, the only station in region `949`,
  omits `capacity`; its capacity is not reported as zero. Synthesis 067's
  reference `0` is therefore unsupported as the region's total capacity.
  Synthesis 069 requests a float but stores `NaN` for an undefined utilization
  ratio. Propose an explicit unknown/null policy with a compatible grader, or
  replacement tasks. These are target-validity findings, not two ordinary
  arithmetic mistakes.
- **Implicit omission:** retrieval 099 and synthesis 003, 010, 011, 023, 024,
  029 and 035 omit the same missing capacity when summing, filtering, ranking
  or averaging. Their published values can be reproduced, but the questions
  must state the missing-data policy. Reported capacities total 700 across
  63 stations; the average reported-capacity utilization is about 0.464319.
- **Double counting:** synthesis 012 explicitly requests an addition that
  produces 670, but calls the result visible vehicles. The 335 derived bike
  rows represent the same 335 station bikes. Keep 670 only if the question is
  explicitly about adding overlapping record counts; 335 is the represented
  station-vehicle count, not an independently observed fleet total.
- **Ties:** synthesis 023, 024, 025, 026, 035 and 079 have multiple valid rank
  answers. Their published selections are valid under a lexical-ID tie rule,
  but the questions do not specify it. Propose an explicit secondary key or a
  grader that accepts all valid tied selections. For 079, both `139977` and
  `414200360` have one cargo bike.
- **Distance convention:** synthesis 041–050 reproduce using a sphere radius
  of 6,371,000 m. This validator independently uses Cartesian unit vectors and
  a cross/dot-product angle, rather than the repository's haversine function.
  The questions omit the radius. A radius of 6,371,008.8 m exceeds the stated
  0.001 tolerance for nine of the ten questions. Declare the formula/radius
  and tolerance; floating-point precision is not physical location accuracy.
  The five radius-count tasks are unchanged by this alternative radius, and
  their boundary margins are recorded. Nearest-station tasks use station
  coordinates, not derived vehicle coordinates.
- **Semantic precision:** 006 and 007 omit the `is_renting` / `is_returning`
  conditions from availability definitions; 054 conflates backend reporting
  time with a record update. The published letters are the best supplied
  choices, but their wording needs qualification. See the
  [GBFS 2.3 station-status definitions](https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson).
- **Plots:** synthesis 081–090 provide `True` as an artifact-existence target,
  not a reference image or substantive rubric. Their chart correctness is
  not verifiable from that target. Publish expected plot data and criteria for
  chart type, axes, units, labels, missing values and ranking ties; evaluate
  actual images separately.

All changes above are **proposals for a separately versioned revision**, not
silent corrections to v1. `correction_proposals_v1_1.json` records them without
creating a new task release or recalculating published model scores.

## Snapshot and review limits

The station joins cover all 64 stations. Vehicle-type counts sum to station
bike counts, and derived-row counts equal those counts at every station.
This is internal consistency of an augmentation, not independent corroboration
of vehicle observations. Derived coordinates are up to approximately 10.75 m
from their assigned station and must not be treated as measured positions.

Station `474397171` has 12 bikes and capacity 11, so its utilization exceeds
one; the source discrepancy is retained. All station operational flags are
true in this snapshot. `system_information.json` contains `time_zone`, whereas
the GBFS 2.3 field is `timezone`: retrieval 003 correctly reads the supplied
field, but this does not demonstrate specification conformance. This audit is
not a complete GBFS schema validator.

Semantic evidence primarily uses the version-pinned
[official GBFS 2.3 reference](https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md).
Governance was checked against the
[official maintainer statement](https://gbfs.org/documentation/process/#maintainer-role),
and the GTFS comparison against the
[GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/).
Project-taxonomy questions and the reproducibility question are explicitly
identified as project-specific or methodological judgments. Sources were
consulted on 16 November 2026; replaying the script does not access the web.

This review does not evaluate historical acquisition truth, cross-system
generalization, model output quality, or chart contents. The existing
84/14/2/0 semantic label imbalance also remains; correction of label balance
belongs to a new dataset version with a fresh evaluation.
