"""Independently validate corrected v1.1 references and preservation contracts.

Offline and standard-library only. Snapshot arithmetic reuses the earlier
independent raw-JSON audit, not the builder, production grader or model outputs.
Changed missing-value/aggregation rules are calculated separately here.
Semantic meaning is source-grounded review plus option-preservation checking;
Python does not prove natural-language truth or independent human validation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "benchmarks/gbfs_mv_rad_v1_1"
ORIGINAL = ROOT / "benchmarks/gbfs_mv_rad_v1"
SNAPSHOT = BUNDLE / "snapshots/mv_rad"
SPEC_URL = "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson"
module_spec = importlib.util.spec_from_file_location("v1_independent_reference_audit", ROOT / "scripts/validate_references.py")
legacy = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(legacy)
legacy.SNAPSHOT = SNAPSHOT
legacy.BUNDLE = BUNDLE


def strict_read(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def agrees(task, calculated):
    expected = task["expected"]
    if expected is None:
        return calculated is None
    if task["grader"] == "numeric":
        return (isinstance(calculated, (int, float)) and not isinstance(calculated, bool)
                and math.isfinite(calculated) and math.isfinite(expected)
                and abs(calculated - expected) <= task["tolerance"])
    if task["grader"] == "set":
        return isinstance(calculated, list) and Counter(calculated) == Counter(expected)
    if (isinstance(expected, (int, float)) and not isinstance(expected, bool)
            and isinstance(calculated, (int, float)) and not isinstance(calculated, bool)):
        return math.isfinite(expected) and math.isfinite(calculated) and calculated == expected
    return type(calculated) is type(expected) and calculated == expected


class IndependentV11(legacy.Audit):
    def __init__(self):
        super().__init__()
        self.original = {t["id"]: t for t in [json.loads(line) for line in (ORIGINAL / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]}

    def record(self, task, value, evidence, *, issues=None, details=None, proposal=None,
               status=None, sources=None):
        # The old audit's warnings describe v1 wording. Version-specific query
        # contracts are checked separately below; arithmetic agreement is not a
        # blanket claim that natural-language wording was formally proved.
        self.records.append({"id": task["id"], "category": task["category"],
                             "reference_matches": agrees(task, value),
                             "expected": task["expected"], "independent_value": value,
                             "method": evidence, "details": details or {},
                             "source_locators": sources or []})

    def retrieval(self, task):
        if task["id"] == "mv_rad_ret_003_timezone":
            return self.record(task, self.data("system_information")["timezone"],
                               "Read normalized /data/timezone from system_information.json.")
        return super().retrieval(task)

    def synthesis(self, task):
        n = int(task["id"].split("_")[3])
        positive_ids = [sid for sid in self.c if self.c[sid] > 0]
        if n == 10:
            return self.record(task, statistics.fmean(self.b[sid] / self.c[sid] for sid in positive_ids),
                               "Mean of individual ratios over reported positive-capacity stations.",
                               details={"eligible_count": len(positive_ids), "excluded_count": len(self.info) - len(positive_ids)})
        if n == 11:
            numerator = sum(self.b[sid] for sid in positive_ids)
            denominator = sum(self.c[sid] for sid in positive_ids)
            return self.record(task, 100 * numerator / denominator,
                               "Independent ratio of sums over the same positive-capacity population.",
                               details={"numerator_bikes": numerator, "denominator_capacity": denominator,
                                        "eligible_count": len(positive_ids), "excluded_count": len(self.info) - len(positive_ids)})
        if n == 12:
            return self.record(task, sum(self.b.values()),
                               "Sum station-status bike counts once; derived rows do not add new vehicles.")
        if n in (62, 67):
            region = "775" if n == 62 else "949"
            ids = [sid for sid, station in self.info.items() if station["region_id"] == region]
            missing = [sid for sid in ids if sid not in self.c]
            value = None if missing else sum(self.c[sid] for sid in ids)
            return self.record(task, value, "Total is unknown if any regional capacity is missing; an empty reported sum is not assumed to be total capacity.",
                               details={"region_id": region, "station_count": len(ids), "capacity_present": len(ids) - len(missing), "missing_ids": missing})
        if n in (64, 69):
            region = "775" if n == 64 else "949"
            ids = [sid for sid in positive_ids if self.info[sid]["region_id"] == region]
            value = statistics.fmean(self.b[sid] / self.c[sid] for sid in ids) if ids else None
            return self.record(task, value, "Mean of eligible ratios, or explicit null when no eligible station exists.",
                               details={"region_id": region, "eligible_station_ids": ids, "eligible_count": len(ids)})
        return super().synthesis(task)

    def semantics(self, task):
        old = self.original[task["id"]]
        review = self.semantic[task["id"]]
        original_correct = old["meta"]["choices"][review["reviewed_choice"]]
        corrected = {
            "sem_006": "The number of vehicles reported available at the station; rental availability additionally requires is_renting=true.",
            "sem_007": "The number of empty functional docks; return availability additionally requires is_returning=true.",
            "sem_054": "The POSIX time when the station last reported its status to the operator backend.",
        }
        correct_text = corrected.get(task["id"], original_correct)
        new_choices = task["meta"]["choices"]
        matching = [letter for letter, text in new_choices.items() if text == correct_text]
        expected_contents = list(old["meta"]["choices"].values())
        expected_contents[expected_contents.index(original_correct)] = correct_text
        preserved = Counter(expected_contents) == Counter(new_choices.values())
        source_query_bound = hashlib.sha256(old["query"].encode()).hexdigest() == review["query_sha256"]
        rendered = "\n".join(f"{letter}. {new_choices[letter]}" for letter in "ABCD")
        query_consistent = "Choices:\n" + rendered + "\n\nAnswer with a single letter (A/B/C/D)." in task["query"]
        letter = matching[0] if len(matching) == 1 and preserved and query_consistent and source_query_bound else None
        self.record(task, letter, "Carry forward source-reviewed answer meaning, check all option texts/permutation and the three explicit GBFS definition corrections.",
                    details={"correct_option_text": correct_text, "all_option_contents_preserved_or_documented": preserved,
                             "rendered_choices_match_metadata": query_consistent,
                             "original_semantic_review_bound_to_source_query": source_query_bound,
                             "definition_revised": task["id"] in corrected,
                             "review_not_independent_human_annotation": True},
                    sources=review["sources"])


def validate():
    tasks_path = BUNDLE / "tasks.jsonl"
    tasks = [json.loads(line, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
             for line in tasks_path.read_text(encoding="utf-8").splitlines()]
    migration = strict_read(BUNDLE / "migration.json")
    manifest = strict_read(BUNDLE / "manifest.json")
    audit = IndependentV11()
    checks = []

    def check(name, passed, details=None):
        item = {"check": name, "passed": bool(passed)}
        if details is not None:
            item["details"] = details
        checks.append(item)

    check("290 unique active tasks", len(tasks) == len({t["id"] for t in tasks}) == 290)
    check("track counts", Counter(t["category"] for t in tasks) == {"semantics": 100, "retrieval": 100, "synthesis": 90})
    check("25 semantic answers in each position", Counter(t["expected"] for t in tasks if t["category"] == "semantics") == dict.fromkeys("ABCD", 25))
    check("no artifact-existence tasks", all(t["grader"] != "artifact_exists" for t in tasks))
    retired = {t["id"] for t in migration["retired_tasks"]}
    expected_retired = {tid for tid, task in audit.original.items() if task["grader"] == "artifact_exists"}
    check("exactly ten original plot tasks retired", retired == expected_retired and len(retired) == 10)
    check("active IDs and retired IDs partition v1", {t["id"] for t in tasks} | retired == set(audit.original)
          and not ({t["id"] for t in tasks} & retired))
    check("manifest task hash", manifest["tasks"]["sha256"] == sha256(tasks_path) == migration["target_tasks_sha256"])
    check("v1 tasks unchanged", sha256(ORIGINAL / "tasks.jsonl") == migration["source_tasks_sha256"])
    check("every v1 source byte preserved", all(sha256(ORIGINAL / name) == value for name, value in migration["original_source_files_sha256"].items()))
    check("every active task fingerprint matches", all(migration["task_fingerprints"][t["id"]] == task_hash(t) for t in tasks))
    source_system = json.loads((ORIGINAL / "snapshots/mv_rad/system_information.json").read_text(encoding="utf-8"))
    normalized = strict_read(SNAPSHOT / "system_information.json")
    restored = json.loads(json.dumps(normalized))
    restored["data"]["time_zone"] = restored["data"].pop("timezone")
    check("timezone normalization is value-preserving only", restored == source_system)
    for name in (p.name for p in (ORIGINAL / "snapshots/mv_rad").glob("*.json") if p.name not in {"manifest.json", "system_information.json"}):
        check("unchanged endpoint: " + name, (ORIGINAL / "snapshots/mv_rad" / name).read_bytes() == (SNAPSHOT / name).read_bytes())
    for line in (SNAPSHOT / "SHA256SUMS.txt").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        check("snapshot checksum: " + name, sha256(SNAPSHOT / name) == expected)
    audited_v1 = strict_read(ROOT / "validation/reference_validation.json")
    check("v1 audit input hashes remain unchanged", all(sha256(ROOT / name) == value
          for name, value in audited_v1["inputs_sha256"].items()))
    problem_ids = {t["id"] for t in audited_v1["tasks"] if t["status"] in {"mismatch", "ambiguous_or_underspecified"}}
    changed_ids = {t["id"] for t in migration["changed_tasks"]}
    check("all 27 non-plot audit findings have explicit changes", problem_ids <= changed_ids and len(problem_ids) == 27)
    for task in tasks:
        meta = task["meta"]
        query = task["query"]
        check("version metadata: " + task["id"], meta["dataset_version"] == "1.1.0")
        if meta.get("tie_break"):
            check("declared tie rule: " + task["id"], "ascending lexicographic string order" in query)
        if meta.get("earth_radius_m"):
            check("declared sphere radius: " + task["id"], meta["earth_radius_m"] == 6371000 and "6371000 meters" in query)
        if task["expected"] is None:
            check("explicit null contract: " + task["id"], "null (Python None)" in query and task["grader"] == "exact"
                  and meta.get("null_requires_explicit_answer") is True)
        getattr(audit, task["category"])(task)
    mismatches = [r["id"] for r in audit.records if not r["reference_matches"]]
    check("all 290 references supported under explicit contracts", not mismatches, mismatches)
    nullable = [t["id"] for t in tasks if t["expected"] is None]
    check("only the two unsupported targets become null", set(nullable) == {
        "mv_rad_syn_067_region_949_total_capacity", "mv_rad_syn_069_region_949_avg_utilization"})
    return {
        "dataset_version": "1.1.0", "validation_date": "2026-11-16",
        "method": "Independent standard-library snapshot calculation plus source-grounded semantic meaning/permutation review.",
        "not_independent_human_validation": True, "no_model_evaluation_performed": True,
        "summary": {"active_tasks": len(tasks), "references_matching": len(audit.records) - len(mismatches),
                    "references_mismatching": len(mismatches), "retired_plot_tasks": len(retired),
                    "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks)},
        "by_category": {cat: {"total": sum(r["category"] == cat for r in audit.records),
                              "matches": sum(r["category"] == cat and r["reference_matches"] for r in audit.records)}
                        for cat in ("semantics", "retrieval", "synthesis")},
        "inputs_sha256": {"tasks.jsonl": sha256(tasks_path), "migration.json": sha256(BUNDLE / "migration.json"),
                          "v1_semantic_review": sha256(ROOT / "validation/semantic_review_v1.json"),
                          "prior_independent_validator": sha256(ROOT / "scripts/validate_references.py")},
        "validator_sha256": sha256(Path(__file__)),
        "limits": ["Source observation truth and original acquisition history are not independently verified.",
                   "Semantic correctness is documented model-assisted/source-grounded review, not proof by Python or independent human annotation.",
                   "Explicit contracts resolve the identified ambiguities; this does not prove that no other linguistic ambiguity can exist.",
                   "Null-target execution handling and graders require separate software regression tests.",
                   "No v1 model scores are claimed as corrected v1.1 model performance."],
        "checks": checks, "tasks": audit.records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write to a new report path; refuses to overwrite")
    args = parser.parse_args()
    report = validate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps(report["summary"], indent=2))
    return 0 if all(c["passed"] for c in report["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
