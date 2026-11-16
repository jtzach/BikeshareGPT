"""Independent, offline audit of the frozen MV-Rad task reference answers.

Uses only the Python standard library, raw snapshot JSON, and a separately
recorded semantic review. Does not import benchmark generators or graders,
read model predictions, call models, or execute saved model-generated code.
Run from any directory; the default prints a summary without writing files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "benchmarks/gbfs_mv_rad_v1"
SNAPSHOT = BUNDLE / "snapshots/mv_rad"
MATCH = "independently_matches"
MISMATCH = "mismatch"
AMBIGUOUS = "ambiguous_or_underspecified"
UNVERIFIABLE = "not_verifiable"
RADIUS = 6_371_000.0


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    """Keep the report strict JSON even though the source includes NaN."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_source_value": str(value)}
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def central_angle(a, b):
    """atan2(norm(cross(u,v)), dot(u,v)); independent of repo haversine."""
    def unit(point):
        lat, lon = map(math.radians, point)
        return math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)
    u, v = unit(a), unit(b)
    cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    return math.atan2(math.sqrt(sum(c*c for c in cross)), sum(x*y for x, y in zip(u, v)))


def matches(task, calculated):
    expected = task["expected"]
    if isinstance(expected, float) and not math.isfinite(expected):
        return False
    if task["grader"] == "numeric":
        return (isinstance(calculated, (float, int)) and not isinstance(calculated, bool)
                and math.isfinite(calculated)
                and abs(calculated-expected) <= task.get("tolerance", 0))
    if isinstance(calculated, list) and "order does not matter" in task["query"]:
        return Counter(calculated) == Counter(expected)
    return type(calculated) is type(expected) and calculated == expected or (
        isinstance(calculated, (int, float)) and not isinstance(calculated, bool)
        and isinstance(expected, (int, float)) and not isinstance(expected, bool)
        and calculated == expected)


