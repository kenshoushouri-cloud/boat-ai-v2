# Railway Service Map

Last verified: 2026-08-24 JST

Source of truth:
- Code / workflow: GitHub `main`
- Production data: Railway PostgreSQL (`boat-v2-postgres` / service `postgres`)
- Railway service Start Command / cron: fresh owner-only Issue #42 `/railway inventory` audit at main `13a2c9127f1364523b0084c552acfb49277f462d`

This map is for identifying which file to change when improving prediction accuracy or diagnosing an operational problem. Cron expressions below are Railway UTC; JST is shown separately.

## Current Railway inventory

| Railway service | Start Command | Railway cron (UTC) | Approx. JST | Main chain / role | Primary DB writes | LINE / Production role |
|---|---|---:|---|---|---|---|
| `backtest-analysis` | `python -u collect_v24_motor2_forward_shadow_pg.py` | `0 0 1 * *` | 1st 09:00 | Motor2 Forward Shadow collector | `v2_v24_motor2_forward_shadow` | Shadow only; no Production decision / LINE |
| `cron-daily-report` | `python -u run_daily_status_report.py` | `50 14 * * *` | daily 23:50 | `run_daily_status_report.py` → `v28_daily_status_report_line.py` | `v2_line_notifications` (`daily_report`) | Sends daily LINE status report; does not create BUY/WATCH/SKIP |
| `cron-data-prepare` | `python -u run_daily_data_prepare_pg.py` | `30 21 * * *` | daily 06:30 | `run_daily_data_prepare_pg.py` → `repair_month_all_pg.py` → odds quality audit | primarily `v2_races`, `v2_race_entries`, `v2_odds_trifecta` (plus venue/data-prep support rows) | Data preparation only; no prediction notification |
| `cron-final-check` | `python -u run_final_pg.py` | `*/15 23,0-14 * * *` | every 15 min, ~08:00–23:45 | `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` → v21 realtime collection → Motor2/N02 optional Shadows → targeted v22 → exhibition Shadow → v23 notifier | realtime snapshot tables, `v2_v24_motor2_forward_shadow`, other FINAL Shadow tables, `v2_realtime_decisions`, `v2_line_notifications` | **Production FINAL**: creates BUY/WATCH/SKIP decisions and sends BUY LINE notifications; no purchase execution |
| `cron-learning-all` | `python -u run_learning_all_realtime_pg.py` | `*/15 23,0-14 * * *` | every 15 min, ~08:00–23:45 | learning wrapper → `v21_realtime_collector_pg.py`, scope=`all`, label=`learning_all` | `v2_realtime_*_snapshots` used by v21 | Learning/snapshot collection only; explicitly no Production judgment / LINE |
| `cron-monthly-report` | `python -u run_monthly_performance_report.py` | `0 0 1 * *` | 1st 09:00 | `run_monthly_performance_report.py` → `v27_performance_report_line.py` | notification log (`v2_line_notifications`) | Sends previous-month + cumulative LINE report; no decision creation |
| `cron-nightly-results` | `python -u run_nightly_results_pg.py` | `30 14 * * *` | daily 23:30 | results-only `repair_month_all_pg.py` → Candidate Filter / N02 / Exhibition / Motor2 evaluation + robustness/health reports | `v2_results`; updates/evaluates Shadow result fields/tables | Post-race learning/evaluation only; no Production BUY/WATCH/SKIP or purchase |
| `cron-racer-course-stats` | `python -u collect_racer_course_stats_pg.py` | `15 22 * * *` | daily 07:15 | BOAT RACE official racer course-stat snapshot | `v2_racer_course_stats_snapshots` | Shadow/research input only; no Production decision / LINE |
| `cron-window-day` | `python -u run_window_pipeline_pg.py` | `35 0 * * *` | daily 09:35 | odds window → Motor2 Forward Shadow → PRE window → v24 pre notifier + Candidate Filter Shadow | `v2_odds_trifecta`, `v2_v24_motor2_forward_shadow`, `v2_candidate_filter_shadow`, notification log | PRE candidate LINE path; not FINAL BUY decision |
| `cron-window-morning` | `python -u run_window_pipeline_pg.py` | `15 23 * * *` | daily 08:15 | same pipeline, `WINDOW_NAME=morning` | same as day window | PRE candidate LINE path; not FINAL BUY decision |
| `cron-window-night` | `python -u run_window_pipeline_pg.py` | `35 5 * * *` | daily 14:35 | same pipeline, `WINDOW_NAME=night` | same as day window | PRE candidate LINE path; not FINAL BUY decision |
| `historical-backfill` | `python -u diagnose_motor2_parser_pg.py` | `0 0 1 * *` | 1st 09:00 | Motor2 parser diagnostic against official page | **none** (`READ_ONLY=1 DB_UPDATE=0`) | Despite service name, current command is diagnostic only; no LINE / BUY |
| `postgres` | `-` | `-` | continuous | Railway PostgreSQL | Production DB | Production data Source of Truth |
| `test-beforeinfo-extra` | `python -u collect_candidate_filter_shadow_pg.py` | `-` | manual/no cron | standalone Candidate Filter Shadow collector | `v2_candidate_filter_shadow` | Shadow only; no `v2_realtime_decisions`, no purchase, no LINE |

