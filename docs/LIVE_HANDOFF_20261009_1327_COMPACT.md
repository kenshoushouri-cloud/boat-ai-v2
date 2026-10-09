# Compact Handoff 2026-10-09 13:27 JST

## Project / operating rules
- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Production = **V4 only**. V5/V5.1 = research-only.
- System body completion first. **Automatic purchase is deferred until the very end.**
- One work item per turn; tool calls minimal. No bulk history / all Actions / all services / all logs.
- Never duplicate a pending command without proving no run exists. No polling loops.
- Railway Agent/AI prohibited.
- Railway cost target <= USD20/month, ideally <= USD15; minimize CPU/RAM/network.
- Do not change purchase / stake / Production model / plan / volume resize-delete without explicit approval.
- Historical research/backtest period remains **2025-07-01..2026-10-05**. Do not extend it with 10/6+ operational data.
- Raw data is preserved. REJECT_INPUT means model exclusion, not deletion.
- User wants **estimated execution time shown whenever a run is launched**.

## LINE change completed
User decided provisional LINE alerts are unnecessary because future operation assumes automation.
Implemented:
- PRE computation / morning-day-night pipelines / Shadow collection continue.
- **PRE candidate LINE sending is disabled by default.**
- FINAL BUY LINE notification remains.
- Code commit: `ba7be659247112702d7a2b43fcf715d6a5360bdd`
- morning/day/night deployments all reached SUCCESS.
Do not disable the morning/day/night commands themselves.

## V5 research state
Strong-core weighted candidate:
**lane + class + recent form 0.50 + exhibition time rank 1.00 + racer-course 0.75 + opponent 1.25 + venue-lane residual 0.75**
Calibration: T=1.00, no extra calibration.
Train-only tuning improved frozen OOS; weight tuning is a strong adoption candidate.
Freeze readiness remains gated by formal V4 / prospective S03_M2 / evidence cleanliness.
Do not promote V5 to Production without explicit review/freeze decision.

## Incident handling
Formal contract exists:
`docs/RACE_INCIDENT_HANDLING_CONTRACT_20261009.md`
commit `a68ccdbe218bb035a2b9e574b0b4a1e3086f421b`
Principles:
- no raw deletion;
- pre-deadline scratch => fail-closed for six-boat model;
- in-race incidents preserve timing-clean prediction evidence but are excluded from primary ability/core fitting initially;
- whole-race cancellation => VOID / zero investment / no training;
- timing unknown => fail-closed for primary fitting.
Participant-level historical eligibility should be finalized only after result-entry coverage is complete.

## Result-entry backfill progress
Official K-file historical detail backfill:
- 2026-08-21..08-31: **11/11 PASS**
- 2026-09-01..09-30: **30/30 PASS**
Read-only preflight after those writes:
- range 2026-08-01..2026-10-05
- TOTAL_RACES=10380
- COMPLETE_RACES=9517
- MISSING_RACES=863
- PARTIAL_RACES=0
- DAYS_WITH_MISSING=9
- missing days:
  - 2026-08-11 missing12 / complete168 / total180
  - 2026-09-09 missing12 / complete132 / total144
  - 2026-09-21 missing35 / complete121 / total156
  - 2026-09-22 missing12 / complete156 / total168
  - 2026-10-01 missing168 / complete0 / total168
  - 2026-10-02 missing168 / complete0 / total168
  - 2026-10-03 missing156 / complete0 / total156
  - 2026-10-04 missing156 / complete0 / total156
  - 2026-10-05 missing144 / complete0 / total144
The 8/11 and September partial-day residuals must be classified read-only after 10/1-5 completion; likely official K structural/availability differences, do not fabricate.

## 2026-10-01..10-05 current active work
Attempted `v2_result_entries` backfill stopped safely at 10/1 because `v2_results=0/168`.
Therefore top-level `v2_results` must be restored first.

Created results-only workflow:
`.github/workflows/railway-candidate-v4-results-repair-20261001-05.yml`
- RACES=0
- RESULTS=1
- ODDS=0
- workers=2
First run timed out at exactly 30 minutes; GitHub run `37878920159` concluded cancelled, not a confirmed DB processing error.
Workflow timeout was extended **30 -> 90 minutes**:
commit `8a42ee8778c807419ddf20973d5cf88919367b9f`

