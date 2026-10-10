# V4 Production runtime source inventory — 2026-09-16

## Fresh override — 2026-09-21 12:42 JST

Fresh Railway Production configuration audit against project `boat-v2-postgres` / Production reconfirmed these candidate-shadow execution surfaces:

| service | current source | start command | schedule | current relevance |
|---|---|---|---|---|
| `cron-window-morning` | `boat-ai-v2@main` | `python -u run_window_pipeline_pg.py` | `15 23 * * *` UTC | active PRE writer invocation |
| `cron-window-day` | `boat-ai-v2@main` | `python -u run_window_pipeline_pg.py` | `35 0 * * *` UTC | active PRE writer invocation |
| `cron-window-night` | `boat-ai-v2@main` | `python -u run_window_pipeline_pg.py` | `35 5 * * *` UTC | active PRE writer invocation |
| `cron-nightly-results` | `boat-ai-v2@main` | `python -u run_nightly_results_pg.py` | `30 14 * * *` UTC | evaluator/report consumer path |
| `test-beforeinfo-extra` | `boat-ai-v2@main` | `python -u collect_candidate_filter_shadow_pg.py` | none | repository-triggerable direct writer |

All five returned `staged=null` in the fresh config reads. No secret values were read; only variable names were inspected.

Natural runtime evidence on 2026-09-21 additionally proves the configured PRE writer path is live:
- morning deployment `6dbbc230-806d-4345-8914-b7710c89cab0`: collector invoked, `candidate_rows=0 / saved_rows=0`;
- day deployment `fd1bf599-0d0b-4883-a147-a264b1f1b741`: collector invoked, `candidate_rows=7 / saved_rows=7`;
- formal V4 run `35549611949` subsequently consumed `legacy_shadow_rows=7`.

Current main at this override is `8867b77569d836b6c02a075fa6444550b1a46a6c`.

Therefore the runtime-source gate remains:
`RAILWAY_WRITER_SURFACES_PRESENT / SAME_DAY_RUNTIME_WRITE_CONFIRMED / CURRENT_MAIN_V4_READER_CONFIRMED / ZERO_CONSUMER_NOT_REACHED / NO_PRODUCTION_MUTATION / NO_DELETE`

Machine-readable snapshot:
`research/evidence/candidate_shadow_zero_consumer_gate_20260921.json`

The older inventory below remains historical context and is superseded where current SHA/config/runtime facts differ.


Status: `READ_ONLY_RAILWAY_CONFIG_AUDIT / NO_RAILWAY_MUTATION / ZERO_CONSUMER_GATE_STILL_CLOSED`

This document freezes a fresh Railway Production service/source audit for Draft PR #363. It exists because a repository-only scan of `main` is not sufficient to prove zero consumers: Railway Production can point at another branch or contain inline/manual service commands that do not exist in the default branch.

No Railway variable, Cron, service, volume, deployment, database row/schema, LINE behavior, model/threshold, Forward persistence, or purchase behavior was changed by this audit. `purchase_action=false` remains mandatory.

## 1. Source-of-truth boundary

- GitHub `main` remains the code Source of Truth: `61f7d6e75629ffb549a583f00bfd5dd58c186a71` at this audit.
- Railway PostgreSQL remains the Production-data Source of Truth.
- A destructive/archive cutover gate must nevertheless inspect the **actual Railway Production source branch and start command** for every Production service, because a live service may temporarily execute a non-main branch or an inline command.
- Draft PR #363 changes are not current-main state and do not authorize deletion.

## 2. Scheduled/current Production service entrypoints rechecked

The following Railway Production configs were read directly with no mutation.

