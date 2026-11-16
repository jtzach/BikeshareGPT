# MV-Rad v1.1 normalized snapshot

This is a separately versioned copy of the v1 snapshot. Only the system-information payload is normalized: `time_zone` is renamed to `timezone`, preserving its value. See `normalization.json` and source hashes in `manifest.json`. Other endpoint payloads remain byte-identical to v1. The 335 free-bike rows are derived augmentation records, and original acquisition/authoring history remains unresolved. Local discovery URLs intentionally remain relative for offline execution. Original files remain under `benchmarks/gbfs_mv_rad_v1/snapshots/mv_rad/`.
