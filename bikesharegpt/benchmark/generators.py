from __future__ import annotations

import random
from typing import List

import pandas as pd

from bikesharegpt.benchmark.task import Task
from bikesharegpt.gbfs.geo import nearest_point, haversine_m
from bikesharegpt.gbfs.snapshot import GBFSSnapshot


def _pick_station_id(info: pd.DataFrame, rng: random.Random) -> str:
    if info.empty or "station_id" not in info.columns:
        return ""
    return str(rng.choice(info["station_id"].astype(str).tolist()))


def generate_retrieval_tasks(snapshot: GBFSSnapshot, n: int, *, seed: int = 42) -> List[Task]:
    """Generate simple, mostly one-hop retrieval tasks for a single snapshot."""
    rng = random.Random(seed)
    tasks: List[Task] = []
    sys_id = snapshot.system_id

    info = snapshot.station_information
    status = snapshot.station_status
    merged = snapshot.merged_stations()

    # Task 1: count stations
    if not info.empty:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_stations",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations are in the {sys_id} GBFS system? Return an integer.",
                expected=int(info.shape[0]),
                grader="exact",
            )
        )

    # Task 2: count renting stations
    if not status.empty and "is_renting" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_renting",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations are currently renting bikes in the {sys_id} system? (Use is_renting==1.)",
                expected=int((status["is_renting"] == 1).sum()),
                grader="exact",
            )
        )

    # Task 3: empty stations
    if not status.empty and "num_bikes_available" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_empty",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations currently have 0 bikes available in {sys_id}? Return an integer.",
                expected=int((status["num_bikes_available"].fillna(0).astype(float) == 0).sum()),
                grader="exact",
            )
        )

    # Task 4: station with max bikes
    if not merged.empty and "num_bikes_available" in merged.columns:
        df = merged.copy()
        if "is_renting" in df.columns:
            df = df[df["is_renting"] == 1]
        if not df.empty:
            idx = df["num_bikes_available"].fillna(-1).astype(float).idxmax()
            row = df.loc[idx]
            expected = {
                "station_id": str(row.get("station_id")),
                "name": str(row.get("name")) if row.get("name") is not None else None,
                "num_bikes_available": int(float(row.get("num_bikes_available"))) if row.get("num_bikes_available") is not None else None,
            }
            tasks.append(
                Task(
                    id=f"{sys_id}_ret_max_bikes_station",
                    category="retrieval",
                    system_id=sys_id,
                    query=f"Which station currently has the most bikes available in {sys_id}? Return station_id, name, and num_bikes_available.",
                    expected=expected,
                    grader="exact",
                )
            )

    # Task 5: random station availability lookup (tests joins & filtering)
    if not merged.empty and "station_id" in merged.columns and "num_bikes_available" in merged.columns:
        sid = _pick_station_id(info if not info.empty else merged, rng)
        if sid:
            sub = merged[merged["station_id"].astype(str) == sid]
            if not sub.empty:
                row = sub.iloc[0]
                exp = int(float(row.get("num_bikes_available"))) if row.get("num_bikes_available") is not None else 0
                tasks.append(
                    Task(
                        id=f"{sys_id}_ret_lookup_{sid}",
                        category="retrieval",
                        system_id=sys_id,
                        query=f"For station_id '{sid}' in {sys_id}, how many bikes are available right now? Return an integer.",
                        expected=exp,
                        grader="exact",
                        meta={"station_id": sid},
                    )
                )

    # Task 6: if free bikes exist, count them
    free = snapshot.free_bike_status
    if not free.empty:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_free_bikes",
                category="retrieval",
                system_id=sys_id,
                query=f"How many dockless/free vehicles are listed in free_bike_status for {sys_id} right now? Return an integer.",
                expected=int(free.shape[0]),
                grader="exact",
            )
        )

    # Task 7: if docks exist, station with max docks
    if not merged.empty and "num_docks_available" in merged.columns:
        df = merged.copy()
        idx = df["num_docks_available"].fillna(-1).astype(float).idxmax()
        row = df.loc[idx]
        expected = {
            "station_id": str(row.get("station_id")),
            "name": str(row.get("name")) if row.get("name") is not None else None,
            "num_docks_available": int(float(row.get("num_docks_available"))) if row.get("num_docks_available") is not None else None,
        }
        tasks.append(
            Task(
                id=f"{sys_id}_ret_max_docks_station",
                category="retrieval",
                system_id=sys_id,
                query=f"Which station currently has the most empty docks available in {sys_id}? Return station_id, name, and num_docks_available.",
                expected=expected,
                grader="exact",
            )
        )

    

    # ---- Additional retrieval tasks (GBFS-Bench) ----

    # Task 8: count installed stations
    if not status.empty and "is_installed" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_installed",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations are installed in {sys_id}? (Use is_installed==1.) Return an integer.",
                expected=int((status["is_installed"] == 1).sum()),
                grader="exact",
            )
        )

    # Task 9: count stations returning bikes
    if not status.empty and "is_returning" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_returning",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations are currently accepting returns in {sys_id}? (Use is_returning==1.) Return an integer.",
                expected=int((status["is_returning"] == 1).sum()),
                grader="exact",
            )
        )

    # Task 10: count stations with low availability (<=2 bikes)
    if not status.empty and "num_bikes_available" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_low_bikes",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations have 2 or fewer bikes available right now in {sys_id}? Return an integer.",
                expected=int((status["num_bikes_available"].fillna(0).astype(float) <= 2).sum()),
                grader="exact",
            )
        )

    # Task 11: count stations with at least one e-bike (if reported)
    if not status.empty and "num_ebikes_available" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_ebike_stations",
                category="retrieval",
                system_id=sys_id,
                query=f"How many stations have at least 1 e-bike available right now in {sys_id}? Return an integer.",
                expected=int((status["num_ebikes_available"].fillna(0).astype(float) >= 1).sum()),
                grader="exact",
            )
        )

    # Task 12: capacity lookup for a specific station (tests exact join keys)
    if not info.empty and "capacity" in info.columns and "station_id" in info.columns:
        sid = _pick_station_id(info, rng)
        sub = info[info["station_id"].astype(str) == str(sid)]
        if not sub.empty:
            cap = int(float(sub.iloc[0].get("capacity")))
            tasks.append(
                Task(
                    id=f"{sys_id}_ret_capacity_{sid}",
                    category="retrieval",
                    system_id=sys_id,
                    query=f"For station_id '{sid}' in {sys_id}, what is the station capacity? Return an integer.",
                    expected=cap,
                    grader="exact",
                    meta={"station_id": sid},
                )
            )

    # Task 13: count vehicle types (if present)
    vt = snapshot.vehicle_types
    if not vt.empty:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_vehicle_types",
                category="retrieval",
                system_id=sys_id,
                query=f"How many vehicle types are listed in vehicle_types for {sys_id}? Return an integer.",
                expected=int(vt.shape[0]),
                grader="exact",
            )
        )

    # Task 14: list vehicle_type_id values (if present)
    if not vt.empty and "vehicle_type_id" in vt.columns:
        exp = sorted(set(vt["vehicle_type_id"].astype(str).tolist()))
        tasks.append(
            Task(
                id=f"{sys_id}_ret_list_vehicle_type_ids",
                category="retrieval",
                system_id=sys_id,
                query=f"List all distinct vehicle_type_id values in {sys_id}. Return a list of strings (order does not matter).",
                expected=exp,
                grader="set",
            )
        )

    # Task 15: list propulsion_type values (if present)
    if not vt.empty and "propulsion_type" in vt.columns:
        exp = sorted(set(vt["propulsion_type"].astype(str).tolist()))
        tasks.append(
            Task(
                id=f"{sys_id}_ret_list_propulsion_types",
                category="retrieval",
                system_id=sys_id,
                query=f"List all distinct propulsion_type values in {sys_id}. Return a list of strings (order does not matter).",
                expected=exp,
                grader="set",
            )
        )

    # Task 16: count dockless e-bikes (if free_bike_status exists)
    if not free.empty and "vehicle_type_id" in free.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_ret_count_free_ebikes",
                category="retrieval",
                system_id=sys_id,
                query=f"How many dockless/free vehicles have vehicle_type_id 'ebike' in {sys_id}? Return an integer.",
                expected=int((free["vehicle_type_id"].astype(str) == "ebike").sum()),
                grader="exact",
            )
        )

