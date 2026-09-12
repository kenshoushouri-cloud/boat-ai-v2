# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, or data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The v21 collector explicitly supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: it stores the full deadline-window race set while emitting only the narrower decision IDs downstream. Natural logs on 2026-09-12 showed final-check using `SCOPE=all TARGET_ID_SCOPE=candidates`.

The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and label `learning_all`.

At the 11:00 JST natural run, both services targeted the same 9 races and each reported 1080 saved/upserted trifecta odds rows. This is direct evidence of duplicate acquisition/update work, although the labels are different (`final_ab` vs `learning_all`).

## Consumer search

A bounded repository search for the literal `learning_all` found:

- the producer wrapper itself;
- service-map/documentation references;
- a safety test ensuring the wrapper uses the safe collector;
- Railway bridge variable allowlisting;
- repository classification text.

No hard-coded analytics/model/LINE consumer of the literal `learning_all` snapshot label was found. Generic snapshot-label-driven analysis code does exist, so absence of a literal consumer is not by itself enough to remove the service.

## Cost/load observation

The schedule permits up to 64 starts/day for each of final-check and learning-all, or up to 128 combined start slots/day. Latest 24h Railway metrics for learning-all showed low CPU but non-zero runtime resource use, with memory averaging about 0.093 GB while sampled. Its main avoidable cost is duplicated HTTP collection plus repeated DB upserts.

## Safest future validation sequence

Any Production change requires a separate explicit approval.

1. Pre-change read-only baseline: confirm final-check full-window coverage, odds completeness, beforeinfo completeness, and current DB growth rate.
2. Prefer a reversible variable-level observation first: temporarily make the learning wrapper exit immediately while leaving final-check untouched. Do not alter v24, BUY/WATCH/SKIP, LINE, or purchase behavior.
3. Observe at least one full natural race day without manual rerun/backfill.
4. Required pass conditions: final-check continues to cover the expected deadline-window races, official odds completeness remains normal, daily/nightly analysis jobs do not report missing required snapshot data, and no code/runtime explicitly requests the `learning_all` label.
5. Immediate rollback if any required downstream job or audit reports missing data attributable to the absent label.
6. Only after the reversible observation passes should deletion or permanent Cron removal be considered under another explicit approval.

## Current decision

`DUPLICATE_COLLECTION_CONFIRMED / LITERAL_DOWNSTREAM_CONSUMER_NOT_FOUND / GENERIC_LABEL_CONSUMPTION_RISK_REMAINS / REVERSIBLE_OBSERVATION_REQUIRED / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_PRODUCTION_CHANGE`
