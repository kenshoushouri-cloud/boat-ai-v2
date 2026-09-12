# Railway Service Map

Last verified: 2026-09-12 JST

This document is a compact current-state map. Service names are not trusted as behavior; always verify the current Railway Start Command and cron before changing anything.

## Source of Truth

- Code: GitHub `main`
- Production data: Railway PostgreSQL project `boat-v2-postgres`
- Active Production PostgreSQL service: **`postgres-recovery`**
- Legacy/inactive PostgreSQL service: `postgres` (no current deployment)
- Production service/config state: Railway Production environment

## Current Railway inventory

| Railway service | Start Command / role | Cron UTC | Approx. JST | Production significance |
|---|---|---:|---|---|
| `cron-data-prepare` | `python -u run_daily_data_prepare_pg.py` | `30 21 * * *` | daily 06:30 | race/entry/base-odds preparation |
| `cron-final-check` | `python -u run_final_pg.py` | `*/15 23,0-14 * * *` | ~08:00–23:45 / 15 min | **Production FINAL + LINE** |
| `cron-learning-all` | `python -u run_learning_all_realtime_pg.py` | `*/15 23,0-14 * * *` | ~08:00–23:45 / 15 min | learning snapshots; indirectly affects FINAL previous-odds features |
| `cron-nightly-results` | `python -u run_nightly_results_pg.py` | `30 14 * * *` | daily 23:30 | results/evaluation |
| `cron-window-morning` | `python -u run_window_pipeline_pg.py` | `15 23 * * *` | daily 08:15 | PRE path |
| `cron-window-day` | `python -u run_window_pipeline_pg.py` | `35 0 * * *` | daily 09:35 | PRE path |
| `cron-window-night` | `python -u run_window_pipeline_pg.py` | `35 5 * * *` | daily 14:35 | PRE path |
| `cron-daily-report` | daily status report | `50 14 * * *` | daily 23:50 | LINE status report |
| `cron-monthly-report` | monthly performance report | `0 0 1 * *` | 1st 09:00 | LINE monthly report |
| `cron-racer-course-stats` | `python -u collect_racer_course_stats_pg.py` | `15 22 * * *` | daily 07:15 | Course research source |
| `cron-opponent-pressure-v2-live` | Opponent Pressure V2 live Forward collector | `0 22 * * *` | daily 07:00 | active research/Forward service |
| `cron-opponent-pressure-v2-runner` | older runner service | none | continuous config / latest deploy failed | not the active scheduled collector; do not delete without approval |
| `cron-opponent-pressure-v2` | older service | none | inactive | preserve until separately reviewed |
| `backtest-analysis` | `python -u collect_v24_motor2_forward_shadow_pg.py` | `0 0 1 * *` | 1st 09:00 | Motor2 Forward Shadow; service name is historical |
| `historical-backfill` | `python -u diagnose_motor2_parser_pg.py` | `0 0 1 * *` | 1st 09:00 | **read-only Motor2 parser diagnostic**; despite its name, not a backfill job |
| `test-beforeinfo-extra` | `python -u collect_candidate_filter_shadow_pg.py` | none | manual | Candidate Filter Shadow |
| `postgres-recovery` | PostgreSQL with `postgres-volume` | none | continuous | **Production DB Source of Truth** |
| `postgres` | no current deployment | none | inactive | legacy service; do not use as current DB Source of Truth |

## Core execution chains

### PRE

```text
cron-window-morning/day/night
└─ run_window_pipeline_pg.py
   ├─ run_odds_window_pg.py
   ├─ collect_v24_motor2_forward_shadow_pg.py        [Shadow]
   └─ run_pre_window_pg.py
      ├─ v24_pre_candidate_notifier_pg.py            [PRE notification path]
      └─ collect_candidate_filter_shadow_pg.py        [Shadow]
```

### FINAL

```text
cron-final-check
└─ run_final_pg.py
   └─ v25_final_realtime_pipeline_pg.py
      ├─ v21_realtime_collector_pg.py
      ├─ optional/research Shadows
      ├─ run_v22_targeted_pg.py
      │  └─ v22_realtime_decision_engine_pg.py
      └─ v23_line_notifier_batch_pg.py
```

FINAL creates BUY/WATCH/SKIP decisions and can send LINE notifications. There is no automatic purchase execution.

### learning_all

```text
cron-learning-all
└─ run_learning_all_realtime_pg.py
   └─ v21_realtime_collector_pg.py
      └─ snapshot_label=learning_all
```

Important: `learning_all` is not output-neutral infrastructure. The shared previous-odds lookup can use a learning sample immediately before a `final_ab` sample, changing drift/steam features used by Production v22 scoring. Do not pause or rewrite this path as a simple capacity optimization.

### Opponent Pressure V2

The active scheduled service is `cron-opponent-pressure-v2-live` at 07:00 JST. Older similarly named services remain present but are not the active natural Cron. Keep them unchanged unless separately approved.

## Important naming corrections

- Correct entries table: `v2_race_entries`.
- Active Production DB service: `postgres-recovery`, not the legacy `postgres` service.
- `historical-backfill` currently runs a read-only parser diagnostic.
- `backtest-analysis` currently runs a Motor2 Forward Shadow collector.

## Change-risk guide

- Highest risk: `cron-final-check`, Production DB, LINE notifier, v22 decision logic.
- Production-sensitive despite its name: `cron-learning-all` because of cross-label previous-odds coupling.
- Research/Shadow: Opponent Pressure V2, Racer Course, Motor2 Forward, Candidate Filter and other Shadows.
- Service names alone are never sufficient evidence for deletion, disabling, or data-retention decisions.

## Safety boundaries

- GitHub: branch → Draft PR → CI → review → merge; do not edit `main` directly.
- Production Railway settings, Variables, Cron, service changes require explicit approval.
- Production DB writes/deletes/schema changes/VACUUM require explicit approval.
- Model coefficients, thresholds, Production decision logic and LINE behavior require explicit approval.
- Shadow evidence alone is not promotion authority.
- Historical/replay work uses fail-closed dry-run/test isolation and must not send LINE.
