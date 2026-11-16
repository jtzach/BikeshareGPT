"""Offline official-schema check for the normalized v1.1 snapshot."""
import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks/gbfs_mv_rad_v1_1"


def validate():
    reports = []
    for schema_path in sorted((ROOT / "validation/gbfs_v2_3_schemas").glob("*.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        names = [schema_path.name, "gbfs_source.json"] if schema_path.name == "gbfs.json" else [schema_path.name]
        for name in names:
            path = DATASET / "snapshots/mv_rad" / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            errors = [{"path": "/".join(map(str, e.absolute_path)), "message": e.message, "validator": e.validator}
                      for e in Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(payload)]
            expected_local = name == "gbfs.json" and len(errors) == 8 and all(
                e["validator"] == "format" and e["path"].endswith("/url") for e in errors)
            reports.append({"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
                            "schema_pass": not errors, "expected_offline_url_deviation": expected_local, "errors": errors})
    return {"dataset_version": "1.1.0", "validation_date": "2026-11-16",
            "official_schema_commit": "f8d605e6ea23620891cb5f67344af1bec62c5e78",
            "validator": "jsonschema Draft7Validator with FormatChecker",
            "scope": "Individual-file schemas, not a complete cross-file specification validator.",
            "summary": {"payloads": len(reports), "schema_pass": sum(r["schema_pass"] for r in reports),
                        "expected_local_discovery_deviations": sum(r["expected_offline_url_deviation"] for r in reports),
                        "unexpected_failures": sum(not r["schema_pass"] and not r["expected_offline_url_deviation"] for r in reports)},
            "payloads": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["unexpected_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
