# Result-day terminal readiness guard — 2026-09-27

Purpose: prevent a manual Forward checkpoint from being interpreted while the nightly result load is incomplete.

For a target date, read only `v2_races` plus matching `v2_results`.

A race is terminal only when either:

- **OFFICIAL**:
  - `result_status=official`;
  - `race_status=official`;
  - valid trifecta ticket;
  - positive trifecta payout.

- **VOID**:
  - both statuses are `cancelled/canceled`.

Everything else is non-terminal:
- missing result row;
- `no_result_page`;
- partial official row;
- unknown/intermediate status.

The day is `READY` only when:
- at least one target race exists; and
- every target race is OFFICIAL or VOID.

Otherwise:
`NOT_READY_FAIL_CLOSED`.

The combined manual Forward checkpoint should run this guard first for its `end_date`. If not ready, stop without advancing V4/S03 review counts.

No DB writes, no result mutation, no Railway config change, no LINE, no BUY.

`READ_ONLY / ALL_RACES_TERMINAL / OFFICIAL_OR_VOID / FAIL_CLOSED`
