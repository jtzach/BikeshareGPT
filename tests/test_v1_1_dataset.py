"""Meaningful regression checks for corrected references and frozen-v1 retention."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tasks():
    return [json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            for line in (ROOT / "benchmarks/gbfs_mv_rad_v1_1/tasks.jsonl").read_text(encoding="utf-8").splitlines()]


def test_complete_corrected_release_passes_independent_reference_and_contract_checks():
    report = load_script("validate_v1_1").validate()
    assert report["summary"]["active_tasks"] == 290
    assert report["summary"]["references_matching"] == 290
    assert all(row["passed"] for row in report["checks"])


def test_independent_snapshot_recalculation_rejects_a_corrupted_reference():
    module = load_script("validate_v1_1")
    task = deepcopy(next(t for t in tasks() if t["id"] == "mv_rad_syn_001_total_bikes"))
    task["expected"] += 1
    audit = module.IndependentV11()
    audit.synthesis(task)
    assert audit.records[0]["independent_value"] == 335
    assert audit.records[0]["reference_matches"] is False


def test_semantic_meaning_check_rejects_a_wrong_letter_after_permutation():
    module = load_script("validate_v1_1")
    task = deepcopy(next(t for t in tasks() if t["id"] == "sem_006"))
    task["expected"] = next(letter for letter in "ABCD" if letter != task["expected"])
    audit = module.IndependentV11()
    audit.semantics(task)
    assert audit.records[0]["reference_matches"] is False


def test_unknown_capacity_and_empty_utilization_are_null_not_zero_or_nan():
    module = load_script("validate_v1_1")
    for number in ("067", "069"):
        task = deepcopy(next(t for t in tasks() if t["id"].startswith("mv_rad_syn_" + number + "_")))
        audit = module.IndependentV11()
        audit.synthesis(task)
        assert task["expected"] is None
        assert audit.records[0]["independent_value"] is None
        for wrong in (0, "null", float("nan")):
            corrupted = deepcopy(task)
            corrupted["expected"] = wrong
            assert not module.agrees(corrupted, None)


def test_builder_is_deterministic_and_does_not_write_originals():
    module = load_script("build_v1_1")
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in module.SOURCE.rglob("*") if p.is_file()}
    generated = module.build()
    assert generated == module.build()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in originals.items())
    assert all((module.DEST / name).read_bytes() == content for name, content in generated.items())


def test_reference_equality_does_not_truncate_fractional_values_or_accept_boolean_counts():
    module = load_script("validate_v1_1")
    task = {"expected": 64, "grader": "exact", "tolerance": 0}
    assert module.agrees(task, 64.0)
    assert not module.agrees(task, 64.9)
    assert not module.agrees({**task, "expected": 1}, True)
