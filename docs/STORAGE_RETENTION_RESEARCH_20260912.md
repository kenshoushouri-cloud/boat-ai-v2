# Storage retention research — 2026-09-12

Research-only. No DB DELETE/UPDATE, Railway setting change, Cron change, Production model change, LINE change, purchase action, VACUUM, backup creation/restore, or merge is authorized by this document.

## Capacity snapshot

Latest read-only metadata shows the Railway PostgreSQL volume at about `4191.019 / 5000 MB` used (~83.8%) and the logical PostgreSQL database at `3,871,176,383` bytes. Capacity pressure is real, but relation row counts must not be converted directly into expected physical Railway-volume reclaim.

Only one Railway backup is currently visible: `Pre-Security-Patch Backup`, created 2026-08-23 and expiring 2026-09-22. It is too old to serve as the recovery gate for a new cleanup. A fresh restore point would require separate explicit Production approval.

## Motor2 Forward Shadow: bounded retention contract now passes protected outputs

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

## `learning_all`: near-total identity duplication, but not feature-total redundancy

`cron-learning-all` and `cron-final-check` collect the same 30-minute pre-deadline window on the same 15-minute cadence under different labels. The final safe collector uses the full `target` set for snapshot collection even when `TARGET_ID_SCOPE=candidates` narrows only decision IDs. This behavior is now protected by CI.

Across odds/weather/exhibition/entry/race-condition/racer-condition tables, current `learning_all` data contains:

- `460,920` rows
- about `103,050,968` bytes of logical tuple payload (~98.3 MiB; not physical reclaim)
- `1,152` identities not present under `final_ab` over the full stored period

In the seven completed days immediately before the current date:

- `learning_all`: `76,235` rows
- learning-only identities: `12`
- identity overlap with `final_ab`: **99.9843%**
- average growth: about `10,890.71` learning rows/day
- average logical tuple payload: about `2,429,374` bytes/day (~2.32 MiB/day)

All 12 recent learning-only identities are exhibition rows. Odds/weather/entry/race-condition/racer-condition had zero recent learning-only identities.

However, the separate label preserves a shifted odds-change trajectory. Among `396,410` overlapping realtime-odds identities:

- current odds equal: `384,472` (**96.99%**)
- market rank equal: `387,059` (**97.64%**)
- `prev_odds` equal: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature differences: `82,952` (**20.93%**)

Therefore `learning_all` is strongly redundant for identity/storage coverage but is not completely redundant for research features. The correct future decision is not “delete the label”; it is a tradeoff between capacity/load and the research value of an independent ~1-minute-shifted movement sample.

No hard-coded scheduled Production model/decision/LINE consumer of literal `learning_all` was found. Final/nightly chains default to `final_ab`, and CI now prevents new top-level runtime scripts from silently hard-coding `learning_all`. Generic research label consumers still exist, so historical learning rows should be preserved unless a separate retention contract is proved.

## Research candidate: odds-only learning path

A useful next research direction is an odds-only learning collector rather than an all-or-nothing retirement.

Why it is worth studying:

- odds rows account for about 73.6% of current `learning_all` logical tuple payload;
- meaningful feature divergence was demonstrated specifically in the odds movement fields;
- the non-odds learning tables account for about 26.4% of current tuple payload and are much more payload-redundant;
- over the latest seven completed days, non-odds learning rows added about `10,912` rows total (~1,559/day) and `4,575,256` logical tuple bytes total (~0.62 MiB/day).

This is only a design candidate. Implementing or deploying an odds-only mode would change Production collection behavior and requires separate approval.

## Physical reclaim boundary

Deleting historical rows is not equivalent to shrinking the Railway volume. Plain PostgreSQL DELETE/VACUUM generally turns space into internal reusable capacity; an operation intended to shrink relation files or the OS-visible volume would require a separate high-impact plan, downtime/locking analysis, fresh backup, and explicit approval.

The immediate capacity benefit of reducing duplicate collection is therefore primarily **slower future growth and less duplicated network/DB write load**, not a guaranteed immediate volume-size drop.

## Required gates before any Production change

1. Keep the Motor2 zero-diff retention and `learning_all` isolation contracts green.
2. Obtain/verify a fresh restorable backup before any deletion/rewrite operation.
3. For Motor2, re-run the exact approved-scope digest immediately before any future delete request.
4. For `learning_all`, explicitly choose whether to preserve the second movement trajectory: keep both, bounded reversible pause, or research an odds-only mode.
5. Treat collector/Cron/variable changes, historical row deletion, and physical rewrite/VACUUM actions as separate approvals.
6. Re-measure logical and Railway volume growth after any approved change before introducing new persistent Shadow tables.

## Current gate

`CAPACITY_PRESSURE_CONFIRMED / MOTOR2_ZERO_DIFF_RETENTION_PASS / CONSERVATIVE_FINAL_ONLY_42552 / BASE_ODDS_NOT_CLEANUP_TARGET / REALTIME_IDENTITY_DUPLICATION_CONFIRMED / RECENT_LEARNING_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / TOP_LEVEL_RUNTIME_LEARNING_CONSUMERS_NONE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / BACKUP_STALE_FOR_CLEANUP / NO_DB_DELETE / NO_VACUUM / NO_BACKUP_CREATE / NO_CRON_CHANGE / NO_PRODUCTION_CHANGE`
