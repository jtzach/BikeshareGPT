"""Audit the frozen release using the Python standard library and no network.

This reads saved model outputs; it never executes model-generated code, calls a
model, or rewrites the historical predictions/grades. The artifact reconciliation
is an explicitly separate existence-only diagnostic, not a new benchmark run.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relocated_artifact(task_dir, reference):
    """Map a recorded artifact to its relocated release task directory only."""
    if not isinstance(reference, str):
        return None
    normalized = reference.replace("\\", "/")
    marker = "/artifacts/" + task_dir.name + "/"
    if marker in normalized:
        relative = normalized.split(marker, 1)[1]
    elif "/" not in normalized:
        relative = normalized
    else:
        return None
    candidate = (task_dir / relative).resolve()
    if not candidate.is_relative_to(task_dir.resolve()):
        return None
    return candidate


def audit(root):
    bundle = root / "benchmarks" / "gbfs_mv_rad_v1"
    snapshot = bundle / "snapshots" / "mv_rad"
    tasks = jsonl(bundle / "tasks.jsonl")
    ids = [row["id"] for row in tasks]
    by_id = {row["id"]: row for row in tasks}
    checks = []

    def check(name, passed, detail=None):
        row = {"check": name, "passed": bool(passed)}
        if detail is not None:
            row["detail"] = detail
        checks.append(row)

    check("300 unique task IDs", len(tasks) == len(set(ids)) == 300)
    categories = dict(Counter(row["category"] for row in tasks))
    check("100 tasks per track", categories == {"semantics": 100, "retrieval": 100, "synthesis": 100})
    graders = dict(Counter(row["grader"] for row in tasks))
    semantics_labels = {label: 0 for label in "ABCD"}
    semantics_labels.update(Counter(row["expected"] for row in tasks if row["category"] == "semantics"))
    check("10 artifact-production tasks", graders.get("artifact_exists") == 10)
    for line in (snapshot / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        path = snapshot / name.strip().lstrip("*")
        check("snapshot checksum: " + path.name, path.is_file() and sha256(path) == expected)

    def payload(name):
        return json.loads((snapshot / (name + ".json")).read_text(encoding="utf-8"))

    counts = {
        "stations": len(payload("station_information")["data"]["stations"]),
        "station_status_rows": len(payload("station_status")["data"]["stations"]),
        "vehicle_types": len(payload("vehicle_types")["data"]["vehicle_types"]),
        "derived_free_bike_rows": len(payload("free_bike_status")["data"]["bikes"]),
        "regions": len(payload("system_regions")["data"]["regions"]),
    }
    check("snapshot row counts", counts == {"stations": 64, "station_status_rows": 64, "vehicle_types": 11, "derived_free_bike_rows": 335, "regions": 2})
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    endpoint_timestamps = {}
    for path in sorted(snapshot.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8")).get("last_updated")
        if value is not None:
            endpoint_timestamps[path.name] = {"last_updated": value, "utc": datetime.fromtimestamp(value, timezone.utc).isoformat()}
    shared_tasks = jsonl(root / "outputs" / "shared" / "benchmark" / "tasks.jsonl")
    check("saved-run tasks match release tasks", tasks == shared_tasks)
    models = []
    for model_dir in sorted((root / "outputs" / "models").iterdir()):
        if not model_dir.is_dir():
            continue
        grades = jsonl(model_dir / "predictions" / "grades.jsonl")
        predictions = jsonl(model_dir / "predictions" / "predictions.jsonl")
        pred_map = {row["task_id"]: row for row in predictions}
        check(model_dir.name + ": complete grade IDs", len(grades) == 300 and {row["task_id"] for row in grades} == set(ids))
        check(model_dir.name + ": complete prediction IDs", len(predictions) == 300 and set(pred_map) == set(ids))
        historical_correct = sum(bool(row["correct"]) for row in grades)
        summary = json.loads((model_dir / "predictions" / "summary.json").read_text(encoding="utf-8"))
        check(model_dir.name + ": summary matches stored grades", abs(summary["overall"]["accuracy"] - historical_correct / 300) < 1e-12)
        plot_rows = []
        nonvisual = []
        for grade in grades:
            task_id = grade["task_id"]
            if by_id[task_id]["grader"] != "artifact_exists":
                nonvisual.append(grade)
                continue
            prediction = pred_map[task_id]
            result = prediction.get("result_obj")
            references = result.get("artifacts", []) if isinstance(result, dict) else []
            task_dir = model_dir / "artifacts" / task_id
            resolved = [relocated_artifact(task_dir, reference) for reference in references]
            exists = bool(references) and all(path is not None and path.is_file() for path in resolved)
            plot_rows.append({
                "task_id": task_id,
                "historical_grade": bool(grade["correct"]),
                "historical_reason": grade["reason"],
                "exec_success": bool(prediction.get("exec_success")),
                "all_referenced_files_present": exists,
                "relocated_files": [path.relative_to(root).as_posix() for path in resolved if path is not None],
                "saved_additional_info": result.get("additional_info") if isinstance(result, dict) else None,
            })
        nonvisual_correct = sum(bool(row["correct"]) for row in nonvisual)
        present_count = sum(row["all_referenced_files_present"] for row in plot_rows)
        models.append({
            "model": model_dir.name,
            "historical_correct": historical_correct,
            "historical_total": len(grades),
            "historical_accuracy": historical_correct / len(grades),
            "nonvisual_correct": nonvisual_correct,
            "nonvisual_total": len(nonvisual),
            "nonvisual_accuracy": nonvisual_correct / len(nonvisual),
            "artifact_tasks_with_referenced_files": present_count,
            "existence_only_reconciliation_correct": nonvisual_correct + present_count,
            "existence_only_reconciliation_accuracy": (nonvisual_correct + present_count) / len(grades),
            "artifact_diagnostics": plot_rows,
        })

    assets = []
    for directory in (root / "benchmarks", root / "outputs", root / "data"):
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                assets.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {
        "audit_schema_version": "1.0",
        "scope": "Offline checks of the submitted frozen release; no generated code executed or model calls made.",
        "interpretation": "Existence-only reconciliation is diagnostic. It neither modifies historical grades nor verifies chart semantics or authorizes replacement paper results.",
        "source_url": manifest["source_auto_discovery_url"],
        "frozen_last_updated_utc": datetime.fromtimestamp(manifest["frozen_last_updated"], timezone.utc).isoformat(),
        "timestamp_caveat": "This is the feed's last_updated value, not independently established collection time.",
        "endpoint_update_timestamps": endpoint_timestamps,
        "atomic_snapshot_caveat": "Endpoint update timestamps differ; the bundle must not be represented as an atomic observation of one instant.",
        "semantics_answer_labels": semantics_labels,
        "always_A_semantics_accuracy": semantics_labels["A"] / categories["semantics"],
        "source_license_id_in_frozen_system_information": payload("system_information")["data"].get("license_id"),
        "snapshot_counts": counts, "category_counts": categories, "grader_counts": graders,
        "checks": checks, "passed": all(row["passed"] for row in checks),
        "models": models, "asset_manifest": assets,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Optional new JSON report path; existing files are never overwritten.")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
        print("Audit written to " + str(args.output))
    else:
        print(serialized, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