| Railway service | source | start command | schedule | archive/legacy relevance |
|---|---|---|---|---|
| `cron-data-prepare` | repo `boat-ai-v2`, branch `main` | `python -u run_daily_data_prepare_pg.py` | `30 21 * * *` | current-day base-data readiness; KEEP ONLINE |
| `cron-final-check` | repo `boat-ai-v2`, branch `main` | `python -u run_final_pg.py` | `*/15 23,0-14 * * *` | active old FINAL chain; blocks legacy decision/LINE retirement |
| `cron-nightly-results` | repo `boat-ai-v2`, branch `main` | `python -u run_nightly_results_pg.py` | `30 14 * * *` | candidate-shadow evaluation/report variables still present; blocks candidate-shadow deletion |
| `cron-window-morning` | repo `boat-ai-v2`, branch `main` | `python -u run_window_pipeline_pg.py` | `15 23 * * *` | PRE path; candidate-shadow variables present |
| `cron-window-day` | repo `boat-ai-v2`, branch `main` | `python -u run_window_pipeline_pg.py` | `35 0 * * *` | PRE path; candidate-shadow variables present |
| `cron-window-night` | repo `boat-ai-v2`, branch `main` | `python -u run_window_pipeline_pg.py` | `35 5 * * *` | PRE path; candidate-shadow variables present |
| `cron-daily-report` | repo `boat-ai-v2`, branch `main` | `python -u run_daily_status_report.py` | `50 14 * * *` | report path retained; send behavior remains separately controlled |
| `cron-monthly-report` | repo `boat-ai-v2`, branch `main` | `python -u run_monthly_performance_report.py` | `0 0 1 * *` | report path retained; send behavior remains separately controlled |
| `cron-racer-course-stats` | repo `boat-ai-v2`, branch `main` | `python -u collect_racer_course_stats_pg.py` | `15 22 * * *` | V4/new-system input; KEEP ONLINE |
| `historical-backfill` | repo `boat-ai-v2`, branch `main` | `python -u diagnose_motor2_parser_pg.py` | `0 0 1 * *` | diagnostic service name is misleading; actual entrypoint is Motor2 parser diagnostic |
| `backtest-analysis` | repo `boat-ai-v2`, branch `main` | `python -u collect_v24_motor2_forward_shadow_pg.py` | `0 0 1 * *` | Motor2 Forward collector; not the historical backtest script implied by service name |
| `cron-learning-all` | repo `boat-ai-v2`, branch `main` | `python -u run_learning_all_realtime_pg.py` | `*/15 23,0-14 * * *` | protected realtime evidence / previous-odds semantics; KEEP unless replaced with proven equivalent |
| `cron-opponent-pressure-v2-live` | repo `boat-ai-v2`, branch **`runtime/opponent-pressure-railway-cron`** | `python -u .github/scripts/opponent_pressure_shadow_v2_compact.py` | `0 22 * * *` | V4/new-system input; non-main runtime branch must be included in every zero-consumer scan |

All configs above reported `staged=null` at this audit.

### Non-main runtime branch finding

`cron-opponent-pressure-v2-live` is the important exception to a main-only scan. Railway Production currently points at `runtime/opponent-pressure-railway-cron`, not `main`.

The exact runtime file was fetched from that branch. It reads historical race entries/results to construct Opponent Pressure and writes `v2_opponent_pressure_shadow_v2`; it did **not** contain direct references to `v2_odds_trifecta` or `v2_realtime_*` in the inspected file.

This does not change the GitHub-main Source-of-Truth policy. It means the final Production dependency gate must compare main **and every branch actually referenced by Railway Production** before declaring zero consumers.

## 3. Additional Production service surfaces that must not be ignored

### `test-beforeinfo-extra`

Railway Production config currently points at repo `main` and start command:

`python -u collect_candidate_filter_shadow_pg.py`

The service has no Cron schedule, but the deploy config contains a one-replica region setting, candidate-shadow variables, and repository watch patterns including top-level Python files. The invoked script is not read-only: current main can create/alter/deduplicate/write `v2_candidate_filter_shadow` and reads same-day `v2_odds_trifecta`.

This is not merely a theoretical config surface. Railway deployment `f047dabd-1179-4e87-bc0f-2a0a1e513f80`, triggered from main commit `8abbb0186852969129175848ee106118031f97e4`, completed SUCCESS on 2026-09-12 and its runtime log reported:

- `TARGET_DATE=2026-09-12 WINDOW_NAME=day ENABLED=True REQUIRE_COMPLETE_ODDS=True`
- `races=156 ready_races=120 skipped_entries=0 skipped_odds=36`
- `candidate_rows=11 saved_rows=11`
- S01/S02/S03 matched `1/5/5`

Later main changes outside its watch scope were recorded as `SKIPPED`, which does **not** prove retirement: a future matching repository change can still trigger the configured start command unless the service is separately retired/isolated under an approved Production change.

Therefore this service is an additional Production execution surface for the old candidate-shadow chain even though its name looks like a test service. It must be included in Issue #360 zero-consumer/retirement proof. No redeploy or config change was made by this audit.

