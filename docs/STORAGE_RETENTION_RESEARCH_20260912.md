# Storage retention research — 2026-09-12

Research-only. No DB DELETE/UPDATE, Railway setting change, Cron change, Production model change, LINE change, purchase action, VACUUM, backup creation/restore, or merge is authorized by this document.

## Capacity snapshot

Latest read-only metadata shows the Railway PostgreSQL volume at about `4191.019 / 5000 MB` used (~83.8%) and the logical PostgreSQL database at `3,871,176,383` bytes. Capacity pressure is real, but relation row counts must not be converted directly into expected physical Railway-volume reclaim.

Only one Railway backup is currently visible: `Pre-Security-Patch Backup`, created 2026-08-23 and expiring 2026-09-22. It is too old to serve as the recovery gate for a new cleanup. A fresh restore point would require separate explicit Production approval.

## Motor2 Forward Shadow: bounded retention contract passes protected outputs

The first naive latest-only rule was rejected because it changed probability-health output. The refined hypothetical contract keeps:

1. every logical key containing any unevaluated row;
2. otherwise the latest row per `(race_id,ticket,run_class,window_name)`;
3. every row belonging to the current latest valid PRE probability-health snapshot group.

Latest Production read-only audit:

- relation size: `202,260,480` bytes
- exact rows: `168,189`
- hypothetical removable rows: `45,632`
- retained rows: `122,557`
- current unevaluated rows: `11,973`
- protected latest-PRE health rows: `44,754`
- ambiguous equal-latest logical keys: `0`

Protected-output invariance remains zero-diff:

- performance: `109,898 / 109,898`
- robustness PRE: `44,860 / 44,860`
- robustness FINAL: `44,318 / 44,318`
- latest PRE health races: `2,529 / 2,529`
- latest PRE health sparse rows: `44,754 / 44,754`

The conservative Phase-1 research candidate remains final/final only: `42,552` rows, `2,366` races, `875` snapshot keys, dates 2026-08-20..2026-09-11, digest `f2e5448b34994f5eb68a35081350ec7626a34e59292c01434fd41f08e3120343`. Protected intersection is 0. This is still a candidate set only; no delete is authorized.

## Largest base relation is historical data, not duplicate history

`v2_odds_trifecta` remains the largest relation:

- total relation: `1,896,914,944` bytes
- exact rows: `7,914,324`
- races: `66,520`
- unique `(race_id,ticket)` identity is enforced
- `is_final=false`: `1,336,278` rows
- date range: 2025-07-01..2026-09-12
- orphan rows: 0

The non-final rows are intentional pre-race base odds, and existing backtest/research consumers often read this table without filtering `is_final`. They are not classified as cleanup candidates.

PostgreSQL statistics are also stale for some recovered/imported legacy tables. For example `v2_result_entries` has `375,306` exact rows while stats-live is 0. Capacity decisions must use exact/read-only checks rather than infer emptiness from stale `pg_stat_user_tables` counts.

## `learning_all`: near-total identity duplication

`cron-learning-all` and `cron-final-check` collect the same 30-minute pre-deadline window on the same 15-minute cadence under different labels. The final safe collector uses the full `target` set for snapshot collection even when `TARGET_ID_SCOPE=candidates` narrows only decision IDs. This behavior is protected by CI.

Across odds/weather/exhibition/entry/race-condition/racer-condition tables, current `learning_all` data contains:

- `460,920` rows
- about `103,050,968` bytes of logical tuple payload (~98.3 MiB; not physical reclaim)
- `1,152` identities not present under `final_ab` over the full stored period

In the seven completed days immediately before the current date:

- `learning_all`: `76,235` rows
- `final_ab`: `139,386` rows
- learning-only identities: `12`
- identity overlap with `final_ab`: **99.9843%**
- average growth: about `10,890.71` learning rows/day
- average logical tuple payload: about `2,429,374` bytes/day (~2.32 MiB/day)

All 12 recent learning-only identities are exhibition rows. Odds/weather/entry/race-condition/racer-condition had zero recent learning-only identities.

## Movement features differ materially

Among `396,410` overlapping realtime-odds identities:

- current odds equal: `384,472` (**96.99%**)
- market rank equal: `387,059` (**97.64%**)
- `prev_odds` equal: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature differences: `82,952` (**20.93%**)

The compared fields include previous odds/rank, odds delta / percentage delta, rank delta, favorite/low-odds flags, and drift/steam flags.

This difference is not merely a second independent research series. A deeper audit found that the two labels are coupled during feature construction.

## Critical indirect Production dependency: previous odds are cross-label

Current `v21_realtime_collector_pg.py::_fetch_previous_odds(rid)` reads the newest rows for a race from `v2_realtime_odds_snapshots` without filtering `snapshot_label`. `v21_realtime_collector_pg_safe.py` reuses that helper when it saves a new odds snapshot.

As a result, a new `final_ab` row may derive these fields from the latest `learning_all` observation, and vice versa:

- `prev_odds`
- `odds_delta`
- `odds_delta_pct`
- `prev_market_rank`
- `market_rank_delta`
- `is_odds_drift`
- `is_odds_steam`

The live read-only audit confirms this is common, not hypothetical:

- overlapping rows where `final_ab` was collected after `learning_all`: `188,319`
- rows where that later `final_ab.prev_odds` **and** `prev_market_rank` equal the current `learning_all` odds/rank: `188,080` (**99.87%** of final-after-learning rows)
- affected races: `1,590`
- reverse direction, `learning_all.prev_*` matching an earlier/current `final_ab`: `207,375` rows
- direct predecessor matches within 180 seconds: `177,186`
- direct predecessor matches in the latest seven completed days: `31,617`
- average direct learning→final gap: about `77.49s`

