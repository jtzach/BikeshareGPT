"""Check a reverse-engineered reconstruction of the frozen 335-row augmentation.

This recipe was inferred on 2026-11-16 from the archived files. It is NOT a
recovered historical creation script and does not establish who generated the
records, when, or with which original program. It is scoped to this frozen
release, not intended as a model of real vehicle positions or battery states.

The default operation (also --check) reads files and compares records only.
--output writes a separate reconstructed JSON file in exclusive-create mode.
Original snapshot files are never rewritten. No external dependencies/network.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


def canonical_hash(value):
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def reconstruct(station_information, station_status, vehicle_types):
    info = {str(row["station_id"]): row for row in station_information["data"]["stations"]}
    types = {str(row["vehicle_type_id"]): row for row in vehicle_types["data"]["vehicle_types"]}
    bikes = []
    for station in station_status["data"]["stations"]:
        station_id = str(station["station_id"])
        location = info[station_id]
        index = 0
        # Preserve the archived station and vehicle-type order.
        for type_count in station.get("vehicle_types_available", []):
            type_id = str(type_count["vehicle_type_id"])
            vehicle_type = types[type_id]
            for _ in range(type_count["count"]):
                index += 1
                record = {
                    "bike_id": f"{station_id}_bike_{index}",
                    "is_reserved": False,
                    "is_disabled": False,
                    "lat": round(location["lat"] + ((index % 7) - 3) * 0.00003, 6),
                    "lon": round(location["lon"] + ((index % 5) - 2) * 0.00003, 6),
                    "vehicle_type_id": type_id,
                    "station_id": station_id,
                }
                if vehicle_type["propulsion_type"] == "electric_assist":
                    # Observed electric records have within-station index 1..4.
                    # This interpolation matches them; it is not evidence for
                    # an original battery formula outside that observed range.
                    fuel = 1 - 0.07 * index
                    record["current_fuel_percent"] = round(fuel, 2)
                    record["current_range_meters"] = int(vehicle_type["max_range_meters"] * fuel)
                bikes.append(record)
    return {
        "last_updated": station_status["last_updated"],
        "ttl": station_status["ttl"],
        "version": station_status["version"],
        "data": {"bikes": bikes},
    }


def verify(root):
    snapshot = root / "benchmarks" / "gbfs_mv_rad_v1" / "snapshots" / "mv_rad"
    names = ["station_information.json", "station_status.json", "vehicle_types.json", "free_bike_status.json"]
    inputs = {}
    hashes = {}
    for name in names:
        path = snapshot / name
        raw = path.read_bytes()
        inputs[name] = json.loads(raw)
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
    reconstructed = reconstruct(inputs[names[0]], inputs[names[1]], inputs[names[2]])
    expected = inputs["free_bike_status.json"]
    actual_rows = reconstructed["data"]["bikes"]
    expected_rows = expected["data"]["bikes"]
    mismatches = [
        index for index, (actual, archived) in enumerate(zip(actual_rows, expected_rows))
        if actual != archived
    ]
    expected_counts = Counter(str(row["station_id"]) for row in expected_rows)
    station_counts_match = all(
        expected_counts[str(row["station_id"])] == row["num_bikes_available"]
        for row in inputs["station_status.json"]["data"]["stations"]
    )
    report = {
        "method_status": "Reverse-engineered on 2026-11-16; not recovered historical code.",
        "scope": "Frozen MV-Rad v1 augmentation only; equality does not establish historical provenance.",
        "input_sha256": hashes,
        "archived_row_count": len(expected_rows),
        "reconstructed_row_count": len(actual_rows),
        "same_order_and_records": actual_rows == expected_rows,
        "whole_json_object_equal": reconstructed == expected,
        "mismatch_zero_based_indices": mismatches,
        "archived_rows_sha256_canonical_json": canonical_hash(expected_rows),
        "reconstructed_rows_sha256_canonical_json": canonical_hash(actual_rows),
        "per_station_derived_counts_equal_available_bikes": station_counts_match,
    }
    return report, reconstructed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Read-only comparison (the default).")
    parser.add_argument("--output", type=Path, help="Optional new JSON path; refuses to overwrite existing files.")
    args = parser.parse_args()
    report, reconstructed = verify(args.root.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(reconstructed, output, indent=2, ensure_ascii=False)
            output.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if report["whole_json_object_equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
