# Provenance search and augmentation reconstruction

This investigation was performed on 16 November 2026. It separates recovered artifacts from an independently reconstructed explanation of their contents. No original data, task labels, manifests, or licence terms were modified.

## Recovered artifacts

A search of 41 workspace ZIP archives and older project sources located `others-bikeshare/gbfs_mv_rad_benchmark_ready_v1.zip`. All 13 members match the submitted snapshot directory byte for byte. Its manifest already labels `free_bike_status.json` as derived from station information/status. The archive contains no generation script or acquisition log.

Two earlier archives named `gbfs_munich_snapshot` actually contain the MV-Rad system identifier `nextbike_um`. The older discovery and station-status JSON each contain one extra closing brace compared with the valid submitted files. The files become byte-identical after removing that one brace. Other checked source files already match. These are evidence of earlier retained payloads and a syntax difference, not proof of acquisition date or the historical repair process. The `updated` archive also contains a different 30-row free-bike file; it is not the released 335-row augmentation.

The search covered code, notebooks, Markdown, text/logs, LaTeX sources, and YAML. The two notebooks found are ImprovedTransitGPT prompt tests, not augmentation notebooks. Package environments, caches and unrelated nested US transit-feed archives were excluded. No original 335-row construction script, complete 300-task construction program, acquisition log, or independent annotation/adjudication record was identified. Absence in this search does not establish that such records never existed.

## Exact reconstruction of the archived augmentation

Run, from the repository root:

```bash
python scripts/reconstruct_derived_bikes.py --check
```

The default is read-only. To produce a separate file, use `--output` with a new path; existing files are never overwritten.

The following inferred recipe reproduces all 335 records in their archived order:

1. Iterate source station-status records and each station's vehicle-type count entries in their existing order. Expand each count into one record and use a one-based index within each station.
2. Construct `bike_id` as `<station_id>_bike_<index>`. Copy station/type identifiers and set reservation/disabled flags to false.
3. Starting at the station coordinate, add `((index % 7) - 3) * 0.00003` to latitude and `((index % 5) - 2) * 0.00003` to longitude; round each to six decimal places.
4. For the six electric-assist records, whose observed within-station indices range from 1 to 4, set a temporary fraction to `1 - 0.07 * index`, save its two-decimal rounded value as `current_fuel_percent`, and save `int(max_range_meters * temporary_fraction)` as range. This explains the archived 55,799-metre value at index 1 through floating-point truncation.
5. Preserve the station-status timestamp, TTL, and GBFS version in the reconstructed envelope.

The reconstructed and archived JSON objects compare equal, including order and all fields. Per-station derived record counts equal `num_bikes_available`, totaling 335. The report supplies source hashes and canonical-record hashes.

This is a reconstruction inferred from the retained files, **not recovered historical code**. Multiple original programs could produce the same records. In particular, the observed battery values do not establish the formula outside indices 1–4. The recipe does not establish the original creator, tool, date, seed, acquisition method or validation process, and it is not a physical model of bicycle positions/battery states.

## Task-construction evidence

The released semantics YAML and loader recreate all 100 archived semantics task objects exactly. Running the generic builder on the frozen input with requests for 100 retrieval and 100 synthesis items produces 125 total tasks: 100 semantics, 15 retrieval and 10 synthesis. Only the 100 semantics IDs overlap the canonical 300-task release. The generic retrieval/synthesis generators therefore do not recreate the released 200 snapshot-task records. Human validation provenance and the exact construction program remain unresolved.

Older paper sources explicitly describe post-processing artifact paths across Windows/POSIX formats. That is documentation consistent with the existence-only score reconciliation, not a recovered executable analysis script.

Machine-readable sources, hashes, search scope, and reconstruction results are in `validation/provenance_search.json`.
