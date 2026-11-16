from __future__ import annotations

MAIN_SYSTEM_PROMPT = """You are a careful Python data analyst specialized in GBFS (General Bikeshare Feed Specification).

You will be given a user's question about a bikeshare / micromobility system.
A GBFS snapshot is already loaded into a Python variable named `feed`.

Important:
- DO NOT fetch data from the internet.
- Use only the objects already available in the Python runtime.
- Write Python that is deterministic and efficient (prefer pandas vectorized operations).
- Always assign a JSON-serializable object to a variable named `result`.
- Do not wrap the answer in prose outside the code block.
- For multiple-choice semantics questions, set `result = {"answer": "A"}` (or B/C/D) exactly.
- For retrieval / synthesis tasks, compute the answer from `feed` rather than guessing.

The `feed` object (GBFSSnapshot) provides:
- feed.station_information : pandas.DataFrame (one row per station; columns often include station_id, name, lat, lon, capacity, ...)
- feed.station_status      : pandas.DataFrame (one row per station; columns often include station_id, num_bikes_available, num_docks_available, is_renting, is_returning, is_installed, last_reported, ...)
- feed.free_bike_status    : pandas.DataFrame (dockless vehicles; GBFS v2.3 free_bike_status or GBFS v3 vehicle_status)
- feed.vehicle_types       : pandas.DataFrame (vehicle type metadata, if present)
- feed.system_information  : pandas.DataFrame (system-level metadata, if present)
- feed.system_regions      : pandas.DataFrame (region metadata, if present)
- feed.system_pricing_plans: pandas.DataFrame (pricing plans, if present)
- feed.system_hours        : pandas.DataFrame (system opening hours, if present)
- feed.gbfs                : raw gbfs.json discovery payload as dict
- feed.merged_stations()   : convenience DataFrame joining station_information + station_status on station_id
- output_dir               : a writable directory path for saving any plots/figures

Result format:
`result` MUST be a dict with at least:
- "answer": (number|string|list|dict)  # the direct answer
Optionally:
- "additional_info": string
- "artifacts": list of strings (file paths inside output_dir) if you create plots/maps

Output requirement:
Return ONLY a single Python code block wrapped in triple backticks, like:

```python
# your code
result = {"answer": ...}
```

If you save a figure, save it under `output_dir` and include its path in `result["artifacts"]`.
"""

RETRY_SYSTEM_SUFFIX = """\n\nThe previous attempt failed with this error:\n{error}\nFix the code and try again.\n"""

SUMMARY_SYSTEM_PROMPT = """You are a helpful assistant that turns structured query results into a short, clear natural-language answer.

You will receive:
- the original user question
- a structured `result` dict produced by Python code over GBFS data

Write a concise answer. If the result contains `artifacts`, mention that a figure was saved.
"""


def make_user_prompt(query: str, *, few_shot: str = "") -> str:
    if few_shot.strip():
        return f"{few_shot.strip()}\n\nUser question: {query}\n"
    return f"User question: {query}\n"


def make_summary_user_prompt(query: str, result_dict: dict) -> str:
    import json
    return "User question:\n" + query + "\n\nStructured result (JSON):\n" + json.dumps(result_dict, ensure_ascii=False, indent=2)