class Audit:
    def __init__(self):
        self.raw = {p.stem: read(p) for p in SNAPSHOT.glob("*.json")}
        self.info = {s["station_id"]: s for s in self.data("station_information")["stations"]}
        self.status = {s["station_id"]: s for s in self.data("station_status")["stations"]}
        self.types = {t["vehicle_type_id"]: t for t in self.data("vehicle_types")["vehicle_types"]}
        self.bikes = self.data("free_bike_status")["bikes"]
        self.free = Counter(b["station_id"] for b in self.bikes)
        self.electric = {k for k, t in self.types.items() if t["propulsion_type"] == "electric_assist"}
        self.human = {k for k, t in self.types.items() if t["propulsion_type"] == "human"}
        self.cargo = {k for k, t in self.types.items() if t["form_factor"] == "cargo_bicycle"}
        self.b = {sid: s["num_bikes_available"] for sid, s in self.status.items()}
        self.d = {sid: s["num_docks_available"] for sid, s in self.status.items()}
        self.c = {sid: s["capacity"] for sid, s in self.info.items() if s.get("capacity") is not None}
        self.u = {sid: self.b[sid]/cap for sid, cap in self.c.items() if cap > 0}
        self.distinct = {sid: len({v["vehicle_type_id"] for v in s["vehicle_types_available"]
                                 if v["count"] > 0}) for sid, s in self.status.items()}
        self.semantic = {s["id"]: s for s in read(ROOT/"validation/semantic_review_v1.json")["tasks"]}
        self.records = []

    def data(self, name):
        return self.raw[name]["data"]

    def type_counts(self, ids):
        return {sid: sum(v["count"] for v in s["vehicle_types_available"] if v["vehicle_type_id"] in ids)
                for sid, s in self.status.items()}

    def point(self, sid):
        return self.info[sid]["lat"], self.info[sid]["lon"]

    def record(self, task, value, evidence, *, issues=None, details=None, proposal=None,
               status=None, sources=None):
        agreement = matches(task, value) if task["grader"] != "artifact_exists" else None
        rec = {"id": task["id"], "category": task["category"],
               "status": status or (AMBIGUOUS if issues else MATCH if agreement else MISMATCH),
               "source_reference": (None if isinstance(task["expected"], float)
                                    and not math.isfinite(task["expected"]) else task["expected"]),
               "source_reference_nonfinite": (str(task["expected"]) if isinstance(task["expected"], float)
                                              and not math.isfinite(task["expected"]) else None),
               "independent_value": value,
               "reference_matches_under_stated_assumptions": agreement,
               "method": evidence, "issues": issues or [], "details": details or {},
               "proposal_for_future_version": proposal, "source_locators": sources or []}
        self.records.append(rec)

    def rank(self, task, values, k, descending=True, issues=None):
        ordered = sorted(values, key=lambda sid: ((-1 if descending else 1)*values[sid], sid))
        selected = ordered[:k]
        groups = defaultdict(list)
        for sid in ordered:
            groups[values[sid]].append(sid)
        tied = [{"value": v, "station_ids": ids} for v, ids in groups.items()
                if len(ids) > 1 and any(sid in selected for sid in ids)]
        problems = list(issues or [])
        if tied:
            problems.append("No tie-breaking rule; multiple answers satisfy the requested ranking.")
        expected = task["expected"] if isinstance(task["expected"], list) else [task["expected"]]
        valid = (len(expected) == k and len(set(expected)) == k and all(s in values for s in expected)
                 and [values[s] for s in expected] == [values[s] for s in selected])
        self.record(task, selected if k > 1 else selected[0],
                    "Independently rank raw values; lexical station_id is an explicit proposed secondary key.",
                    issues=problems, status=MISMATCH if not valid else AMBIGUOUS if problems else MATCH,
                    details={"ranked_values": [{"station_id": s, "value": values[s]} for s in selected],
                             "tie_groups": tied, "published_answer_is_valid_tie_selection": valid},
                    proposal="Specify lexical station_id ascending as secondary key, or accept all valid tied answers."
                    if tied else None)

    def retrieval(self, t):
        n = int(t["id"].split("_")[3])
        system = self.data("system_information")
        feeds = self.data("gbfs")["en"]["feeds"]
        names = sorted(f["name"] for f in feeds)
        regions = self.data("system_regions")["regions"]
        plans = self.data("system_pricing_plans")["plans"]
        hours = self.data("system_hours")["rental_hours"][0]
        fields = ["name", "operator", "time_zone", "phone_number", "email", "feed_contact_email",
                  "license_id", "system_id", "language", "url"]
        evidence = "Direct raw-JSON field lookup or independently counted/filter-selected rows."
        detail = {}
        if n <= 10:
            key = fields[n-1]
            value = system[key]
            detail = {"json_pointer": "/data/"+key, "file": "system_information.json"}
            if n == 3:
                detail["schema_note"] = "Literal time_zone is present; standard GBFS 2.3 field is timezone."
        elif n <= 30:
            lookup = {11: len(self.data("gbfs")), 12: sorted(self.data("gbfs")), 13: len(feeds),
                      14: names, 15: len(regions), 16: sorted(r["name"] for r in regions),
                      17: len(plans), 18: plans[0]["plan_id"], 19: plans[0]["currency"],
                      20: plans[0]["price"], 21: sorted(hours["user_types"]), 22: sorted(hours["days"]),
                      23: hours["start_time"], 24: hours["end_time"],
                      25: next(r["region_id"] for r in regions if r["name"] == "MV-Rad"),
                      26: next(r["region_id"] for r in regions if r["name"] == "MV-Rad Scooter"),
                      27: "free_bike_status" in names, 28: "station_information" in names,
                      29: "vehicle_types" in names, 30: "system_alerts" in names}
            value = lookup[n]
            if n in (11, 12):
                detail = {"scope": "Derived local gbfs.json, not gbfs_source.json",
                          "original_discovery_languages": sorted(self.data("gbfs_source"))}
        elif n <= 38:
            value = {31: len(self.types), 32: sorted(self.types),
                     33: sorted({x["propulsion_type"] for x in self.types.values()}),
                     34: sorted({x["form_factor"] for x in self.types.values()}),
                     35: len(self.electric), 36: len(self.human),
                     37: sum(x["form_factor"] == "bicycle" for x in self.types.values()),
                     38: len(self.cargo)}[n]
        elif n <= 48:
            type_id = re.search(r"vehicle_type_id '([^']+)'", t["query"]).group(1)
            key = "name" if n <= 43 else {44: "propulsion_type", 45: "form_factor",
                    46: "rider_capacity", 47: "max_range_meters", 48: "max_range_meters"}[n]
            value = self.types[type_id][key]
            detail = {"file": "vehicle_types.json", "vehicle_type_id": type_id, "field": key}
        elif n <= 50:
            value = sorted(self.electric if n == 49 else self.human)
        elif n <= 90:
            sid = re.search(r"station_id '([^']+)'", t["query"]).group(1)
            value = (self.c[sid] if n <= 60 else self.info[sid]["short_name"] if n <= 70 else
                     self.b[sid] if n <= 80 else self.d[sid] if n <= 85 else self.free[sid])
            detail = {"station_id": sid, "derived_vehicle_records": n >= 86}
        elif n <= 96:
            value = {91: len(self.info), 92: sum(v == 0 for v in self.b.values()),
                     93: sum(v == 0 for v in self.d.values()),
                     94: sum(x.get("is_virtual_station", False) for x in self.info.values()),
                     95: sum(x["region_id"] == "775" for x in self.info.values()),
                     96: sum(x["region_id"] == "949" for x in self.info.values())}[n]
        elif n <= 99:
            return self.rank(t, {97: self.b, 98: self.d, 99: self.c}[n], 1,
                             issues=["Capacity is absent for station 582784416; ranking covers reported capacities only."]
                             if n == 99 else None)
        else:
            bike_id = re.search(r"bike_id '([^']+)'", t["query"]).group(1)
            value = next(b["station_id"] for b in self.bikes if b["bike_id"] == bike_id)
            detail = {"bike_id": bike_id, "derived_vehicle_records": True}
        self.record(t, value, evidence, details=detail)

    def synthesis(self, t):
        n = int(t["id"].split("_")[3])
        ids = list(self.info)
        b, d, c, u = self.b, self.d, self.c, self.u
        issues, detail, proposal, override = [], {}, None, None
        method = "Independent standard-library calculation on raw frozen snapshot records."
        electric, human, cargo = self.type_counts(self.electric), self.type_counts(self.human), self.type_counts(self.cargo)
        if n <= 20:
            value = {1: sum(b.values()), 2: sum(d.values()), 3: sum(c.values()),
                     4: statistics.mean(b.values()), 5: statistics.median(b.values()),
                     6: statistics.mean(d.values()), 7: statistics.median(d.values()),
                     8: 100*sum(v == 0 for v in b.values())/len(b),
                     9: 100*sum(v == 0 for v in d.values())/len(d),
                     10: statistics.mean(u.values()), 11: 100*sum(b.values())/sum(c.values()),
                     12: sum(b.values())+len(self.bikes), 13: len(self.bikes),
                     14: len(self.bikes)/len(ids),
                     15: sum(x["vehicle_type_id"] in self.electric for x in self.bikes),
                     16: sum(electric.values()), 17: sum(human.values()), 18: sum(cargo.values()),
                     19: sum(b[s] > d[s] for s in ids), 20: sum(b[s] == d[s] for s in ids)}[n]
            if n in (3, 10, 11):
                issues = ["Station 582784416 has no capacity field; missing-value handling is unspecified."]
                detail = {"capacity_present": len(c), "station_count": len(ids),
                          "capacity_sum_reported_only": sum(c.values()), "ratio_denominators_present": len(u)}
                proposal = "State that only reported positive capacities enter utilization; label sums as reported-capacity sums."
            if n == 12:
                issues = ["The requested sum is 670, but the term visible vehicles double-counts derived rows representing station bikes."]
                detail = {"station_bikes": sum(b.values()), "derived_rows": len(self.bikes),
                          "unique_represented_station_vehicles": sum(b.values())}
                proposal = "Ask for the sum of two record counts without claiming unique vehicles, or ask for 335 represented station vehicles."
        elif n in (21, 22, 23, 24, 25, 26, 33, 34, 35, 77, 78, 79):
            values = {21: b, 22: d, 23: c, 24: u, 25: b, 26: d,
                      33: {s: b[s] for s in ids if self.info[s]["region_id"] == "775"},
                      34: dict(self.free), 35: u, 77: electric, 78: human, 79: cargo}[n]
            if n in (23, 24, 35):
                issues.append("Missing capacity at station 582784416 is excluded; query does not state that policy.")
            return self.rank(t, values, 5 if n <= 26 else 3 if n <= 35 else 1,
                             descending=n not in (25, 26, 35), issues=issues)
        elif n <= 40:
            value = {27: sorted(s for s in ids if b[s] == 0), 28: sorted(s for s in ids if d[s] == 0),
                     29: sorted(s for s in c if c[s] > 15 and b[s] < 5),
                     30: sorted(self.electric), 31: sorted(self.human),
                     32: sorted(s for s in ids if self.info[s]["region_id"] == "949"),
                     36: sorted(s for s in ids if b[s] > 0 and self.free[s] == 0),
                     37: sorted(s for s in ids if b[s] == self.free[s]),
                     38: sorted(s for s in ids if self.distinct[s] > 1),
                     39: sorted(s for s in ids if cargo[s] > 0),
                     40: sorted(s for s in ids if electric[s] > 0)}[n]
            if n == 29:
                issues = ["Missing capacity at station 582784416 prevents deciding its eligibility; published answer excludes unknown values."]
                proposal = "Specify that records with missing capacity are excluded."
        elif n <= 50:
            sid1, sid2 = re.findall(r"station_id '([^']+)'", t["query"])
            angle = central_angle(self.point(sid1), self.point(sid2))
            value = angle*RADIUS
            issues = ["Great-circle distance requires a sphere radius; the question omits it."]
            detail = {"coordinate_order": "latitude, longitude; degrees", "station_ids": [sid1, sid2],
                      "coordinates": [self.point(sid1), self.point(sid2)], "radius_m": RADIUS,
                      "alternative_radius_m": 6371008.8, "alternative_distance_m": angle*6371008.8,
                      "radius_choice_difference_m": angle*8.8,
                      "published_numeric_tolerance": t["tolerance"]}
            method = "Spherical unit-vector cross/dot central angle times 6371000 m; not repo haversine code."
            proposal = "Specify sphere radius 6371000 m and absolute meter tolerance; avoid implying millimeter physical accuracy."
        elif n <= 55:
            sid = re.search(r"station_id '([^']+)'", t["query"]).group(1)
            distances = {s: central_angle(self.point(sid), self.point(s))*RADIUS for s in ids}
            included = sorted(s for s, x in distances.items() if x <= 5000)
            value = len(included)
            detail = {"included_station_ids": included,
                      "minimum_distance_from_5000m_boundary": min(abs(x-5000) for x in distances.values()),
                      "radius_6371008_8_same_membership": included == sorted(s for s, x in distances.items()
                                                                  if x*6371008.8/RADIUS <= 5000)}
            method = "Spherical unit-vector distances, radius 6371000 m, threshold <=5000 m including self."
        elif n <= 60:
            lat, lon = map(float, re.search(r"coordinates \(([^,]+), ([^)]+)\)", t["query"]).groups())
            nearest = sorted((central_angle((lat, lon), self.point(s))*RADIUS, s) for s in ids)
            value = nearest[0][1]
            detail = {"query_latitude": lat, "query_longitude": lon, "nearest_two_distance_m_and_id": nearest[:2]}
            method = "Independent spherical search over all 64 station coordinates; coordinates interpreted as latitude, longitude."
        elif n <= 70:
            region = re.search(r"region_id '([^']+)'", t["query"]).group(1)
            region_ids = [s for s in ids if self.info[s]["region_id"] == region]
            present = [s for s in region_ids if s in c]
            ratios = [u[s] for s in region_ids if s in u]
            op = (n-61) % 5
            value = [sum(b[s] for s in region_ids), sum(c[s] for s in present),
                     statistics.mean(b[s] for s in region_ids), statistics.mean(ratios) if ratios else None,
                     100*sum(b[s] == 0 for s in region_ids)/len(region_ids)][op]
            detail = {"region_id": region, "station_ids": region_ids, "capacity_present_count": len(present)}
            if n == 67:
                value = None
                override = MISMATCH
                issues = ["The sole region 949 station has missing capacity. Reference 0 mistakes an empty reported-capacity sum for known total capacity."]
                proposal = "Return null/unknown under an explicit missing-data policy, or explicitly ask for the sum of reported capacities."
            if n == 69:
                override = MISMATCH
                issues = ["No defined utilization ratio exists; source reference is non-standard JSON NaN and the query demands a float."]
                proposal = "Return JSON null with an explicitly supported missing-value grader, or replace this task."
        elif n <= 80:
            value = {71: sum(v["rider_capacity"] for v in self.types.values()),
                     72: statistics.mean(v["rider_capacity"] for v in self.types.values()),
                     73: sum(v.get("max_range_meters") is None for v in self.types.values()),
                     74: max(v["max_range_meters"] for v in self.types.values() if v.get("max_range_meters") is not None),
                     75: sum(v["rider_capacity"] > 1 for v in self.types.values()),
                     76: max(self.distinct.values()), 80: statistics.mean(self.distinct.values())}[n]
        elif n <= 90:
            value = None
            override = UNVERIFIABLE
            issues = ["Boolean True is an artifact-existence target, not a reference plot or content rubric. No model artifact inspected or executed."]
            proposal = "Publish expected plot data plus a rubric for chart type, axes, units and labels; review actual images separately."
            if n in (83, 87):
                issues.append("Plot also requires an explicit missing-capacity policy.")
            if n in (85, 86, 87):
                issues.append("Top 10 plotting requires an explicit secondary ordering rule for ties.")
        else:
            sid = re.search(r"station_id '([^']+)'", t["query"]).group(1)
            value = b[sid]/c[sid]
            detail = {"station_id": sid, "numerator": b[sid], "denominator": c[sid]}
        self.record(t, value, method, issues=issues, details=detail, proposal=proposal, status=override)

    def semantics(self, task):
        review = self.semantic[task["id"]]
        if review["query_sha256"] != hashlib.sha256(task["query"].encode()).hexdigest():
            return self.record(task, None, "Frozen semantic review no longer matches question text.", status=UNVERIFIABLE)
        self.record(task, review["reviewed_choice"], review["basis"],
                    issues=review.get("issues"), proposal=review.get("proposal"),
                    details={"field_or_section": review["field_or_section"],
                             "review_type": "GPT-6-Astra source-grounded adjudication; not an independent human review",
                             "qualification": review.get("qualification")},
                    sources=review["sources"])

    def run(self):
        tasks = [json.loads(line) for line in (BUNDLE/"tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(tasks) == 300 and len({t["id"] for t in tasks}) == 300
        assert self.info.keys() == self.status.keys(), "Station join coverage changed"
        for task in tasks:
            getattr(self, task["category"])(task)
        source_files = [BUNDLE/"tasks.jsonl", ROOT/"validation/semantic_review_v1.json", *sorted(SNAPSHOT.glob("*.json"))]
        missing = sorted(set(self.info)-set(self.c))
        discrepancies = [{"station_id": s, "capacity": self.c[s], "bikes": self.b[s], "docks": self.d[s]}
                         for s in self.c if self.c[s] != self.b[s]+self.d[s]]
        type_conservation = all(sum(v["count"] for v in s["vehicle_types_available"]) == s["num_bikes_available"]
                                for s in self.status.values())
        max_offset = max(central_angle((b["lat"], b["lon"]), self.point(b["station_id"]))*RADIUS for b in self.bikes)
        counts = {status: sum(r["status"] == status for r in self.records)
                  for status in (MATCH, MISMATCH, AMBIGUOUS, UNVERIFIABLE)}
        return clean({"schema_version": "1.0", "validation_date": "2026-11-16",
                      "validator": "Independent GPT-6-Astra review and standard-library Python recalculation",
                      "not_human_validation": True, "semantic_review_not_blinded": True, "offline_replay": True,
                      "semantic_sources_checked_online_on": "2026-11-16",
                      "scope": "Frozen GBFSBench MV-Rad v1; published task labels/results unchanged",
                      "classification_definitions": {
                          MATCH: "Unambiguous reference supported by independent calculation or source-grounded choice review.",
                          MISMATCH: "Published target is unsupported/invalid as an answer to the literal question.",
                          AMBIGUOUS: "Reference can be reproduced or is the best choice, but required assumptions/qualifications are missing.",
                          UNVERIFIABLE: "No substantive reference target/rubric available for validation."},
                      "summary": counts,
                      "by_category": {cat: dict(Counter(r["status"] for r in self.records if r["category"] == cat))
                                      for cat in ("semantics", "retrieval", "synthesis")},
                      "inputs_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in source_files},
                      "validator_sha256": digest(Path(__file__)),
                      "snapshot_diagnostics": {
                          "stations": len(self.info), "status_rows": len(self.status), "vehicle_types": len(self.types),
                          "derived_vehicle_rows": len(self.bikes), "missing_capacity_station_ids": missing,
                          "capacity_vs_bikes_plus_docks_discrepancies": discrepancies,
                          "vehicle_type_breakdowns_sum_to_station_bike_counts": type_conservation,
                          "derived_row_counts_equal_station_bikes_at_all_stations": all(self.free[s] == self.b[s] for s in self.info),
                          "derived_vehicle_max_coordinate_offset_from_station_m": max_offset,
                          "all_station_operational_flags_true": all(s[k] for s in self.status.values()
                                                                     for k in ("is_renting", "is_returning", "is_installed")),
                          "system_information_nonstandard_time_zone_field": "time_zone" in self.data("system_information")
                                                                                     and "timezone" not in self.data("system_information")},
                      "limits": ["Independent implementation, not independent acquisition of source observations.",
                                 "Semantic adjudications are documented model-assisted judgments and replayed offline, not re-adjudicated by Python.",
                                 "No provider API calls, model reruns, model-output agreement or artifact-content validation.",
                                 "Derived vehicle coordinates and IDs do not independently establish observed vehicle locations or identities.",
                                 "Numeric matching uses explicit absolute source tolerances; it does not reproduce benchmark grader logic.",
                                 "This is new validation on 16 November 2026, not validation claimed to have preceded the original experiment.",
                                 "All corrections are proposals; published task and result files are untouched."],
                      "tasks": self.records})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a new report; refuses to overwrite an existing file")
    args = parser.parse_args()
    report = Audit().run()
    if args.output:
        destination = args.output.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"summary": report["summary"], "by_category": report["by_category"]}, indent=2))


if __name__ == "__main__":
    main()
