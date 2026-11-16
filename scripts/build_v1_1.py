"""Build the corrected, separately versioned MV-Rad v1.1 bundle offline.

Original v1 inputs/results are read only. Default writes missing generated files
and refuses to replace different existing bytes. --overwrite replaces only this
script's named v1.1 outputs. --check compares the deterministic build with disk.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/gbfs_mv_rad_v1"
DEST = ROOT / "benchmarks/gbfs_mv_rad_v1_1"
RELEASE = "1.1.0"
DATE = "2026-11-16"
BALANCE_SEED = "GBFSBench-MV-Rad-v1.1-semantic-options-2026-11-16"
SPEC = "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson"
LETTERS = "ABCD"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_old(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"source_nonfinite": str(value)}
    if isinstance(value, dict):
        return {k: safe_old(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_old(v) for v in value]
    return value


def build():
    baseline_audit = json.loads((ROOT / "validation/reference_validation.json").read_text(encoding="utf-8"))
    for relative, expected in baseline_audit["inputs_sha256"].items():
        if digest((ROOT / relative).read_bytes()) != expected:
            raise ValueError(f"Frozen v1 audit input changed: {relative}")
    original_bytes = (SOURCE / "tasks.jsonl").read_bytes()
    original = [json.loads(line) for line in original_bytes.decode("utf-8").splitlines()]
    tasks = [deepcopy(t) for t in original if t["grader"] != "artifact_exists"]
    source_by_id = {t["id"]: t for t in original}
    snapshot = SOURCE / "snapshots/mv_rad"
    info = {s["station_id"]: s for s in json.loads((snapshot / "station_information.json").read_text())["data"]["stations"]}
    status = {s["station_id"]: s for s in json.loads((snapshot / "station_status.json").read_text())["data"]["stations"]}
    capacities = {sid: s["capacity"] for sid, s in info.items() if s.get("capacity") is not None}
    positive = {sid: c for sid, c in capacities.items() if c > 0}
    bikes = {sid: s["num_bikes_available"] for sid, s in status.items()}
    util = {sid: bikes[sid] / c for sid, c in positive.items()}
    ranked_sem = sorted((t["id"] for t in tasks if t["category"] == "semantics"),
                        key=lambda tid: digest((BALANCE_SEED + "|position|" + tid).encode()))
    targets = {tid: LETTERS[i // 25] for i, tid in enumerate(ranked_sem)}
    permutations = []
    changes = []
    semantic_revisions = {
        "sem_006": ("The number of vehicles reported available at the station; rental availability additionally requires is_renting=true.",
                    "The count and the permission to rent are separate: a nonzero count alone does not establish rental availability when is_renting is false."),
        "sem_007": ("The number of empty functional docks; return availability additionally requires is_returning=true.",
                    "The number of empty functional docks and permission to return are separate; is_returning must be true for returns."),
        "sem_054": ("The POSIX time when the station last reported its status to the operator backend.",
                    "last_reported describes the station's report to the operator backend, not necessarily a later feed-record or file update."),
    }
    ranking_syn = {21, 22, 23, 24, 25, 26, 33, 34, 35, 77, 78, 79}
    rank_rule = " Break ties by station_id in ascending lexicographic string order."
    missing_rule = " Exclude stations with missing capacity; do not treat a missing capacity as zero."
    util_rule = " Use only stations with a reported capacity greater than zero; exclude missing or zero capacity and retain ratios greater than one without clipping."
    distance_rule = (" Use station latitude/longitude in degrees and spherical great-circle distance with Earth radius 6371000 meters, "
                     "not an ellipsoidal geodesic. Numerical answers are checked with absolute tolerance 0.001 meters; this is not a claim of physical position accuracy.")
    for task in tasks:
        old = source_by_id[task["id"]]
        reasons = []
        meta = task.setdefault("meta", {})
        meta["dataset_version"] = RELEASE
        if task["category"] == "semantics":
            choices = dict(task["meta"]["choices"])
            correct_old = old["expected"]
            if task["id"] in semantic_revisions:
                choices[correct_old], meta["explanation"] = semantic_revisions[task["id"]]
                meta["definition_source"] = SPEC
                reasons.append("Clarify the GBFS field definition and its operating/timestamp condition.")
            correct_new = targets[task["id"]]
            distractors = sorted((letter for letter in LETTERS if letter != correct_old),
                                 key=lambda letter: digest((BALANCE_SEED + "|option|" + task["id"] + "|" + letter).encode()))
            available = [letter for letter in LETTERS if letter != correct_new]
            mapping = {correct_old: correct_new, **dict(zip(distractors, available))}
            new_choices = {new: choices[next(old_letter for old_letter, target in mapping.items() if target == new)] for new in LETTERS}
            task["expected"] = correct_new
            meta["choices"] = new_choices
            question = old["query"].split("\n\nChoices:", 1)[0]
            task["query"] = question + "\n\nChoices:\n" + "\n".join(f"{k}. {v}" for k, v in new_choices.items()) + "\n\nAnswer with a single letter (A/B/C/D)."
            reasons.append("Deterministic option permutation balances answer positions across the 100 semantic items.")
            permutations.append({"id": task["id"], "old_to_new": mapping, "old_correct": correct_old,
                                 "new_correct": correct_new, "definition_revised": task["id"] in semantic_revisions})
        elif task["category"] == "retrieval":
            n = int(task["id"].split("_")[3])
            if n == 3:
                task["query"] = "What is the timezone field in the normalized system_information for mv_rad? Return a string."
                reasons.append("Read the normalized GBFS timezone field rather than the legacy time_zone spelling.")
            if n in (97, 98, 99):
                task["query"] += rank_rule
                meta["tie_break"] = "station_id_lexicographic_ascending"
                reasons.append("Declare a stable secondary ranking key.")
            if n == 99:
                task["query"] = task["query"].replace("largest capacity", "largest reported capacity") + missing_rule
                meta["missing_capacity"] = "exclude"
                reasons.append("Restrict the ranking to stations with reported capacity.")
        else:
            n = int(task["id"].split("_")[3])
            if n == 3:
                task["query"] = "What is the sum of reported station capacities across mv_rad? Exclude stations with missing capacity and do not infer their capacities. Return an integer."
                task["expected"] = sum(capacities.values())
                meta["missing_capacity"] = "exclude"
                reasons.append("Label the value as a reported-capacity sum, not an observed total including unknown capacities.")
            if n == 10:
                task["query"] = "What is the unweighted mean station utilization ratio (num_bikes_available/capacity) in mv_rad?" + util_rule + " Return a float."
                task["expected"] = statistics.mean(util.values())
                meta["population"] = "stations_with_reported_positive_capacity"
                reasons.append("Define the positive-capacity population and missing-value policy.")
            if n == 11:
                task["query"] = "What is the occupancy percentage among mv_rad stations with reported capacity greater than zero? Divide the sum of num_bikes_available for those same eligible stations by the sum of their capacities, then multiply by 100. Exclude missing or zero capacity from both numerator and denominator; do not clip values. Return a float."
                task["expected"] = 100 * sum(bikes[sid] for sid in positive) / sum(positive.values())
                meta["population"] = "same_stations_with_reported_positive_capacity_in_numerator_and_denominator"
                reasons.append("Use the same explicit eligible population in numerator and denominator.")
            if n == 12:
                task["query"] = "How many station vehicles are represented by the sum of num_bikes_available across mv_rad station_status records? The derived free_bike_status rows represent those same vehicles and must not be added again. Return an integer; this is a reported station count, not an independently observed fleet total."
                task["expected"] = sum(bikes.values())
                meta["deduplication_policy"] = "station_status_count_only_derived_rows_not_added"
                reasons.append("Remove double counting of station bikes and their derived record representation.")
            if n in ranking_syn:
                task["query"] += rank_rule
                meta["tie_break"] = "station_id_lexicographic_ascending"
                reasons.append("Declare ascending lexical station_id for tied ranking values.")
            if n in (23, 29):
                task["query"] += missing_rule
                meta["missing_capacity"] = "exclude"
                reasons.append("State the missing-capacity exclusion policy.")
            if n in (24, 35):
                task["query"] += util_rule
                meta["population"] = "stations_with_reported_positive_capacity"
                reasons.append("State the positive-capacity utilization population.")
            if 41 <= n <= 50:
                task["query"] += distance_rule
                meta["earth_radius_m"] = 6371000
                meta["distance_method"] = "spherical_great_circle"
                meta["absolute_tolerance_m"] = 0.001
                reasons.append("Specify the sphere radius, coordinate convention and numerical tolerance.")
            if 51 <= n <= 60:
                task["query"] += " Use spherical great-circle distances with Earth radius 6371000 meters and coordinates in latitude, longitude order."
                meta["earth_radius_m"] = 6371000
                meta["distance_method"] = "spherical_great_circle"
                if n <= 55:
                    task["query"] += " Include the reference station itself and use an inclusive distance threshold (<=5000 meters)."
                    meta["include_reference_station"] = True
                else:
                    task["query"] += rank_rule
                    meta["tie_break"] = "station_id_lexicographic_ascending"
                reasons.append("Declare geography conventions consistently even where the old answer was not sensitive to them.")
            if n in (62, 67):
                region = "775" if n == 62 else "949"
                eligible = [sid for sid in info if info[sid]["region_id"] == region]
                known = [sid for sid in eligible if sid in capacities]
                task["query"] = f"What is the total station capacity in region_id '{region}' for mv_rad? Return an integer only when every station in this region reports a capacity; if any capacity is missing, return null (Python None) because the total is unknown. Do not replace missing capacity with zero."
                task["expected"] = sum(capacities[sid] for sid in known) if len(known) == len(eligible) else None
                task["grader"] = "exact"
                task["tolerance"] = 0.0
                meta["missing_capacity"] = "null_if_any_missing"
                meta["null_requires_explicit_answer"] = True
                reasons.append("Represent unknown total regional capacity by an explicit null target.")
            if n in (64, 69):
                region = "775" if n == 64 else "949"
                values = [util[sid] for sid in util if info[sid]["region_id"] == region]
                task["query"] = f"What is the unweighted mean utilization ratio (num_bikes_available/capacity) among stations in region_id '{region}' for mv_rad with a reported capacity greater than zero? Exclude missing or zero capacities and retain ratios greater than one without clipping. Return a float if at least one eligible station exists; otherwise return null (Python None)."
                task["expected"] = statistics.mean(values) if values else None
                task["grader"] = "numeric" if values else "exact"
                task["tolerance"] = 1e-6 if values else 0.0
                meta["population"] = "stations_with_reported_positive_capacity"
                meta["empty_population"] = "explicit_null"
                meta["null_requires_explicit_answer"] = True
                reasons.append("Use an explicit empty-population null policy instead of a nonfinite number.")
        meta["source_task_id"] = old["id"]
        changed_fields = [field for field in ("query", "expected", "grader", "tolerance")
                          if safe_old(task[field]) != safe_old(old[field])]
        if changed_fields:
            changes.append({"id": task["id"], "changed_fields": changed_fields,
                            "reasons": reasons, "v1_expected": safe_old(old["expected"]),
                            "v1_1_expected": task["expected"],
                            "v1_query_sha256": digest(old["query"].encode()),
                            "v1_1_query_sha256": digest(task["query"].encode())})
    task_bytes = ("\n".join(json.dumps(t, ensure_ascii=False, allow_nan=False) for t in tasks) + "\n").encode()
    assert Counter(t["category"] for t in tasks) == {"semantics": 100, "retrieval": 100, "synthesis": 90}
    assert Counter(t["expected"] for t in tasks if t["category"] == "semantics") == dict.fromkeys(LETTERS, 25)
    planned = {"tasks.jsonl": task_bytes, "LICENSE_DATASET.txt": (SOURCE / "LICENSE_DATASET.txt").read_bytes()}
    snapshot_planned = {p.name: p.read_bytes() for p in sorted(snapshot.iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt"}
    sysinfo = json.loads(snapshot_planned["system_information.json"])
    assert "timezone" not in sysinfo["data"] and "time_zone" in sysinfo["data"]
    sysinfo["data"]["timezone"] = sysinfo["data"].pop("time_zone")
    snapshot_planned["system_information.json"] = encoded(sysinfo)
    normalization = {"version": RELEASE, "date": DATE,
                     "source_release": "../gbfs_mv_rad_v1", "acquisition_date": None,
                     "transforms": [{"file": "system_information.json", "operation": "rename /data/time_zone to /data/timezone",
                                     "value_preserved": "Europe/Berlin", "reason": "GBFS 2.3 required field name",
                                     "source_sha256": digest((snapshot / "system_information.json").read_bytes()),
                                     "normalized_sha256": digest(snapshot_planned["system_information.json"])}],
                     "limits": ["Normalization is not new acquisition or recovery of historical provenance.",
                                "Derived free-bike coordinates and battery values remain derived, not observed.",
                                "Relative discovery URLs intentionally support local offline execution."]}
    snapshot_planned["normalization.json"] = encoded(normalization)
    sm = json.loads(snapshot_planned["manifest.json"])
    sm["dataset_id"] = "mv_rad_benchmark_ready_v1_1"
    sm["label"] = "MV-Rad v1.1 normalized benchmark snapshot"
    sm["dataset_version"] = RELEASE
    sm["source_snapshot_sha256"] = {p.name: digest(p.read_bytes()) for p in sorted(snapshot.iterdir()) if p.is_file()}
    sm["raw_files"].remove("system_information.json")
    sm["normalized_files"] = ["system_information.json"]
    sm["notes"].append("v1.1 renames the original system_information time_zone key to timezone; source bytes remain in the v1 directory.")
    snapshot_planned["manifest.json"] = encoded(sm)
    snapshot_planned["README.md"] = ("# MV-Rad v1.1 normalized snapshot\n\nThis is a separately versioned copy of the v1 snapshot. Only the system-information payload is normalized: `time_zone` is renamed to `timezone`, preserving its value. See `normalization.json` and source hashes in `manifest.json`. Other endpoint payloads remain byte-identical to v1. The 335 free-bike rows are derived augmentation records, and original acquisition/authoring history remains unresolved. Local discovery URLs intentionally remain relative for offline execution. Original files remain under `benchmarks/gbfs_mv_rad_v1/snapshots/mv_rad/`.\n").encode()
    snapshot_planned["SHA256SUMS.txt"] = ("\n".join(f"{digest(data)}  {name}" for name, data in sorted(snapshot_planned.items())) + "\n").encode()
    for name, data in snapshot_planned.items():
        planned["snapshots/mv_rad/" + name] = data
    retired = [{"id": t["id"], "reason": "Retired from v1.1: file existence has no substantive chart-correctness target; retained only in archival v1."}
               for t in original if t["grader"] == "artifact_exists"]
    migration = {"from_version": "1.0.0", "to_version": RELEASE, "date": DATE,
                 "source_tasks_sha256": digest(original_bytes), "target_tasks_sha256": digest(task_bytes),
                 "v1_preserved": True, "historical_model_results_reused_as_v1_1_results": False,
                 "model_evaluation_status": "No new model runs or v1.1 performance claims.",
                 "retained_task_ids": [t["id"] for t in tasks], "retired_tasks": retired,
                 "changed_tasks": changes, "semantic_balance_seed": BALANCE_SEED,
                 "semantic_permutations": permutations,
                 "task_fingerprints": {t["id"]: fingerprint(t) for t in tasks},
                 "original_source_files_sha256": {str(p.relative_to(SOURCE)).replace("\\", "/"): digest(p.read_bytes())
                                                  for p in sorted(SOURCE.rglob("*")) if p.is_file()}}
    planned["migration.json"] = encoded(migration)
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    manifest.update({"name": "GBFSBench MV-Rad v1.1", "version": RELEASE, "release_date": DATE,
                     "description": "Corrected 290-task release with explicit missingness, ranking, distance and semantic contracts; visualization tasks retired.",
                     "tasks": {"total": len(tasks), "counts_by_category": dict(Counter(t["category"] for t in tasks)),
                               "counts_by_grader": dict(Counter(t["grader"] for t in tasks)),
                               "semantic_answer_positions": dict(Counter(t["expected"] for t in tasks if t["category"] == "semantics")),
                               "sha256": digest(task_bytes)},
                     "source_release": "../gbfs_mv_rad_v1", "source_tasks_sha256": digest(original_bytes),
                     "migration": "migration.json", "validation_report": "validation_report.json",
                     "model_evaluation_status": "not_run_for_v1_1",
                     "grading_contract": {"expected_null": "Only an explicitly returned answer:null matches; missing result, missing answer, exception, string null and NaN must fail.",
                                          "numeric_tolerance": "Absolute tolerance recorded per task; no relative tolerance.",
                                          "exact_integer": "Integral numeric equality, not truncation of fractional values.",
                                          "task_identity": "version plus task fingerprint; never resume changed tasks by ID alone."}})
    manifest["system"]["notes"].append("v1.1 normalizes system_information.time_zone to timezone; see snapshot normalization.json.")
    planned["manifest.json"] = encoded(manifest)
    planned["README.md"] = ("""# GBFSBench MV-Rad v1.1

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
""").encode()
    return planned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated bytes without writing")
    parser.add_argument("--overwrite", action="store_true", help="Replace only named generated v1.1 files")
    args = parser.parse_args()
    planned = build()
    differences = []
    for relative, content in planned.items():
        path = DEST / relative
        if path.exists() and path.read_bytes() == content:
            continue
        differences.append(relative)
        if args.check:
            continue
        if path.exists() and not args.overwrite:
            raise FileExistsError(f"Generated file differs: {path}; use --overwrite for this v1.1 output only")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(json.dumps({"version": RELEASE, "generated_files": len(planned),
                      "check_pass": not differences if args.check else True,
                      "differing_or_written_files": differences}, indent=2))
    return 1 if args.check and differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