This matters to Production behavior. `v22_realtime_decision_engine_pg.py::_realtime_judge()` reads the `final_ab` snapshot and changes its realtime score when movement flags are set:

- `is_odds_steam` → `+0.3`
- `is_odds_drift` → `-0.5`

Recommendations then depend on that score (`buy` at >=1.0, `watch` at >=0.0, otherwise `skip`, absent stronger skip conditions).

No Production code needs to hard-code the literal `learning_all` string for this dependency to exist.

## Counterfactual proxy: removing the immediate learning hop changes a Production-scored feature

Realtime storage keeps one current row per `(race_id,snapshot_label,ticket)`, so exact replay of every overwritten same-label snapshot is unavailable. The read-only audit therefore uses a bounded one-step proxy only where:

1. a final row demonstrably used current learning odds as `prev_odds`; and
2. that learning row itself has non-null previous odds.

For `169,758` such rows:

- stored drift rows: `1,122`
- proxy drift rows without the immediate learning hop: `12,584`
- stored steam rows: `282`
- proxy steam rows: `3,900`
- rows whose drift/steam movement score changes: **`15,419`**
- changed rows in the latest seven completed days: **`10,805`**
- proxy score higher than stored: `3,791`
- proxy score lower than stored: `11,628`
- possible proxy movement-score delta: **`-0.8` to `+0.8`**

This is **not** evidence that 15,419 historical BUY/WATCH/SKIP recommendations would flip. It is a bounded sensitivity result showing that removing the learning hop can materially change an input that v22 scores in Production.

The current persisted decision table is too small for a historical decision-flip claim. The safe conclusion is mechanistic and prospective: the current feature path is demonstrably cross-label and Production-score-sensitive, so a learning pause is not output-invariant by construction.

## Consequence: full `learning_all` pause is blocked as a cleanup experiment

A `LEARNING_ALL_ENABLED=0` pause would change the observation sequence available to `_fetch_previous_odds`. That can change `final_ab.prev_odds`, drift/steam flags, and therefore v22 scores even if no model coefficient or threshold is edited.

Accordingly:

- do **not** classify a learning-service pause as a harmless reversible capacity test;
- any full pause requires explicit Production/model-impact approval plus an output-comparison and rollback design;
- historical `learning_all` rows remain preservation-by-default;
- changing `_fetch_previous_odds` to be label-scoped would also change feature semantics and therefore requires a separate Production/model-impact approval.

CI freezes this hidden dependency explicitly so future cleanup work cannot accidentally assume label independence.

## Research candidate: odds-only learning path

The strongest safe research direction is no longer a full pause. It is an **odds-only learning** design that keeps the `learning_all` odds observations—and therefore preserves the current cross-label predecessor cadence—while skipping redundant learning-label weather/exhibition/entry/condition writes.

Current logical tuple split:

- odds learning bytes: `75,876,808`, about **73.63%** of stored `learning_all` tuple bytes;
- non-odds learning bytes: `27,174,160`, about **26.37%**;
- over the latest seven completed days, non-odds learning rows added `10,912` rows total (~`1,559/day`);
- non-odds logical tuple payload added `4,575,256` bytes over seven days (~`0.62 MiB/day`).

This would be a modest storage-growth reduction, not a complete capacity solution, but it can also reduce duplicate beforeinfo/network/DB-write work while preserving the current odds feature chain. It remains design-only: implementing, merging, deploying, or enabling such a mode requires separate approval.

## Physical reclaim boundary

Deleting historical rows is not equivalent to shrinking the Railway volume. Plain PostgreSQL DELETE/VACUUM generally turns space into internal reusable capacity; an operation intended to shrink relation files or the OS-visible volume would require a separate high-impact plan, downtime/locking analysis, fresh backup, and explicit approval.

The immediate capacity benefit of reducing duplicate collection is primarily **slower future growth and less duplicated network/DB write load**, not a guaranteed immediate volume-size drop.

## Required gates before any Production change

1. Keep the Motor2 zero-diff retention and `learning_all` dependency contracts green.
2. Obtain/verify a fresh restorable backup before any deletion/rewrite operation.
3. For Motor2, re-run the exact approved-scope digest immediately before any future delete request.
4. Treat a full `learning_all` pause as a Production/model-impact experiment, not a cleanup-only observation.
5. Treat any label-scoped previous-odds rewrite as a Production/model-impact change.
6. Research odds-only learning separately and keep it default-off / undeployed until explicitly approved.
7. Treat collector/Cron/variable changes, historical row deletion, and physical rewrite/VACUUM actions as separate approvals.
8. Re-measure logical and Railway volume growth after any approved change before introducing new persistent Shadow tables.

## Current gate

`CAPACITY_PRESSURE_CONFIRMED / MOTOR2_ZERO_DIFF_RETENTION_PASS / CONSERVATIVE_FINAL_ONLY_42552 / BASE_ODDS_NOT_CLEANUP_TARGET / REALTIME_IDENTITY_DUPLICATION_CONFIRMED / RECENT_LEARNING_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / CROSS_LABEL_PREVIOUS_ODDS_CONFIRMED / DIRECT_PREDECESSOR_MATCHES_188080 / RECENT7_DIRECT_PREDECESSOR_MATCHES_31617 / COUNTERFACTUAL_PROXY_SCORE_CHANGED_15419 / RECENT7_PROXY_SCORE_CHANGED_10805 / V22_STEAM_DRIFT_SCORE_SENSITIVE / FULL_LEARNING_PAUSE_BLOCKED / HISTORICAL_LEARNING_PRESERVE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / BACKUP_STALE_FOR_CLEANUP / NO_DB_DELETE / NO_VACUUM / NO_BACKUP_CREATE / NO_CRON_CHANGE / NO_PRODUCTION_CHANGE`
