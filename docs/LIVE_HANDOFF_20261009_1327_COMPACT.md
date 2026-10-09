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

### ACTIVE PENDING READ-ONLY AUDIT — DO NOT DUPLICATE
- New GitHub workflow: `.github/workflows/railway-candidate-v4-results-coverage-audit-20261001-05.yml`
- Commit: `2797a54907c4d5645d05359d2c642a15a44af4c0`.
- Issue #581 command comment id: **6075339999**
- Command: `/railway candidate-v4-results-coverage-audit-20261001-05`
- Performs PostgreSQL `BEGIN READ ONLY` and SELECT-only comparisons between `v2_races` and `v2_results` for each day 2026-10-01..05.
- Expected execution time announced: about **2–5 min**, GitHub job timeout 10 min.
- **Do not issue a duplicate command or restart while pending.** This does NOT perform result repair or write DB data.

## Next ONE task
**Only check the result of Issue #581 command comment `6075339999` (and matching bot reply/run if needed).**
- If PASS: record exact per-day BASE_RACES / RESULTS / MISSING / EXTRA, then use next turn to plan one date-scoped RESULTS-only repair; do not launch a repair now.
- If FAILED: inspect only the specific audit job/error and fix one issue at a time.
- After result coverage complete: run existing `v2_result_entries` backfill 10/1..10/5, read-only result-entry preflight, classify 8/11 and September residuals, incident inventory, then V5 backtest/freeze.
- Production=V4, V5 research-only; automatic purchase last. No Railway Agent/AI or unnecessary Railway cost.

`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