### `cron-opponent-pressure-v2-runner`

This separate service points at `main`, runs the same Opponent Pressure compact script, has no Cron schedule, and has a one-replica deploy config. Its latest deployment in the status snapshot is `FAILED` from 2026-09-10. It is not used as evidence that the live scheduled service is unhealthy; `cron-opponent-pressure-v2-live` remains the scheduled SUCCESS path.

Do not redeploy this old runner merely for audit purposes.

## 4. Dormant/manual/audit service safety inventory

These Production-environment services are not justification for deleting them or redeploying them. They are listed so future audits do not accidentally treat a service name as harmless without reading its actual start command.

### `storage-maintenance-once` — destructive command retained in config

The service uses image `python:3.12-slim`, has no Cron schedule, and its configured inline start command contains guarded PostgreSQL checks followed by:

`DROP INDEX CONCURRENTLY public.idx_v2_odds_race_date`

The current audit **did not execute or redeploy** this service and does not infer any new action from its old deployment history. Its existence is a strong reason to keep the rule: no Production audit service is redeployed casually.

Classification: `DORMANT_MANUAL_PRODUCTION_SURFACE / DESTRUCTIVE_START_COMMAND_PRESENT / DO_NOT_REDEPLOY_FOR_AUDIT`.

### `storage-index-drop-once`

The service remains present with image `python:3.12-slim`, no Cron schedule, and no start command returned in the current config read. No change was made.

### Snapshot/Motor2 audit services

`v2-motor2-shadow-audit`, `pg-snapshot-audit`, `pg-snapshot-inspect`, and `snapshot-audit-readonly` remain separate Production-environment audit/inspection surfaces. Their current configs are not part of normal scheduled model execution. `pg-snapshot-audit` still shows an old CRASHED deployment; the others have prior SUCCESS deployments.

Do not redeploy any of these solely to refresh an audit. Existing GitHub Actions read-only paths are preferred for new evidence collection.

## 5. Revised zero-consumer proof contract

A future `ZERO_CONSUMER=PASS` for an old-history table or label is invalid unless all of the following are checked from a fresh snapshot:

1. current GitHub `main` direct and indirect executable consumers;
2. every Railway Production service's actual `source.repo`, `source.branch`, and `startCommand`;
3. every non-main branch currently referenced by a Railway Production service;
4. inline/image-backed Railway start commands that have no GitHub source file;
5. scheduled services, continuously configured services, repository-triggered/no-Cron services, manual/no-Cron services, and diagnostic/maintenance services separately classified;
6. workflow-dispatch / owner-command GitHub Actions paths that can still read Production history;
7. Draft-only retirement/guards are not counted as current-main removal until landed under the applicable approval boundary;
8. ambiguous or unreachable service config => fail closed, not “probably unused”.

A service being named `test`, `audit`, `backtest`, `historical`, or `once` is not classification evidence. Actual source/start command and deploy trigger behavior control.

## 6. Current implications

- `v2_candidate_filter_shadow` zero-consumer proof is **not reached**: PRE windows, nightly evaluation, V4 legacy carryover on current main, and `test-beforeinfo-extra` still provide current Production dependencies/execution surfaces.
- `v2_realtime_decisions` / `v2_line_notifications` remain tied to the active FINAL/LINE chain until that chain is separately retired/replaced.
- `v2_realtime_odds_snapshots` remains shared/new-system-required Stage2 market evidence and is not a legacy-delete target.
- `learning_all` remains protected because of its previous-odds/drift/steam semantics and is not a capacity-driven stop/delete candidate.
- historical base odds can continue archive/read-through research, but Production old-row deletion remains blocked by permanent-archive, recovery, fresh-restore, headroom, and explicit-approval gates.

## 7. Current gate

`MAIN_ONLY_SCAN_INSUFFICIENT / RAILWAY_RUNTIME_BRANCH_SCAN_REQUIRED / OPPONENT_LIVE_NONMAIN_BRANCH_ACCOUNTED / TEST_BEFOREINFO_EXTRA_CONFIRMED_WRITER_DEPLOY_SURFACE / DORMANT_DESTRUCTIVE_MAINTENANCE_COMMAND_IDENTIFIED_NO_REDEPLOY / ZERO_CONSUMER_NOT_REACHED / NO_PRODUCTION_MUTATION / NO_DELETE / PURCHASE_FALSE`
