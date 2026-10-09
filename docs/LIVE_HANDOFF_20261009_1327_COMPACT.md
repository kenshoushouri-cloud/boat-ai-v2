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

## Historical official VOID eligibility guard — OFFLINE MODULE ADDED (not yet wired)
- Official K cancellation evidence: Issue #581 bot comment `6077502477`; exact 71 race IDs verified explicit `中止`.
- Contract inspected: `docs/RACE_INCIDENT_HANDLING_CONTRACT_20261009.md` — whole-race cancellation is VOID, no learning, zero hypothetical investment, preserve raw evidence; noncancellation alone does **not** establish train/evaluation eligibility.
- Inspected existing V5 research backtests `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py`, `research/v5_strong_core_weight_tuning_pg.py`, `research/v5_strong_core_calibration_pg.py` and `research/v5_current_core_plus_venue_lane_pg.py`. They filter winner 1..6 and result statuses `official` when columns exist; this alone may not robustly exclude legacy cancellation rows. Any eligibility integration must guard against result leakage and retain normal Sep21 races.
- Added **pure research-only manifest** `research/historical_void_registry.py` at commit `dc2dbe443a2d7b06cd43ef79c839693df380b240`; static 7 date/venue/race ranges => 71 exact IDs, evidence ref `github_issue_581_comment_6077502477`. `classify_historical_void()` returns `VERIFIED_VOID` with training false, VOID, hypothetical investment 0 or `UNDETERMINED` (never implies eligible). No DB or Railway access.
- Added `tests/test_historical_void_registry.py` at commit `b4048d15c02d23308bfdde52ee4c15dea1911e9d`. Tested offline using Python stdlib: **6 tests PASS**, syntax compilation PASS; 71 boundaries + Sep21 津4R / 三国9R correctly excluded from VOID list.
- **Registry is not yet connected to any V5 backtest selection, reporting, economics or Production.** No existing model/DB/selector/LINE/BUY/stake changed. A repo test workflow has not been launched; tests ran locally only.

## V5 research-only VOID guard: VERIFIED
- `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` now excludes exact 71 official-K-confirmed VOID race IDs from scoring outcome rows AND racer-course history before computing priors; commit `164fec75d2aea09e567990db7622f698e255d017`.
- Counts and evidence provenance are included in the research coverage output; non-VOID status never means automatically eligible.
- `tests/test_v5_historical_void_integration.py` commit `71edbd1131529def2cdfc77986ea5b7904b5e6a1`. GitHub-only workflow `research-v5-historical-void-offline-tests.yml` command comment `6078120588`, bot `6078124223`: PASS 9/9 offline tests (6 registry + 3 integration).
- Tests verify 71 ID manifest, protect completed Sep21 津4R and 三国9R, remove legacy mislabeled cancelled result from scoring and history, and fail on missing race IDs. No DB/Railway access in tests.
- Only ONE V5 research script is guarded. No Production V4 / LINE / BUY / stake / Railway / DB changes, no real historical backtest rerun yet.

## V5 weight tuning VOID guard — COMPLETE / PASS
- `research/v5_strong_core_weight_tuning_pg.py` commit `be9471290d3e40ac1ab7f9deb8728d8be98229fd`: V5 research-only `b.exclude_verified_void_rows` guards selected race outcomes and result-entry racer-course history before fitting; adds explicit counts & provenance to coverage.
- Regression test `tests/test_v5_weight_tuning_void_guard.py`, commit `fdc77efa1db73752e350b1019067d6ee2527ab62`.
- GitHub Issue #581 command `6078177001`, bot result **`6078180261`**: `V5_WEIGHT_TUNING_VOID_TEST_PASS`, 1 test run, 0 failed, process exit code 0. This mocked test covers confirmed VOID injection into fake `official` rows, prior-history removal, five normal races including 9/21 津4R/三国9R, and train/Apr/May/late spans. **No live DB rerun yet.**
- Previous base opponent research guard 9/9 offline tests PASS (`6078124223`); do not confuse targeted unit PASS with an actual full-sample V5 backtest.
- No DB, Railway or Production V4/LINE/BUY/stake change. V5 research-only, keep raw data and 2025-07-01..2026-10-05 frozen research window.

