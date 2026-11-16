"""Generate the data-descriptor figures from the corrected frozen release.

These are explanatory manuscript figures, not model-produced benchmark tasks.
The script uses no live feeds, model calls, map tiles or archived predictions.
Run: python scripts/make_paper_figures.py
Dependencies: matplotlib and numpy (included in the project requirements).
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.ticker import MaxNLocator
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "benchmarks/gbfs_mv_rad_v1_1"
OUTPUT = ROOT / "paper/figures"
BLUE = "#245973"
TEAL = "#287F80"
GOLD = "#B66D2B"
INK = "#182D3B"
MUTED = "#53616A"
LINE = "#8E9AA2"
PALE = "#F1F5F7"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10.5,
        "axes.labelsize": 10.5, "axes.titlesize": 11.5,
        "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": LINE, "axes.linewidth": 0.7,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "svg.fonttype": "none", "svg.hashsalt": "GBFSBench-v1.1-figures",
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })


def panel(ax, label, title):
    ax.text(0, 1.05, label + "  " + title, transform=ax.transAxes, fontsize=11.5,
            fontweight="bold", ha="left", va="bottom")


def box(ax, x, y, width, height, text, *, fill=PALE, size=10.4, weight="normal", dashed=False):
    ax.add_patch(Rectangle((x, y), width, height, facecolor=fill, edgecolor=LINE,
                           linewidth=0.9, linestyle="--" if dashed else "-"))
    ax.text(x + width/2, y + height/2, text, fontsize=size, fontweight=weight,
            ha="center", va="center", linespacing=1.45)


def arrow(ax, start, end, *, style="-|>", color=BLUE, connection="arc3,rad=0", lw=1.25, dashed=False):
    patch = FancyArrowPatch(start, end, arrowstyle=style, color=color,
                            mutation_scale=11, linewidth=lw,
                            connectionstyle=connection,
                            linestyle="--" if dashed else "-",
                            shrinkA=0, shrinkB=0)
    ax.add_patch(patch)
    return patch


def save(fig, stem):
    fig.savefig(OUTPUT / (stem + ".png"), dpi=300)
    fig.savefig(OUTPUT / (stem + ".svg"), metadata={"Date": None, "Creator": "make_paper_figures.py"})
    fig.savefig(OUTPUT / (stem + ".pdf"), metadata={"CreationDate": None, "ModDate": None,
                                                   "Creator": "make_paper_figures.py"})
    plt.close(fig)


def overview(stats):
    fig = plt.figure(figsize=(7.2, 4.5))
    left = fig.add_axes([.055, .16, .49, .68])
    right = fig.add_axes([.66, .23, .30, .54])
    left.set(xlim=(0, 1), ylim=(0, 1)); left.axis("off")
    fig.text(.055,.92,"A  Snapshot and augmentation",fontsize=11.5,fontweight="bold")
    box(left, 0, .64, .48, .29,
        f"{stats['stations']} stations\nmetadata + status", size=10.3)
    box(left, 0, .39, .48, .20,
        f"{stats['vehicle_types']} vehicle types\n{stats['regions']} regions", size=10.3)
    box(left, .63, .53, .37, .32,
        f"{stats['derived_bikes']} derived\nbike records", fill="#E7F1EF", size=11, weight="bold")
    arrow(left, (.48, .75), (.63, .75))
    arrow(left, (.48, .47), (.63, .61))
    left.text(.815, .46, "Expansion of\nstation counts", size=9.4, ha="center", va="top")
    left.text(.5, .265, "Constructed positions and optional battery values", size=9.2, ha="center", va="top",
              color=MUTED, linespacing=1.4)
    left.text(0, .17, "Capacity reporting", fontsize=10.5, fontweight="bold")
    fraction = stats["reported_capacity"] / stats["stations"]
    left.add_patch(Rectangle((0, .075), fraction, .06, facecolor=BLUE, edgecolor="none"))
    left.add_patch(Rectangle((fraction, .075), 1-fraction, .06, facecolor=GOLD, edgecolor="none"))
    left.text(0, .015, f"{stats['reported_capacity']} reported", fontsize=9.7, va="top")
    left.text(1, .015, f"{stats['missing_capacity']} missing", fontsize=9.7, ha="right", va="top", color=GOLD)

    cats = ["Semantics", "Retrieval", "Synthesis"]
    values = [stats["task_counts"][cat.lower()] for cat in cats]
    fig.text(.66,.92,"B  Corrected v1.1 tasks",fontsize=11.5,fontweight="bold")
    right.barh([2, 1, 0], values, height=.55, color=[BLUE, TEAL, GOLD])
    right.set_yticks([2, 1, 0], cats)
    right.set(xlim=(0, 116), ylim=(-.6, 2.65), xlabel="Number of tasks")
    right.set_xticks([0, 50, 100]); right.spines["left"].set_visible(False)
    right.tick_params(axis="y", length=0)
    for y, value in zip([2, 1, 0], values):
        right.text(value + 3, y, str(value), va="center", fontsize=10.5, fontweight="bold")
    fig.text(.81, .85, f"{sum(values)} active tasks", fontsize=11.3, fontweight="bold", ha="center")
    fig.text(.055, .035,
             "v1 is retained in full; its 10 artifact-existence tasks are excluded from active v1.1.",
             fontsize=9.3, color=MUTED)
    save(fig, "figure_1_data_overview")


def geography(rows, stats):
    fig = plt.figure(figsize=(7.2, 4.9))
    ax = fig.add_axes([.095, .36, .40, .48])
    hist = fig.add_axes([.635, .36, .325, .48])
    fig.text(.095,.92,"A  Station coordinates",fontsize=11.5,fontweight="bold")
    fig.text(.635,.92,"B  Availability distribution",fontsize=11.5,fontweight="bold")
    lon = [r["lon"] for r in rows]; lat = [r["lat"] for r in rows]
    bikes = [r["bikes_available"] for r in rows]
    sc = ax.scatter(lon, lat, c=bikes, vmin=0, vmax=max(bikes), cmap="cividis",
                    s=28, edgecolors="white", linewidths=.35, zorder=3)
    missing = [r for r in rows if r["capacity"] is None]
    ax.scatter([r["lon"] for r in missing], [r["lat"] for r in missing], s=100,
               facecolors="none", edgecolors=GOLD, linewidths=1.5, zorder=4,
               label="Capacity missing")
    ax.set_xlabel("Longitude (°E)", labelpad=4); ax.set_ylabel("Latitude (°N)", labelpad=5)
    ax.set_aspect(1 / math.cos(math.radians(float(np.mean(lat)))) )
    ax.set_xlim(min(lon)-.18, max(lon)+.18); ax.set_ylim(min(lat)-.10, max(lat)+.10)
    ax.xaxis.set_major_locator(MaxNLocator(4)); ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.grid(color="#DCE3E7", linewidth=.5, zorder=0)
    ax.legend(loc="upper left", fontsize=8.6, frameon=False, handlelength=1.0, borderpad=.2)
    color_ax = fig.add_axes([.115, .18, .34, .025])
    cbar = fig.colorbar(sc, cax=color_ax, orientation="horizontal", ticks=[0, 10, 20, 30, max(bikes)])
    cbar.ax.tick_params(labelsize=8.8, length=2.5)
    cbar.set_label("Bikes available", fontsize=9.5, labelpad=2)
    cbar.outline.set_visible(False)

    labels = ["0", "1–4", "5–9", "10–19", "20–39"]
    counts = [sum(v==0 for v in bikes), sum(1<=v<=4 for v in bikes),
              sum(5<=v<=9 for v in bikes), sum(10<=v<=19 for v in bikes),
              sum(20<=v<=39 for v in bikes)]
    assert sum(counts) == len(rows)
    hist.bar(labels, counts, color=[GOLD, BLUE, BLUE, BLUE, BLUE], width=.65)
    hist.set(ylabel="Number of stations", xlabel="Bikes available (groups)", ylim=(0, max(counts)+4))
    hist.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    for x, count in enumerate(counts):
        hist.text(x, count+.5, str(count), ha="center", fontsize=10)
    hist.tick_params(axis="x", length=0)
    fig.text(.635, .21, f"{stats['total_station_bikes']} available bikes\n{len(rows)} stations, including\n"
             f"{stats['zero_bike_stations']} with zero bikes",
             fontsize=10.2, linespacing=1.4, va="top")
    fig.text(.095, .035, "Station records only; derived bike coordinates are not mapped.", fontsize=9.3, color=MUTED)
    save(fig, "figure_2_station_snapshot")
    return {label: count for label, count in zip(labels, counts)}


def framework(stats):
    fig = plt.figure(figsize=(7.2, 5.4))
    ax = fig.add_axes([.025, .105, .95, .86])
    ax.set(xlim=(0,1), ylim=(0,1)); ax.axis("off")
    box(ax, .025, .84, .435, .12, "Versioned task + fixed system prompt\n+ five fixed few-shot examples", size=10.4)
    box(ax, .585, .84, .39, .12, "Frozen snapshot\nloaded as feed tables", size=10.4)
    box(ax, .025, .60, .435, .15, "Model request\nPython code generation", fill="#E7F1EF", size=11, weight="bold")
    box(ax, .585, .60, .39, .15, "Extract and execute Python\n30 s subprocess timeout\nText parsing if no code is returned", size=9.9)
    arrow(ax, (.2425,.84), (.2425,.75)); arrow(ax, (.78,.84), (.78,.75))
    arrow(ax, (.46,.675), (.585,.675))
    ax.text(.521,.71,"response",ha="center",fontsize=9.1,color=MUTED)

    # Error return is routed outside the main downward result path.
    ax.plot([.585,.525,.525,.2425],[.615,.615,.525,.525],color=GOLD,lw=1.15)
    arrow(ax,(.2425,.525),(.2425,.60),color=GOLD)
    ax.text(.027,.49,"Error feedback: up to two repair retries",fontsize=10,color=GOLD,va="top")
    ax.text(.027,.445,"Fresh request with the original prompt\nand latest error; at most three main calls",fontsize=9.4,
            color=MUTED,va="top",linespacing=1.4)

    box(ax,.585,.29,.39,.17,"Reference-based grading\nStructured answer or parsed text\nCorrectness and execution flag\nrecorded separately",size=10.1)
    arrow(ax,(.78,.60),(.78,.46))
    ax.text(.805,.525,"final result",fontsize=9.3,color=MUTED,ha="left",va="center")
    box(ax,.025,.235,.435,.12,"Optional natural-language summary\nNot used in the primary grade",size=10.0,dashed=True)
    ax.plot([.78,.78,.51,.51,.2425],[.49,.475,.475,.375,.375],color=LINE,lw=1.0,ls="--")
    arrow(ax,(.2425,.375),(.2425,.355),color=LINE,dashed=True)
    box(ax,.025,.055,.95,.105,"Persist final predictions, primary grades, attempt counts, token use and timing",size=10.5)
    arrow(ax,(.78,.29),(.78,.16))
    arrow(ax,(.2425,.235),(.2425,.16),color=LINE,dashed=True)
    fig.text(.05,.065,f"Archived study: v1, {stats['historical_tasks']} tasks × {stats['historical_models']} models = "
             f"{stats['historical_prediction_records']:,} model–task records.",fontsize=9.7)
    fig.text(.05,.027,f"Corrected v1.1: {sum(stats['task_counts'].values())} tasks; no new model evaluation is represented by this diagram.",fontsize=9.7,color=MUTED)
    save(fig,"figure_3_framework")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",type=Path,default=DEFAULT_BUNDLE)
    args=parser.parse_args()
    bundle=args.bundle.resolve(); snapshot=bundle/"snapshots/mv_rad"
    if not (bundle/"tasks.jsonl").is_file():
        raise SystemExit("Build the v1.1 release before generating its figures.")
    tasks=[json.loads(line) for line in (bundle/"tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    counts=dict(Counter(task["category"] for task in tasks))
    assert counts == {"semantics":100,"retrieval":100,"synthesis":90}, counts
    assert not any(task["grader"]=="artifact_exists" for task in tasks)
    raw={path.stem:read_json(path) for path in snapshot.glob("*.json")}
    info=raw["station_information"]["data"]["stations"]
    status={row["station_id"]:row for row in raw["station_status"]["data"]["stations"]}
    assert {row["station_id"] for row in info} == set(status)
    rows=[{"station_id":row["station_id"],"lat":row["lat"],"lon":row["lon"],
           "region_id":row.get("region_id"),"capacity":row.get("capacity"),
           "bikes_available":status[row["station_id"]]["num_bikes_available"],
           "docks_available":status[row["station_id"]]["num_docks_available"]}
          for row in info]
    stats={"stations":len(info),"station_status_rows":len(status),
           "reported_capacity":sum(row["capacity"] is not None for row in rows),
           "missing_capacity":sum(row["capacity"] is None for row in rows),
           "vehicle_types":len(raw["vehicle_types"]["data"]["vehicle_types"]),
           "regions":len(raw["system_regions"]["data"]["regions"]),
           "derived_bikes":len(raw["free_bike_status"]["data"]["bikes"]),
           "total_station_bikes":sum(row["bikes_available"] for row in rows),
           "zero_bike_stations":sum(row["bikes_available"]==0 for row in rows),
           "task_counts":counts,
           "semantics_label_counts":dict(sorted(Counter(t["expected"] for t in tasks if t["category"]=="semantics").items()))}
    assert stats["stations"]==64 and stats["derived_bikes"]==335
    assert stats["total_station_bikes"]==335 and stats["missing_capacity"]==1
    legacy_tasks=ROOT/"benchmarks/gbfs_mv_rad_v1/tasks.jsonl"
    historical_predictions=sorted((ROOT/"outputs/models").glob("*/predictions/predictions.jsonl"))
    stats["historical_tasks"]=sum(bool(line.strip()) for line in legacy_tasks.read_text(encoding="utf-8").splitlines())
    stats["historical_models"]=len(historical_predictions)
    stats["historical_prediction_records"]=sum(sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines()) for path in historical_predictions)
    assert (stats["historical_tasks"],stats["historical_models"],stats["historical_prediction_records"])==(300,7,2100)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    style();overview(stats);stats["bike_count_groups"]=geography(rows,stats);framework(stats)
    with (OUTPUT/"station_figure_data.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    source_files=[bundle/"tasks.jsonl",*sorted(snapshot.glob("*.json")),ROOT/"bikesharegpt/pipeline.py",legacy_tasks,*historical_predictions]
    captions={
        "release":"GBFSBench MV-Rad v1.1",
        "purpose":"Explanatory manuscript figures, not visualization benchmark tasks or model-produced plots.",
        "method":"Deterministic Python/Matplotlib generation from versioned snapshot and task files; no network or model calls.",
        "sources_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in source_files},
        "script_sha256":sha(Path(__file__)),"statistics":stats,
        "figures":[
            {"number":1,"filename":"figure_1_data_overview.png","width_inches":7.2,"height_inches":4.5,
             "caption":"Data composition and corrected task coverage. (A) The frozen bundle contains 64 station metadata and 64 station-status records, 11 vehicle types and two regions. Capacity is reported for 63 stations and missing for one. The 335 derived bike records expand station counts and contain constructed positions and, where applicable, battery values; they are not an independent set of observed vehicles. (B) The active v1.1 benchmark contains 100 semantics, 100 retrieval and 90 synthesis tasks. The ten artifact-existence tasks remain in the preserved v1 release and are excluded from v1.1.",
             "alt_text":"Diagram connecting station records and vehicle types to 335 derived bike records; capacity bar shows 63 reported and one missing; task bars show 100, 100 and 90."},
            {"number":2,"filename":"figure_2_station_snapshot.png","width_inches":7.2,"height_inches":4.9,
             "caption":"Station locations and availability in the retained MV-Rad snapshot. (A) All 64 stations are plotted at their station-information coordinates; colour encodes bikes available in station status, and the ring marks the station without reported capacity. The latitude/longitude aspect ratio is adjusted using the mean latitude. No basemap or derived bike positions are shown. (B) Counts of stations in explicit bike-availability groups sum to 64: 14 report zero bikes, 21 report 1–4, 22 report 5–9, six report 10–19 and one reports 20–39. The total is 335 available station bikes. Endpoint update timestamps refer to 28 February 2026 and do not establish the acquisition time.",
             "alt_text":"Longitude/latitude scatter of 64 stations coloured by bikes available and a categorical frequency chart showing 14, 21, 22, six and one stations in the five availability groups."},
            {"number":3,"filename":"figure_3_framework.png","width_inches":7.2,"height_inches":5.4,
             "caption":"BikeshareGPT evaluation framework. Each versioned task is combined with a fixed system prompt and five fixed few-shot examples. Generated Python runs in a subprocess with a 30-second timeout; runtime errors or missing code can trigger at most two repair requests. Each retry contains the original task/prompt and latest error rather than a full conversation history. If no code is returned, parsed text may be retained and graded after the retries; execution success and answer correctness are recorded separately. In v1.1, explicit-null targets additionally require successful execution and an explicit answer field. Optional natural-language summaries do not determine primary grades. Saved records retain the final attempt, not all intermediate conversations. The archived seven-model study used 300 v1 tasks; the corrected 290-task v1.1 release has not been newly evaluated on those models. The executor is timeout-controlled, not an operating-system security sandbox.",
             "alt_text":"Workflow from task/prompt and snapshot to model generation, extraction/execution or text fallback, bounded error-feedback loop, independent primary grading and optional summary, followed by saved records."}
        ]}
    (OUTPUT/"captions.json").write_text(json.dumps(captions,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(OUTPUT),"figures":3,"statistics":stats},indent=2))


if __name__=="__main__":main()
