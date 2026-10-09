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

## 2026-08-01..10-05 result-entry audit — COMPLETED / PASS
- Issue #581 command `6075853528`; bot result `6075857637` reports `RESULT_ENTRIES_COVERAGE_AUDIT_20260801_1005_PASS`.
- Read-only period 66 days: BASE_RACES=10380, COMPLETE6=10309, MISSING=71, PARTIAL=0, OVER6=0, RESULT_ENTRY_ROWS=61854, GAP_DAYS=4.
- 2026-10-01..05: all 792/792 complete with 4752 detail rows, MISSING=0. Do not rerun October backfill.
- Remaining missing (race has ZERO result-entry rows): 2026-08-11=12, 2026-09-09=12, 2026-09-21=35, 2026-09-22=12. No partial6 or >6 anomalies. Do not invent missing official K rows.
- Historical backtest window remains 2025-07-01..2026-10-05, not 10/06+ data.

## 71 residual result-entry K classification — COMPLETE / PASS
- Issue #581 command `6076014344` and bot result `6076028310`: `K_RESIDUAL_CLASSIFICATION_71_PASS`.
- Read-only official K + DB inspection (2026-08-11, 09-09, 09-21, 09-22): DB_BASE=648, DB_MISSING=71, DB_PARTIAL_OR_OVER6=0.
- All **71** missing-entry race IDs are category **K_HEADER_UNPARSED**: loose `1R...12R` header present in K venue section, but strict `parse_header()` does not parse it into a normal race; result-entry count=0. ALL 71 have top-level `v2_results` rows. This is **NOT proof of cancellation** and does not justify fabricated result entries.
- By venue/date:
  - 08/11 江戸川(03) 1–12R = 12, DB status=official
  - 09/09 江戸川(03) 1–12R = 12, status=scheduled
  - 09/21 戸田(02) 1–12R = 12; 江戸川(03) 1–12R = 12; 津(09) 5–12R = 8; 三国(10) 10–12R = 3; all scheduled
  - 09/22 津(09) 1–12R = 12, scheduled.
- Previous full coverage read-only audit: 10380 base / 10309 complete6 / 71 missing; Oct01–05 all 792/792 complete. Raw data retained, Production V4 unchanged.

## Official K raw-header samples — COMPLETE / PASS
- Issue #581 command `6076185812`; bot result `6076196860`; GitHub Actions run `37897211423` completed SUCCESS, 2026-10-09 16:07 JST (~49 seconds).
- Scope: four official K files, nine bounded samples; GitHub-only read, NO DB or Railway operations.
- Seven sampled residual header lines explicitly say `中　止` (full-width space): Aug11 江戸川 1R, Sep09 江戸川 1R, Sep21 戸田 1R / 江戸川 1R / 津 5R / 三国 10R, Sep22 津 1R.
- Two adjacent non-residual lines Sep21 津 4R and 三国 9R contain payout records, corroborating the observed switch to cancellation on that day.
- Keyword detector returned `FLAGS=NONE` even for these explicit cancel lines because it searched literal `中止` without removing the full-width space. **Always normalize whitespace for the next classification.**
- Only 7 of 71 residual race IDs were individually inspected as cancelled. **Do NOT state all 71 verified yet.** Preserve raw data; never fabricate finish positions. Prior total: 10380 base / 10309 complete6 / 71 missing; Oct1–5 already complete.

## Sep 21 storm-related cancellations — user clarification
- User reports 2026-09-21 typhoon impacts causing **some venues to cancel all races** and **others to stop partway through the card**.
- This context is not by itself official verification of the cause for each individual race. Verify raw K header `中　止` (normalize full-width spaces) and race-by-race outcome before eligibility assignment.
- Existing sampled K evidence on 2026-09-21: 戸田(02) 1R cancelled, 江戸川(03) 1R cancelled, 津(09) 4R has payout / 5R cancelled, 三国(10) 9R has payout / 10R cancelled. Do not classify **all races** at partially interrupted venues as cancelled.
- Preserve every completed race's normal result/learning eligibility (subject to separate incident rules). Explicit cancelled races: `VOID` / no stake or learning. Never delete raw rows, fabricate finishing order or conflate `scheduled` in DB with a confirmed official result. Distinguish **pre-race cancellation** versus **during-race incident**, using official evidence.

## Exact 71/71 official K cancellation verification — COMPLETE / PASS
- Issue #581 command `6077489287`; GitHub Actions bot result `6077502477` `K_71_CLASSIFICATION_PASS`, process exit 0.
- Official K files for 2026-08-11, 09-09, 09-21, 09-22 downloaded OK (HTTP 200); **exact 71 residual race IDs** checked with whitespace-normalized explicit race-specific `中止` header.
- `SUMMARY AUDITED=71 CANCEL_EXPLICIT=71 OTHER_UNPARSED=0 NO_K_HEADER=0 CONFLICT=0` — no ambiguity remaining for these 71.
- 8/11 江戸川 (03) 1–12R =12; 9/9 江戸川 (03) 1–12R =12; 9/21 戸田 (02) 1–12R =12, 江戸川 (03) 1–12R =12, 津 (09) 5–12R =8, 三国 (10) 10–12R =3; 9/22 津 (09) 1–12R =12.
- **9/21 津 1–4R and 三国 1–9R ARE NOT among cancelled 71**; preserve their normal racing evidence. Other normal races remain subject to per-participant incident eligibility rules.
- Historic 8/01..10/05 `v2_races`: 10380 total, 10309 with complete six-entry results, 71 explicit official cancelled / no entry results. Those 71 are NOT data ingestion gaps and must NEVER be given fabricated finishing positions.
- This confirmation was **GitHub-only read-only**: NO database mutation, Railway call, training, or live system change.

## Next ONE task
Inspect formal `docs/RACE_INCIDENT_HANDLING_CONTRACT_20261009.md` and the actual **backtest/model eligibility code path** using narrowly scoped reads, then implement/test a safe, provenance-tracked **VOID / excluded-from-fitting** classification for these 71 cancellations, preferably starting with read-only / offline eligibility policy before any DB writes. No deletion of source rows, no fabricated finish results, no accidental exclusion of completed Sep21 races. Show estimated execution time before initiating any runtime job; one operation per turn. After incident inventory, V5 research-only backtest/freeze. Production V4; auto-purchase LAST; Railway Agent/AI prohibited; spending <=USD20/month ideally <=USD15.
`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
