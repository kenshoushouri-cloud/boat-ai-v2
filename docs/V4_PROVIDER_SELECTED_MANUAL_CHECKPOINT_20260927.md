# Manual provider-selected V4 Forward checkpoint

This workflow is intentionally **manual only**.

Trigger:
- `workflow_dispatch`
- optional `end_date=YYYY-MM-DD`
- blank end date resolves to current JST date

Ordering:
1. list prospective-freeze provider runs;
2. inventory/hash/arbiter-select formal artifacts with zero Boat DB/result/payout/odds reads;
3. materialize only selected immutable artifacts;
4. verify archive hashes;
5. freeze exact formal races/tickets;
6. only then open a PostgreSQL read-only result query;
7. report complete formal days, TOP1/TOP2 economics, robustness, voids and pending races.

The workflow never reconstructs unavailable formal days.

No schedule is attached. It does not mutate Railway config, DB, selector, TOP6/TOP2, stake, LINE or purchase behavior.

Use this as the standard refresh path after natural result availability.

`MANUAL_ONLY / PROVIDER_SELECTED_BEFORE_RESULT / ARTIFACT_FIRST / READ_ONLY_DB / NO_RECONSTRUCTION / PURCHASE_FALSE`