# Downsample to n (stable ordering, stable random)
    if len(tasks) > n:
        # keep always-first "core" tasks, then sample the rest
        core = tasks[: min(3, len(tasks))]
        rest = tasks[min(3, len(tasks)) :]
        rng.shuffle(rest)
        tasks = core + rest[: max(0, n - len(core))]
    return tasks


def generate_synthesis_tasks(snapshot: GBFSSnapshot, n: int, *, seed: int = 42) -> List[Task]:
    """Generate harder tasks requiring aggregation, geospatial logic, or artifacts."""
    rng = random.Random(seed + 999)
    tasks: List[Task] = []
    sys_id = snapshot.system_id

    info = snapshot.station_information
    status = snapshot.station_status
    merged = snapshot.merged_stations()

    # S1: total bikes (aggregation)
    if not status.empty and "num_bikes_available" in status.columns:
        total = int(status["num_bikes_available"].fillna(0).astype(float).sum())
        tasks.append(
            Task(
                id=f"{sys_id}_syn_total_bikes",
                category="synthesis",
                system_id=sys_id,
                query=f"What is the total number of bikes available right now across all stations in {sys_id}? Return an integer.",
                expected=total,
                grader="exact",
            )
        )

    # S2: average bikes per station (float, tolerance)
    if not status.empty and "num_bikes_available" in status.columns and status.shape[0] > 0:
        avg = float(status["num_bikes_available"].fillna(0).astype(float).mean())
        tasks.append(
            Task(
                id=f"{sys_id}_syn_avg_bikes",
                category="synthesis",
                system_id=sys_id,
                query=f"What is the average number of bikes available per station right now in {sys_id}? Return a float.",
                expected=avg,
                grader="numeric",
                tolerance=1e-6,
            )
        )

    # S3: top-k stations list
    if not merged.empty and "num_bikes_available" in merged.columns and "name" in merged.columns:
        df = merged.copy()
        if "is_renting" in df.columns:
            df = df[df["is_renting"] == 1]
        df = df.sort_values(by="num_bikes_available", ascending=False).head(5)
        expected = df[["station_id", "name"]].astype(str).to_dict(orient="records")
        tasks.append(
            Task(
                id=f"{sys_id}_syn_top5_station_names",
                category="synthesis",
                system_id=sys_id,
                query=f"List the top 5 stations by bikes available in {sys_id}. Return a list of dicts with station_id and name, sorted descending.",
                expected=expected,
                grader="exact",
            )
        )

    # S4: geospatial nearest station (requires lat/lon)
    if not info.empty and all(c in info.columns for c in ["lat", "lon", "name"]):
        # pick a random station as query point, then ask nearest station to that station (should be itself)
        row = info.sample(1, random_state=rng.randint(0, 10_000)).iloc[0]
        qlat, qlon = float(row["lat"]), float(row["lon"])
        coords = list(zip(info["lat"].astype(float), info["lon"].astype(float)))
        i, d = nearest_point(qlat, qlon, coords)
        nearest = info.iloc[i]
        expected = {"name": str(nearest.get("name")), "distance_m": float(d)}
        tasks.append(
            Task(
                id=f"{sys_id}_syn_nearest_station",
                category="synthesis",
                system_id=sys_id,
                query=f"Find the nearest station to coordinates ({qlat:.6f}, {qlon:.6f}) in {sys_id}. Return its name and distance in meters.",
                expected=expected,
                grader="numeric",  # we'll grade distance with tolerance, name exact
                tolerance=1e-3,
                meta={"expects_name": expected["name"]},
            )
        )

    # S5: visualization artifact existence
    if not status.empty and "num_bikes_available" in status.columns:
        tasks.append(
            Task(
                id=f"{sys_id}_syn_plot_hist",
                category="synthesis",
                system_id=sys_id,
                query=f"Create a histogram plot of num_bikes_available per station for {sys_id}. Save it as a PNG inside output_dir and return result with artifacts list.",
                expected=True,
                grader="artifact_exists",
            )
        )

    

    # ---- Additional synthesis tasks (GBFS-Bench) ----

    # S6: total e-bikes available at stations (if reported)
    if not status.empty and "num_ebikes_available" in status.columns:
        total_e = int(status["num_ebikes_available"].fillna(0).astype(float).sum())
        tasks.append(
            Task(
                id=f"{sys_id}_syn_total_ebikes",
                category="synthesis",
                system_id=sys_id,
                query=f"What is the total number of e-bikes available right now across all stations in {sys_id}? Return an integer.",
                expected=total_e,
                grader="exact",
            )
        )

    # S7: station with maximum utilization (bikes / capacity), return station_id
    if not merged.empty and "num_bikes_available" in merged.columns and "capacity" in merged.columns and "station_id" in merged.columns:
        dfu = merged.copy()
        dfu["capacity"] = pd.to_numeric(dfu["capacity"], errors="coerce")
        dfu["num_bikes_available"] = pd.to_numeric(dfu["num_bikes_available"], errors="coerce").fillna(0)
        dfu = dfu[dfu["capacity"] > 0]
        if not dfu.empty:
            dfu["utilization"] = (dfu["num_bikes_available"] / dfu["capacity"]).astype(float)
            sid = str(dfu.loc[dfu["utilization"].idxmax(), "station_id"])
            tasks.append(
                Task(
                    id=f"{sys_id}_syn_max_utilization_station",
                    category="synthesis",
                    system_id=sys_id,
                    query=f"Which station has the highest utilization ratio (num_bikes_available divided by capacity) in {sys_id}? Return only the station_id as a string.",
                    expected=sid,
                    grader="exact",
                )
            )

    # S8: percent of empty stations (0 bikes)
    if not status.empty and "num_bikes_available" in status.columns and status.shape[0] > 0:
        pct = float((status["num_bikes_available"].fillna(0).astype(float) == 0).mean() * 100.0)
        tasks.append(
            Task(
                id=f"{sys_id}_syn_pct_empty_stations",
                category="synthesis",
                system_id=sys_id,
                query=f"What percentage of stations have 0 bikes available right now in {sys_id}? Return a float in [0, 100].",
                expected=pct,
                grader="numeric",
                tolerance=1e-6,
            )
        )

    # S9: great-circle distance between two stations (meters)
    if not info.empty and all(c in info.columns for c in ["station_id", "lat", "lon"]) and info.shape[0] >= 2:
        dfi = info.copy()
        dfi["station_id"] = dfi["station_id"].astype(str)
        dfi["lat"] = pd.to_numeric(dfi["lat"], errors="coerce")
        dfi["lon"] = pd.to_numeric(dfi["lon"], errors="coerce")
        dfi = dfi.dropna(subset=["lat", "lon"]).sort_values("station_id")
        if dfi.shape[0] >= 2:
            a = dfi.iloc[0]
            b = dfi.iloc[1]
            d_m = float(haversine_m(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"])))
            tasks.append(
                Task(
                    id=f"{sys_id}_syn_distance_two_stations",
                    category="synthesis",
                    system_id=sys_id,
                    query=f"What is the great-circle (haversine) distance in meters between station_id '{a['station_id']}' and station_id '{b['station_id']}' in {sys_id}? Return a float.",
                    expected=d_m,
                    grader="numeric",
                    tolerance=1e-3,
                )
            )

    # S10: count stations within 1000 meters of a reference station
    if not info.empty and all(c in info.columns for c in ["station_id", "lat", "lon"]) and info.shape[0] >= 1:
        dfi = info.copy()
        dfi["station_id"] = dfi["station_id"].astype(str)
        dfi["lat"] = pd.to_numeric(dfi["lat"], errors="coerce")
        dfi["lon"] = pd.to_numeric(dfi["lon"], errors="coerce")
        dfi = dfi.dropna(subset=["lat", "lon"]).sort_values("station_id")
        if dfi.shape[0] >= 1:
            ref = dfi.iloc[0]
            ref_lat, ref_lon = float(ref["lat"]), float(ref["lon"])
            within = 0
            for _, r in dfi.iterrows():
                if haversine_m(ref_lat, ref_lon, float(r["lat"]), float(r["lon"])) <= 1000.0:
                    within += 1
            tasks.append(
                Task(
                    id=f"{sys_id}_syn_count_within_1km",
                    category="synthesis",
                    system_id=sys_id,
                    query=f"How many stations are within 1000 meters of station_id '{ref['station_id']}' in {sys_id}? Count the reference station as well. Return an integer.",
                    expected=int(within),
                    grader="exact",
                )
            )

    # S11: total vehicles (station bikes + dockless vehicles, if present)
    if not status.empty and "num_bikes_available" in status.columns:
        station_total = int(status["num_bikes_available"].fillna(0).astype(float).sum())
        free_total = int(snapshot.free_bike_status.shape[0]) if not snapshot.free_bike_status.empty else 0
        tasks.append(
            Task(
                id=f"{sys_id}_syn_total_vehicles_all",
                category="synthesis",
                system_id=sys_id,
                query=f"In {sys_id}, what is the total number of vehicles visible right now (sum of num_bikes_available across stations + count of free_bike_status vehicles if present)? Return an integer.",
                expected=int(station_total + free_total),
                grader="exact",
            )
        )

# Downsample to n
    if len(tasks) > n:
        rng.shuffle(tasks)
        tasks = tasks[:n]
    return tasks