### Last results-only repair — CLOSED / CANCELLED
- Issue #581 command comment `6074271031` completed with bot result `6075249663`: FAILED.
- GitHub run `37884046769` ended `cancelled` after ~90 min; step "Repair results only" cancelled.
- The underlying process output was redirected to a temporary log that the workflow deleted. DB per-day progress is **unknown**, not zero.
- **Do not rerun** full 2026-10-01..05 repair without a read-only coverage audit and a date-scoped plan.

### Oct 1-5 read-only coverage audit — COMPLETED / PASS
- Issue #581 audit command comment: `6075339999`.
- Bot result comment: `6075344857` — `RESULTS_COVERAGE_AUDIT_20261001_05_PASS`.
- DB: `postgres-hobby-fullhistory-candidate-v4`; transaction READ ONLY.
- `v2_races` vs `v2_results` by date:
  - 2026-10-01: BASE=168, RESULTS=168, MISSING=0, EXTRA=0
  - 2026-10-02: BASE=168, RESULTS=168, MISSING=0, EXTRA=0
  - 2026-10-03: BASE=156, RESULTS=156, MISSING=0, EXTRA=0
  - 2026-10-04: BASE=156, RESULTS=156, MISSING=0, EXTRA=0
  - 2026-10-05: BASE=144, RESULTS=0, MISSING=144, EXTRA=0
  - TOTAL: BASE=792, RESULTS=648, MISSING=144, EXTRA=0.
- All results for Oct 1-4 are present; only Oct 5 needs RESULTS repair. The earlier 90-minute five-day command was cancelled and **must not be relaunched**.
- This audit made no DB changes. Raw repair progress before the audit is unknown.

## Oct 05 missing-only RESULTS repair — COMPLETED / PASS
- Issue #581 command `6075467401`, result comment `6075638332`.
- GitHub run `37892542149`: completed SUCCESS, 2026-10-09 15:27 JST (~13 min).
- Target DB: `postgres-hobby-fullhistory-candidate-v4`.
- Target **2026-10-05 only**: before BASE=144, RESULTS=0, MISSING=144; processed 144/144 success, 0 failures; DB after BASE=144, RESULTS=144, MISSING=0, EXTRA=0.
- `RESULTS_REPAIR_OCT05_VERIFIED_PASS` and process exit 0.
- Combined 2026-10-01..05 `v2_results`: 792/792 confirmed (Oct1=168, Oct2=168, Oct3=156, Oct4=156, Oct5=144). Do NOT rerun either previous RESULTS repair.
- No Production model / LINE / purchase / stake / Railway plan or volume change.

## 2026-10-01..05 result-entry backfill — COMPLETED / PASS
- Issue #581 command comment `6075666638`.
- GitHub bot result comment `6075705473`, received 2026-10-09 15:33 JST: `CANDIDATE_V4_OCT01_05_RESULT_ENTRIES_BACKFILL_PASS`, exit code 0.
- Official K daily records (all days PASS, `STOP_ON_ERROR=True`):
  - 10/01: 168 races, 1008 `v2_result_entries`, normal=994, accident=14.
  - 10/02: 168 races, 1008 rows, normal=985, accident=23.
  - 10/03: 156 races, 936 rows, normal=918, accident=18.
  - 10/04: 156 races, 936 rows, normal=924, accident=12.
  - 10/05: 144 races, 864 rows, normal=848, accident=16.
- **Total: 792/792 races, 4752 result-entry rows, 5/5 days PASS, no parser errors, duplicate race IDs or incomplete6, failed_days=0.**
- `v2_results` top-level was already confirmed 792/792 from previous read-only audit and Oct 05 fix.
- No relaunch needed; do not repost command. No Production model, LINE, BUY, stake, plan or volume change.

## Next ONE task
Run the existing **read-only result-entry coverage preflight** for historical period 2026-08-01..2026-10-05, specifically confirming the 2026-10-01..05 detail coverage and current residual dates. Inspect only the specific relevant workflow and pending command first. Show estimated runtime before triggering; avoid duplicate or bulk runs.
Then classify any remaining 8/11 and September residual gaps without fabricating data; rerun incident inventory only after coverage is finalized; proceed to V5 final backtest/freeze review. Production=V4; V5/V5.1 research-only. Automatic purchase LAST. Railway Agent/AI prohibited; target monthly cost <=USD20, ideally <=USD15.

`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
