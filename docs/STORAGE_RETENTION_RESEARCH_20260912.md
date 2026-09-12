# Storage retention research — 2026-09-12

Research-only. No DB DELETE/UPDATE, Railway setting change, Cron change, Production model change, LINE change, or purchase action is authorized by this document.

## Capacity snapshot

`postgres-recovery` is about 4.152 GB / 5 GB used (~83.0%). Read-only Railway metrics showed roughly +38 MB over the latest 24h and about +195 MB over 7d. Treat these as observed trend snapshots, not a forecast guarantee.

## Bounded growth findings

### Motor2 Forward Shadow

`cron-final-check` runs every 15 minutes during the configured daily range. `collect_v24_motor2_forward_shadow_pg.py` uses a timestamp-like `snapshot_key`, and the unique key includes:

`(race_id, ticket, run_class, window_name, snapshot_key)`

Therefore eligible runs create distinct historical snapshot groups.

Current read-only consumers do not all treat that history the same way:
- `motor2_forward_prob_health.py`: chooses one latest valid PRE snapshot per race.
- `report_v24_motor2_forward_performance_pg.py`: deduplicates to latest snapshot within run_class/window and then latest race/ticket where required.
- `report_v24_motor2_forward_robustness_pg.py`: deduplicates to latest race/ticket for PRE and FINAL analyses.
- `evaluate_v24_motor2_forward_shadow_pg.py`: raw diagnostic summary can include all stored observations and therefore would change if old rows were removed.
- collection-health reporting can also depend on historical snapshot counts.

Conclusion: old rows are not proven safe to delete yet. Promotion-relevant performance/robustness paths are latest-oriented, but raw diagnostics/history are not invariant.

### learning_all collector

`cron-learning-all` runs on the same 15-minute schedule as `cron-final-check`, collecting the same 30-minute-before-deadline race window under `snapshot_label=learning_all`.

Realtime odds rows are upserted on `(race_id, snapshot_label, ticket)`, so repeated runs do not create unlimited rows for the same race/label/ticket. They still duplicate network collection and DB update work relative to final-check. No hard-coded downstream consumer of the literal `learning_all` label was found in the bounded code search beyond the producer and Railway bridge, but generic label-driven analysis exists; this is not sufficient evidence to disable it.

## Offline retention contract

`research/storage_retention_contract.py` is deliberately DB-free. It models only a hypothetical candidate set:
- any logical key with an unevaluated row is fully retained;
- evaluated-only keys may nominate older snapshots as removable candidates;
- one latest snapshot is retained per `(race_id, ticket, run_class, window_name)`;
- ambiguous equal-time latest snapshots fail closed;
- malformed identities fail closed.

This helper does not execute SQL and does not imply deletion approval.

## Required gates before any real cleanup

1. Read-only inventory of row counts and storage by table/index.
2. Read-only comparison of current outputs vs hypothetical latest-only data for performance, robustness, health, evaluator summaries, and collection-health.
3. Explicit list of diagnostics allowed to change after compaction.
4. Recovery/backup plan and exact bounded date scope.
5. Separate explicit approval for any Production DB delete/vacuum/schema operation.
6. Re-measure disk usage after any approved maintenance before considering Course neutral shadow persistence.

## Current gate

`CAPACITY_PRESSURE_CONFIRMED / MOTOR2_TIMESTAMP_SNAPSHOT_GROWTH_CONFIRMED / LEARNING_ALL_DUPLICATE_COLLECTION_LOAD_CONFIRMED / LATEST_ONLY_CONSUMERS_IDENTIFIED / RAW_DIAGNOSTICS_NOT_INVARIANT / OFFLINE_RETENTION_CONTRACT_ONLY / NO_DB_DELETE / NO_CRON_CHANGE / NO_PRODUCTION_CHANGE`
