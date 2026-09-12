# `cron-learning-all` redundancy review — 2026-09-12

Research-only. This document does not change Railway variables, Cron, services, Production decisions, LINE, purchases, or Production data.

## Current natural behavior

Both services currently run every 15 minutes during `23,0-14` UTC (about 08:00–23:45 JST):

- `cron-final-check` → `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → `v21_realtime_collector_pg_safe.py`
- `cron-learning-all` → `run_learning_all_realtime_pg.py` → `v21_realtime_collector_pg_safe.py`

The safe v21 collector supports `COLLECT_SCOPE=all + TARGET_ID_SCOPE=candidates`: final-check stores the full deadline-window collection set while narrowing only downstream decision IDs. The learning wrapper separately forces `COLLECT_SCOPE=all`, the same 30-minute-before-deadline window, and a separate `learning_all` label.

Natural evidence on 2026-09-12 JST:

- 11:00: both collectors targeted the same 9 races and each saved 1080 trifecta odds rows.
- 11:15: both targeted the same 11 races, saved 1200 odds rows, and observed the same one official-odds miss.
- 12:00: both targeted the same 9 races and saved 1080 odds rows.
- 12:15: both targeted the same 10 races, saved 1080 odds rows, 30 exhibition rows, and 60 entry rows; both observed the same one odds miss.
- 12:30: start-time drift moved one edge race in/out of the 30-minute window, but 9/10 race identities still overlapped; both saved 1080 odds rows and 60 entry rows.

This confirms duplicate acquisition/update work under normal Production timing. No Cron or service setting was changed during this research.

## Live label inventory: duplication is quantitative, not just inferred from logs

All queries below ran through the research-only live audit with:

- `PGOPTIONS=-c default_transaction_read_only=on`
- static rejection of DB mutation primitives
- SELECT/catalog queries only

### Trifecta realtime odds

`v2_realtime_odds_snapshots` currently occupies about `506,576,896` bytes and has `1,381,750` exact rows.

Label counts:

- `final_ab`: `985,340` rows / `8,444` races
- `learning_all`: `396,290` rows / `3,367` races
- `final_ab_debug`: `120` rows / 1 race

On `(race_id,ticket)` identity:

- `learning_all` rows: `396,290`
- also present as `final_ab`: `395,330` (**99.76%**)
- `learning_all`-only identities: `960`
- overlapping rows with equal odds: `383,747` (**97.07% of overlap**)
- overlapping rows with different odds: `11,583`
- exact-equal collection timestamp: `0`
- average absolute collection-time difference: about `72.46s`

The differing values are expected to exist because the two independent collectors do not start at exactly the same instant. Identity overlap therefore establishes duplicate coverage, not byte-for-byte equivalence for every odds row.

### Other realtime snapshot tables

The same identity-overlap pattern appears across the other realtime tables:

| Table | `learning_all` rows | Identity overlap with `final_ab` | Learning-only | Payload-identical within overlap |
|---|---:|---:|---:|---:|
| weather | 3,374 | 3,368 | 6 | 3,260 |
| exhibition | 16,128 | 16,020 | 108 | **16,020** |
| entry | 20,244 | 20,208 | 36 | 19,956 |
| race condition | 3,374 | 3,368 | 6 | 3,260 |
| racer condition | 20,244 | 20,208 | 36 | 19,932 |

Across odds plus these five tables:

- total `learning_all` identities: **459,654**
- identities also present under `final_ab`: **458,502**
- identity overlap: **99.75%**
- `learning_all`-only identities: **1,152**

The exhibition overlap is especially strong: all `16,020` overlapping rows had identical non-identity payloads.

## Consumer search and Production-path boundary

A bounded repository search for the literal `learning_all` found:

- the learning producer wrapper itself;
- service-map/documentation references;
- a routing safety test;
- Railway bridge variable allowlisting;
- repository classification text.

No hard-coded Production model/decision/LINE consumer of the literal `learning_all` label was found.

The currently scheduled Production chain instead has an explicit `final_ab` default:

- `run_final_pg.py`: sets `SNAPSHOT_LABEL=final_ab` and `DECISION_LABEL=final_ab` if absent;
- `v25_final_realtime_pipeline_pg.py`: defaults `SNAPSHOT_LABEL` to `final_ab` and passes the same label through collection, targeted v22 decision, exhibition Shadow, and notifier stages;
- `v22_realtime_decision_engine_pg.py`: defaults `SNAPSHOT_LABEL` to `final_ab`;
- `run_v22_targeted_pg.py`: passes the requested snapshot label into the realtime fetch path and contains no `learning_all` literal;
- `v22_exhibition_shadow_pg.py`: defaults `SNAPSHOT_LABEL` to `final_ab`;
- `v23_line_notifier_batch_pg.py`: derives its decision label from `final_ab` by default;
- `run_nightly_results_pg.py`: uses `SNAPSHOT_LABEL=final_ab` by default for its scheduled post-race chain.

Railway Production variable-name inspection is consistent with this separation:

- `cron-final-check` has no `LEARNING_*` variables and currently relies on its final wrapper/default chain;
- `cron-learning-all` owns `LEARNING_ALL_ENABLED`, `LEARNING_SNAPSHOT_LABEL`, and its learning-window variables.

The learning wrapper itself only launches `v21_realtime_collector_pg_safe.py`, uses a separate target-race-id file, and explicitly states no LINE, no Production judgment, and no purchase processing.

## CI contract added by this Draft

`tests/test_learning_all_redundancy_contract.py` now freezes the current isolation assumptions in CI. It fails if the known scheduled final/nightly chain starts hard-coding `learning_all`, stops defaulting to `final_ab`, or if the learning wrapper gains decision/notifier/purchase wiring.

This is a static contract. It does **not** prove that every ad-hoc historical/research script is independent of `learning_all`.

## Remaining generic-consumer risk

Generic `snapshot_label` consumers exist in the repository. Some historical/research analysis code reads realtime snapshot tables by label or iterates labels without hard-coding `learning_all`.

Therefore:

- literal Production consumer absence is strong evidence that the label is not required by the scheduled decision/LINE chain;
- it is not sufficient to authorize deletion of historical `learning_all` rows;
- it is not sufficient to authorize a Production Cron/service change without a reversible natural-run observation.

## Capacity implication

The avoidable cost is not only Railway process runtime. The duplicate service creates a second label identity for almost the entire same pre-deadline race/ticket population across multiple large tables.

Stopping future duplicate collection could slow growth materially, especially in `v2_realtime_odds_snapshots`, but this research deliberately does not claim that deleting rows would proportionally shrink the Railway volume. PostgreSQL row deletion/plain VACUUM mainly creates reusable internal space; physical volume shrink requires a separate high-impact reclaim plan.

## Safest future validation sequence

Any Production change requires separate explicit approval.

1. Keep the current static CI consumer contract green.
2. Immediately before any approved observation, recheck Railway service configuration and current natural overlap.
3. Prefer a reversible observation: make the learning wrapper no-op while leaving `cron-final-check` untouched. This is a Production setting/behavior change and therefore requires explicit approval before execution.
4. Observe at least one full eligible natural race day without manual rerun/backfill.
5. Required pass conditions:
   - final-check continues to cover expected deadline-window races;
   - official odds completeness remains normal;
   - final decision/LINE path remains normal;
   - nightly reports/evaluations do not report missing required snapshot data;
   - no scheduled job requests `learning_all` explicitly;
   - DB growth attributable to duplicate labels stops as expected.
6. Immediate rollback if any required downstream job or audit reports a missing-data regression attributable to the absent learning run.
7. Only after the observation passes should permanent Cron retirement or a historical-row retention/deletion contract be considered under another explicit approval.

## Current decision

`LIVE_DUPLICATION_QUANTIFIED / LEARNING_IDENTITY_OVERLAP_99_75PCT / PRODUCTION_LITERAL_CONSUMER_NOT_FOUND / SCHEDULED_FINAL_AND_NIGHTLY_DEFAULT_FINAL_AB / STATIC_CONSUMER_ISOLATION_CONTRACT_ADDED / GENERIC_RESEARCH_LABEL_CONSUMPTION_RISK_REMAINS / REVERSIBLE_NATURAL_OBSERVATION_REQUIRED / NO_SERVICE_DISABLE_AUTHORIZED / NO_CRON_CHANGE / NO_DB_DELETE / NO_PRODUCTION_CHANGE`
