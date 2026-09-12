# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, purchases, or Production data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The safe v21 collector supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: `target` remains the full deadline-window collection set, while `target_id_rows` is only the downstream decision subset. `collection_ids` and the data-collection loop both use the full `target`. This behavior is frozen by CI so candidate targeting cannot silently narrow snapshot collection.

The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and a separate `learning_all` label.

Natural evidence on 2026-09-12 JST repeatedly showed the same race sets and almost identical saved-row counts. At 11:00, 11:15, 12:00 and 12:15 both collectors covered the same deadline-window races; at 12:30 a small start-time drift moved one edge race but 9/10 race identities still overlapped. No Cron or service setting was changed during this research.

## Live identity inventory: duplication is nearly complete

All queries below run through a research-only live audit with `PGOPTIONS=-c default_transaction_read_only=on`, static rejection of DB mutation primitives, and SELECT/catalog queries only.

Latest verified realtime-odds inventory before the indirect-dependency extension:

- `v2_realtime_odds_snapshots`: `506,904,576` bytes / `1,383,910` exact rows
- `final_ab`: `986,420` rows / `8,453` races
- `learning_all`: `397,370` rows / `3,376` races
- final-vs-learning `(race_id,ticket)` overlap: `396,410`
- learning-only odds identities: `960`
- equal current odds in overlap: `384,472` (**96.99%**)
- average absolute collection-time gap: about `72.60s`

Across odds + weather + exhibition + entry + race-condition + racer-condition, current `learning_all` contains `460,920` rows and about `103,050,968` bytes of logical tuple payload (~98.3 MiB; not physical reclaim). Only `1,152` stored identities lack the same identity under `final_ab`.

For the seven completed days immediately before the current date:

- `learning_all`: `76,235` rows
- `final_ab`: `139,386` rows
- recent learning-only identities: **12**
- recent identity overlap: **99.9843%**
- all 12 recent learning-only identities are exhibition rows
- average learning growth: about **10,890.71 rows/day**
- average logical tuple payload: about **2,429,374 bytes/day** (~2.32 MiB/day)

This proves near-total duplicate identity coverage and ongoing duplicated write/storage growth.

## Movement features differ materially

For `396,410` overlapping odds identities:

- equal current odds: `384,472` (**96.99%**)
- equal market rank: `387,059` (**97.64%**)
- equal `prev_odds`: `314,260` (**79.28%**)
- all compared movement features equal: `313,458` (**79.07%**)
- movement-feature differences: `82,952` (**20.93%**)

The compared movement set includes previous odds/rank, delta / percentage delta, rank delta, favorite/low-odds flags, and drift/steam flags.

Initially this looked like a separate research-only shifted trajectory. A deeper code audit found a stronger constraint: the two labels are **not independent feature chains**.

## Critical indirect Production dependency: previous odds are cross-label

Current `v21_realtime_collector_pg.py::_fetch_previous_odds(rid)` queries:

`v2_realtime_odds_snapshots where race_id=%s order by snapshot_at desc ... limit 240`

It does **not** filter by `snapshot_label`. The safe collector reuses that helper when building each new odds row.

Therefore the previous observation used to compute a new `final_ab` row may come from `learning_all`, and vice versa. The computed fields include:

- `prev_odds`
- `odds_delta`
- `odds_delta_pct`
- `prev_market_rank`
- `market_rank_delta`
- `is_odds_drift`
- `is_odds_steam`

This is not merely research metadata. `v22_realtime_decision_engine_pg.py::_realtime_judge()` reads the `final_ab` odds snapshot and changes the Production realtime score when these flags are set:

- `is_odds_steam` → `score += 0.3`
- `is_odds_drift` → `score -= 0.5`

Recommendations are then derived from the score (`buy` at score >= 1.0, `watch` at score >= 0.0, otherwise `skip`, absent other skip conditions).

So the statement “no Production code hard-codes the literal `learning_all` label” remains true, but it is **not sufficient to prove output independence**. The learning collector can influence the semantics of later `final_ab` movement features through the shared previous-odds lookup.

