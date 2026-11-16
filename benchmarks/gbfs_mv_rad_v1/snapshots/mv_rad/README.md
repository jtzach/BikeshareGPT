# MV-Rad GBFS Benchmark-Ready Snapshot

This bundle is a self-contained GBFS snapshot prepared for benchmark development and evaluation.

## Contents
- `gbfs_source.json`: original source discovery document
- `gbfs.json`: local self-contained discovery document with relative URLs
- `system_information.json`, `vehicle_types.json`, `station_information.json`, `station_status.json`, `system_hours.json`, `system_regions.json`, `system_pricing_plans.json`: frozen GBFS files
- `free_bike_status.json`: derived file generated from station availability and vehicle-type breakdowns to support richer queries
- `manifest.json`: provenance, counts, and notes

## Counts
- Stations: 64
- Station status rows: 64
- Vehicle types: 11
- Derived free-bike rows: 335
- Regions: 2

## Recommended use in the paper
Use this bundle as a reproducible evaluation snapshot. In the paper, describe `free_bike_status.json` as a derived augmentation rather than a raw vendor file.