## Prediction / notification chains

### Daily data preparation

```text
cron-data-prepare
└─ run_daily_data_prepare_pg.py
   └─ repair_month_all_pg.py
      ├─ race / deadline / entries
      └─ pre-race trifecta odds
   └─ audit_target_date()
```

Important correction: the entries table is **`v2_race_entries`**, not `v2_entries`.

### PRE windows

```text
cron-window-morning / day / night
└─ run_window_pipeline_pg.py
   ├─ run_odds_window_pg.py
   │  └─ v2_odds_trifecta
   ├─ collect_v24_motor2_forward_shadow_pg.py
   │  └─ v2_v24_motor2_forward_shadow
   └─ run_pre_window_pg.py
      ├─ v24_pre_candidate_notifier_pg.py
      │  └─ PRE candidate notification path
      └─ collect_candidate_filter_shadow_pg.py
         └─ v2_candidate_filter_shadow
```

Current PRE windows defined in code:
- morning: 08:30–10:15 JST
- day: 09:45–15:00 JST
- night: 14:45 onward

The window pipeline passes only its selected `TARGET_RACE_IDS` forward. Historical/future replay is guarded; replay forces DRY_RUN/TEST_MODE and can disable Candidate Shadow.

### FINAL

```text
cron-final-check
└─ run_final_pg.py
   └─ v25_final_realtime_pipeline_pg.py
      ├─ v21_realtime_collector_pg.py
      │  └─ realtime weather / exhibition / entry / odds / condition snapshots
      ├─ collect_v24_motor2_forward_shadow_pg.py      [Shadow]
      ├─ collect_n02_windlt4_final_shadow_pg.py      [Shadow]
      ├─ collect_wave_venue_lane_final_shadow_pg.py  [optional Shadow; default OFF]
      ├─ run_v22_targeted_pg.py
      │  └─ v22_realtime_decision_engine_pg.py
      │     └─ v2_realtime_decisions (BUY / WATCH / SKIP)
      ├─ v22_exhibition_shadow_pg.py                 [Shadow]
      └─ v23_line_notifier_batch_pg.py
         ├─ reads BUY rows from v2_realtime_decisions
         └─ v2_line_notifications + LINE push
```

`v25_final_realtime_pipeline_pg.py` explicitly states that Shadow stages do not change Production BUY/WATCH/SKIP or LINE targets. Wave Shadow is non-fatal and default OFF. There is no automatic purchase execution; the production action is final decision storage + LINE notification.

## Which file to change for which problem

| Goal / symptom | First files to inspect | Do not change first |
|---|---|---|
| Race card / deadline / entry parsing | `repair_month_all_pg.py`, `run_daily_data_prepare_pg.py` | FINAL selector |
| Window odds missing / partial | `run_odds_window_pg.py`, odds parser in `repair_month_all_pg.py` | probability formula |
| PRE probability / candidate selection | `v24_pre_candidate_notifier_pg.py` | FINAL realtime judge |
| Candidate Filter research | `collect_candidate_filter_shadow_pg.py` | Production selector |
| Motor2 Forward research | `collect_v24_motor2_forward_shadow_pg.py` | Production BUY rules |
| Realtime official data collection | `v21_realtime_collector_pg.py` | PRE formula |
| FINAL BUY/WATCH/SKIP | `v22_realtime_decision_engine_pg.py`, wrapper `run_v22_targeted_pg.py` | LINE formatting first |
| FINAL pipeline ordering / optional Shadows | `v25_final_realtime_pipeline_pg.py` | individual parsers unless data is wrong |
| FINAL LINE send / duplicate / quota handling | `v23_line_notifier_batch_pg.py` | decision formula |
| Daily LINE report | `v28_daily_status_report_line.py` | FINAL notification path |
| Monthly LINE report | `v27_performance_report_line.py` | FINAL notification path |
| Post-race result ingestion / evaluation order | `run_nightly_results_pg.py`, `repair_month_all_pg.py` | live selectors |
| Racer × course snapshot collection | `collect_racer_course_stats_pg.py` | historical race rows |
| Motor parser diagnosis | `diagnose_motor2_parser_pg.py` | DB writes — current diagnostic is read-only |

## Safety boundaries

- GitHub main is not edited directly: branch → Draft PR → CI → review → merge.
- Railway PostgreSQL is the production data Source of Truth.
- Shadow evidence alone must never change Production BUY/WATCH/SKIP or LINE behavior.
- Historical/replay validation uses DRY_RUN / TEST_MODE and must not send LINE.
- `cron-final-check` is the highest-risk service because it owns Production final decisions and LINE; changes here require extra review.
- `cron-learning-all`, `backtest-analysis`, `test-beforeinfo-extra`, racer-course stats and research Shadows are not promotion authority.
- Service names are not sufficient to infer behavior: always use the current Start Command. `historical-backfill` is the concrete example — its current command is a read-only diagnostic.
