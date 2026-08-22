# Historical weather repair safety note

The July 2025 month repair intentionally fills only `temperature_c` and
`water_temperature_c` NULL cells in `snapshot_label=historical` rows using the
already-stored official `raw.text` source. Confirmed source-gap races remain
NULL. No values are guessed.

Production prediction logic, Shadow logic, LINE notification code, exhibition,
course, ST and tilt fields are outside this repair scope.