A dedicated read-only audit is now quantifying how often current rows visibly show this cross-label predecessor relationship and how many saved final decisions intersect it.

## Consequence: full learning pause is currently blocked

A future `LEARNING_ALL_ENABLED=0` observation is no longer classified as a harmless reversible data-collection test. Even with no code/threshold change, stopping the learning collector can change the time interval and source used for `final_ab.prev_odds`, which can change steam/drift flags and therefore Production BUY/WATCH/SKIP scores.

Accordingly:

- **do not pause or disable `cron-learning-all` under the current feature semantics** without explicit Production/model-impact approval and a stronger output-invariance plan;
- historical `learning_all` rows remain preservation-by-default;
- a label-scoped `_fetch_previous_odds` rewrite would itself change feature semantics and is also a Production model-impact change, not a cleanup-only patch.

## Consumer/isolation CI contract

`tests/test_learning_all_redundancy_contract.py` now protects both the direct and indirect assumptions:

- final/nightly chains default to `final_ab`;
- no other top-level runtime Python script silently hard-codes `learning_all`;
- learning wrapper remains collection-only with no decision/notifier/purchase wiring;
- candidate decision targeting cannot narrow full snapshot collection;
- the current previous-odds lookup is explicitly recognized as cross-label, while v22 is recognized as consuming steam/drift in its score.

The last item intentionally prevents a future cleanup discussion from forgetting this hidden coupling. If the collector is later redesigned, this research contract must be updated together with a new invariance proof.

## Capacity direction after the dependency finding

Three earlier choices are no longer equivalent.

### Keep both collectors

This preserves current Production feature semantics exactly, at the cost of near-total identity duplication and ~10.9k extra logical learning rows/day.

### Full learning pause

**Blocked as an output-neutral capacity experiment.** It may alter `final_ab` movement features and v22 scores. Any future test requires explicit approval as a Production/model-impact experiment, plus a rollback and output-comparison design.

### Odds-only learning path

This becomes the most relevant research candidate. The odds label appears to be the part needed to preserve the current cross-label market-movement predecessor behavior, while the non-odds `learning_all` tables are much more payload-redundant and are read by Production only through the `final_ab` label.

Current logical tuple split:

- odds rows: about **73.6%** of stored learning tuple bytes;
- non-odds learning tables: about **26.4%**;
- recent non-odds learning growth: about `1,559` rows/day and ~`0.62 MiB/day` of logical tuple payload.

An odds-only design would not solve the full volume-growth problem, but it could remove redundant beforeinfo/network work and non-odds writes while preserving the current odds cross-label predecessor mechanism. It remains design-only until separately reviewed and approved.

## Safe next research sequence

1. Finish the cross-label predecessor and saved-decision read-only audit.
2. Freeze the indirect dependency in docs/CI.
3. Specify an odds-only learning mode as a separate Draft design with **default-off / no Production deployment**.
4. Prove statically that such a mode still writes `learning_all` odds on the same schedule/window but skips only non-odds learning writes.
5. Quantify expected write/load savings; do not claim proportional physical volume shrink.
6. Do not merge/deploy/enable the mode without explicit approval.
7. Treat any full pause or label-scoped previous-odds rewrite as a separate Production/model-impact change.

## Current decision

`IDENTITY_DUPLICATION_CONFIRMED / RECENT_IDENTITY_OVERLAP_99_9843PCT / LEARNING_GROWTH_10891_ROWS_PER_DAY / MOVEMENT_FEATURE_DIFFERENCE_20_93PCT / DIRECT_LITERAL_PRODUCTION_CONSUMER_NOT_FOUND / INDIRECT_CROSS_LABEL_PREVIOUS_ODDS_DEPENDENCY_CONFIRMED_STATICALLY / V22_STEAM_DRIFT_SCORE_SENSITIVE / FULL_LEARNING_PAUSE_BLOCKED / HISTORICAL_LEARNING_ROWS_PRESERVE / ODDS_ONLY_REDESIGN_RESEARCH_CANDIDATE / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_DB_DELETE / NO_PRODUCTION_CHANGE`