## V5 calibration VOID guard — COMPLETE / PASS
- Official K `中止` exactly 71 historical race IDs established at Issue #581 bot `6077502477`. Research-only `research/historical_void_registry.py`; never fabricate result or delete raw.
- Representative V5 core `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` guard PASS 9/9 offline tests at `6078124223`. Weight optimization `research/v5_strong_core_weight_tuning_pg.py` PASS 1/1 offline test at `6078180261`.
- **This turn:** `research/v5_strong_core_calibration_pg.py` commit `0eb35163b600e990c0b25b9d71a5f0dbcc6be8bc`: calls shared `b.exclude_verified_void_rows()` on selected outcomes and historical result-entry rows *before* fit/scoring. Research JSON outputs excluded candidate/history counts and `b.EVIDENCE_REF`. Existing train/Apr/May/late split and frozen temperature selection preserved.
- Added `tests/test_v5_calibration_void_guard.py` commit `b994324723812f77859beeaf265949e400127a0a`, uses fake DB with deliberately mislabeled cancelled 9/21 津5R and completed 津4R / 三国9R; validates VOID excluded from score+history and model splits.
- GitHub-only offline test workflow `.github/workflows/research-v5-calibration-void-offline-tests.yml` commit `da4a08784c834024621bac67235682508a616a5f`.
- Issue #581 command comment `6078219291` run **ONCE**, bot result comment **`6078221781`**: `V5_CALIBRATION_VOID_TEST_PASS`, 1 test OK, process exit code 0. No pending action to rerun.
- These are offline mock tests. **No live historical 2025-07-01..2026-10-05 backtest executed yet; NOT all V5 scripts covered**. No Production V4/LINE/BUY/stake, DB, Railway, plan, volume or raw data changes.

## V5 research venue-lane VOID guard — COMPLETE / PASS
- Official-K-confirmed 71 cancellations from Issue #581 result `6077502477`. 2026-09-21 津4R and 三国9R were completed and are NOT VOID.
- Research-only `research/v5_current_core_plus_venue_lane_pg.py` commit `418e5bda6820f91696d2a6341ac775b79ed7c5d9` now excludes verified VOID from both selected outcomes and historical result-entry ability priors, using shared `b.exclude_verified_void_rows()`; reports excluded row counts and evidence provenance.
- Fake-DB test `tests/test_v5_venue_lane_void_guard.py`, commit `e3d8d64a90089b94575865503bcaf0c902e71328`, checks exclusion + normal venue races retained. Issue #581 command `6078275111`, bot `6078278314`: `V5_VENUE_LANE_VOID_TEST_PASS`, 1/1 test, exit 0. NO rerun pending.
- Prior V5 guarded paths also offline PASS: opponent main `6078124223` (9 tests); weight tuning `6078180261` (1); temperature calibration `6078221781` (1). **Four research scripts guarded**; not a claim that all V5 scripts have been audited, nor that real full-period V5 backtest has run.
- No DB, Railway, Production V4, LINE, purchase, stakes or raw-data change. Never fabricate results; research only.

