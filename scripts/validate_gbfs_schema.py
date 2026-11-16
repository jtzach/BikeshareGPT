"""Check frozen endpoint payloads against pinned official GBFS 2.3 schemas.

Offline; never repairs source payloads. Install validation/schema_requirements.txt.
This checks individual JSON schemas, not all cross-file GBFS specification rules.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_COMMIT = "f8d605e6ea23620891cb5f67344af1bec62c5e78"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    schema_dir = ROOT / "validation/gbfs_v2_3_schemas"
    snapshot = ROOT / "benchmarks/gbfs_mv_rad_v1/snapshots/mv_rad"
    checks = []
    hashes = {}
    for schema_path in sorted(schema_dir.glob("*.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        hashes[schema_path.name] = sha256(schema_path)
        names = [schema_path.name]
        if schema_path.name == "gbfs.json":
            names.append("gbfs_source.json")
        for name in names:
            data_path = snapshot / name
            payload = json.loads(data_path.read_text(encoding="utf-8"))
            validator = Draft7Validator(schema, format_checker=FormatChecker())
            errors = [{"path": "/".join(map(str, error.absolute_path)),
                       "message": error.message, "validator": error.validator}
                      for error in validator.iter_errors(payload)]
            checks.append({
                "file": name, "input_sha256": sha256(data_path),
                "schema": schema_path.name, "schema_pass": not errors,
                "errors": errors,
                "interpretation": (
                    "Derived offline discovery intentionally uses relative URLs; URI-format failures are expected."
                    if name == "gbfs.json" else
                    "Missing required timezone field; source has nonstandard time_zone. Preserved unchanged."
                    if name == "system_information.json" and errors else
                    "No individual-schema violations detected; this does not establish complete GBFS conformance."
                ),
            })
    return {
        "validation_date": "2026-11-16", "gbfs_version": "2.3",
        "schema_repository": "https://github.com/MobilityData/gbfs-json-schema",
        "schema_commit": SCHEMA_COMMIT,
        "schema_directory_url": "https://github.com/MobilityData/gbfs-json-schema/tree/" + SCHEMA_COMMIT + "/v2.3",
        "schema_license": "Apache-2.0 (unmodified upstream LICENSE included)",
        "schema_hashes_sha256": hashes,
        "validator": "jsonschema Draft7Validator with FormatChecker",
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "validator_script_sha256": sha256(Path(__file__)),
        "summary": {"payloads_checked": len(checks), "schema_pass": sum(c["schema_pass"] for c in checks),
                    "schema_fail": sum(not c["schema_pass"] for c in checks)},
        "limits": ["Checks each payload independently; conditional relationships across endpoints are not fully checked.",
                   "Schemas and payloads are preserved, not modified to force validation to pass.",
                   "This is a new audit, not evidence of original acquisition or historical validation."],
        "payloads": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write report to a new file; existing files are not overwritten")
    args = parser.parse_args()
    report = run()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps(report["summary"], indent=2))
    # The report deliberately contains known legacy failures. Success means the
    # audit completed, not that all payloads conform to the schema.


if __name__ == "__main__":
    main()
