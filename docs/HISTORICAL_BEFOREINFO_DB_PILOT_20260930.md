# Historical beforeinfo DB pilot — 2026-09-30

User-approved historical acquisition pilot.

Scope:
- target date: 2025-07-01
- at most 24 races
- BOAT RACE official beforeinfo only
- write only to historical snapshot tables
- snapshot_label=historical
- no canonical v2_races/v2_race_entries overwrite
- no result/odds write
- no LINE
- no purchase

Fields include historical weather, exhibition, race conditions and racer conditions that are inherently pre-race information.

Evidence class:
`HISTORICAL_RECONSTRUCTED_PREDEADLINE_ASSUMPTION`

This remains distinct from prospectively timestamped evidence.