## Historical V5 incident inventory — PENDING single existing workflow
- Prior research-only guard tests all PASS: core opponent `6078124223`, weight tuning `6078180261`, calibration `6078221781`, venue-lane `6078278314`. Exactly 71 official K `中止` races, result `6077502477`, must remain VOID with raw retained. Non-VOID completed races Sep21 津1–4R and 三国1–9R preserved.
- Inspected existing `research/race_incident_inventory_pg.py` (BEGIN READ ONLY, dates `2025-07-01..2026-10-05`, counts result-entry completeness, withdrawal/flying/late/incident/unknown statuses, and DB-marked dual cancelled states). It does **NOT** incorporate official K 71 VOID manifest itself; DB `WHOLE_RACE_VOID` may be smaller than verified official cancellations, DO NOT interpret as contradicting official evidence. It may also count `other_nonstandard_status` overlapping incident labels; categories can overlap.
- Existing `.github/workflows/railway-candidate-v4-incident-inventory-readonly.yml` command `/railway incident-inventory-readonly`, DB candidate-v4 via Railway CLI (remote DB connection only), 10 minute job limit. Read-only SELECT via transaction, NO DB modifications. Railway Agent/AI prohibited.
- 2026-10-09 Issue #581 command scan had NO existing matching command; posted ONCE: **`6078322463`**. Runtime estimate provided: **2–5 min**, max 10 min. **DO NOT POST AGAIN WHILE PENDING.**
- Risk notes: status/result flags alone cannot establish timing relative to prediction cutoff; postrace-only incidents must not leak into historical predeadline prediction.
- No Production V4/LINE/BUY/stake/volume/plan change.

## Full V5 frozen-range incident inventory — COMPLETE / PASS (read-only)
- Existing `research/race_incident_inventory_pg.py` run ONCE using `.github/workflows/railway-candidate-v4-incident-inventory-readonly.yml`, Issue #581 command `6078322463`, bot report **`6078332204`**. Output `INCIDENT_INVENTORY_READ_ONLY=PASS`; 2025-07-01..2026-10-05, BEGIN READ ONLY, no DB write or model/Production/LINE/BUY/stake/plan/volume modification.
- Full period: `TOTAL_RACES=70968`, `RESULT_ENTRY_RACES=70268`, `RESULT_ENTRY_ROWS=421608`, `RESULT_ENTRY_COVERAGE_PCT=99.014`, `INCOMPLETE_RESULT_ENTRY_RACES=700`. All 700 incomplete have **zero** result-entry rows; 0 with 1–5 rows.
- `WHOLE_RACE_VOID=700` **according to existing DB dual cancelled/canceled result_status AND race_status**. Do not equate to 700 independently official-K-verified cancellations; EXACT 71 (Aug11/Sep09/Sep21/Sep22) were individually confirmed via official K at `6077502477`. No simple 71-vs-700 discrepancy because 71 is only residual subset of full 2025/26 range.
- Abnormal **distinct** races from result participant statuses: **4655**, categories may **overlap**: withdrawal=715, flying=1146, late=36, incident_or_disqualification=2820, other_nonstandard_status=0. Incident timing relative to prediction deadline NOT established; this is result-side retrospective evidence only.
- Month with most zero-entry races: 2026-01 n0=174; 2026-05 n0=86; 2026-06 n0=71; 2026-09 n0=59; Oct01..05 n0=0 (792/792 complete). Prior 8/01..10/05 audit had 71 explicit cancellations, no missing data beyond cancelled race set.
- Four key V5 research scripts with 71 VOID guard pass mocked offline tests: opponent core `6078124223`, weight tuning `6078180261`, calibration `6078221781`, venue-lane `6078278314`. NO full-window live V5 backtest has been run yet; not all V5 scripts were audited. Raw preserved, Production V4 unchanged.

## Next ONE task
Design + implement **non-destructive, research-only primary training eligibility guard for the 4655 incident-marked races**, starting with a pure standalone classifier and offline tests for `K0/K1/L0/L1/F/S0/S1/S2` and textual abnormal statuses, and unknown timing => fail-closed. Do not confuse postrace result codes with pre-deadline knowledge or with real official payout economics. Do not automatically deem every other race eligible; independent six-boat/timing/snapshot quality conditions still required. Keep separate official-K 71 VOID manifest. Then integrate one V5 script at a time and run a read-only frozen full-window backtest/freeze review. One task per turn. Auto-purchase LAST, Railway Agent/AI prohibited; spend <=USD20/mo, ideally <=USD15.
`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
