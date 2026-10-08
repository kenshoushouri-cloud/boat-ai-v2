# LIVE HANDOFF — 2026-10-08 11:55 JST — COMPACT

## Purpose
V5 zero-base research for boat-race probability prediction. Formal evaluation period is **2025-07-01..2026-10-05**. Production remains **V4 only** until separate approval.

## Chat / tool discipline
- Read only: HANDOFF_LATEST → this file → NEXT_CHAT_START_HERE.
- Do NOT bulk-read old handoffs, PROJECT_HISTORY, long workflows, old chats, all Actions, or all Issue comments.
- One task at a time; normally 1–3 tool calls. Code + runner + one launch may be bundled.
- Never duplicate a pending command. Long run: launch in one turn, result check in next.
- SHA/run/count/capacity are not fixed facts; fetch only when needed.
- User prefers concise Japanese and minimal intermediate logs.

## Hard protections
- Production prediction/model = V4 only. V5/V5.1 = research-only.
- Railway Agent/AI prohibited.
- Railway cost target <= USD20/month, preferably <= USD15; minimize CPU/RAM/Network.
- No purchase / LINE / stake / Production model / plan / volume resize-delete without explicit approval.
- DB research runs must be read-only.
- No target-race outcome leakage; same fixed walk-forward / previous-day contract across comparisons.
- REJECT_INPUT != delete. Not-yet-adopted != rejected. Keep collected raw data.

## V5 method
B0 true no-info → test one family standalone + incremental → KEEP/HOLD/REJECT_INPUT.
Primary: LogLoss, Brier. Venue stability + Top1 secondary.
After screening: provenance/leakage audit → redundancy/core incrementals → limited interactions → weight tuning on earlier train only → calibration → selector/ROI.
Do not jump to ROI before core freeze.

## Frozen baseline
B0: LL 1.7917594692, Brier 0.8333333333.
Lane B1: LL 1.3697721368, Brier 0.6525407038.
Lane + class baseline: LL 1.2906504677, Brier 0.6249721328. This is the current core seed.

## Strong current core candidates
All below are incremental over lane+class unless noted.
- racer-course residual: **KEEP strong**, dLL -0.01272816, dBrier -0.00452285, 24/24 venues better both.
- recent form last5 top3: **KEEP strong**, dLL -0.01943635, dBrier -0.00831740, 24/24 both.
- avg_st: **KEEP**, dLL -0.00396159, dBrier -0.00232749, LL 23/24, Brier 24/24.
- opponent composition: **KEEP**, dLL -0.0134803, dBrier -0.0068082, 24/24 both.
- F/L counts: **KEEP candidate**, dLL -0.00461447, dBrier -0.00325833, 24/24 both.
- venue-lane residual: **small KEEP candidate**, dLL -0.00387262, dBrier -0.00218264, 17/24 both.
- branch: weak KEEP candidate, dLL -0.00191661, dBrier -0.00150081.
National win/place2 after lane+class are mostly redundant/HOLD-ish.

## Exhibition data — IMPORTANT
Policy fixed in `docs/V5_EXHIBITION_DATA_POLICY_20261008.md`.
- Raw exact exhibition_time over lane+class: **HOLD**, essentially zero/slightly worse.
- exhibition_time_rank over lane+class: **strong KEEP candidate**:
  dLL -0.01472644, dBrier -0.00550834, LL 22/24, Brier 24/24, coverage 98.98%.
- Add exhibition rank on top of lane+class+recent_form:
  baseline LL 1.27008245 / Brier 0.61601659
  → LL **1.25880792**, Brier **0.61199701**
  dLL -0.01127454, dBrier -0.00401958, Top1 improved, LL 22/24, Brier 23/24.
  => exhibition_time_rank remains independently useful and is a formal core candidate.
- Frozen forward evidence: 278 safe observations, 2026-08-23..25, 16 venues, captured ~8.3–14.8 min before deadline, official beforeinfo, 6 lanes complete, zero timing/source/rank violations.
- Frozen forward rank test: dLL -0.01758904, dBrier -0.00606004.
- Historical provenance audit: 69,575 complete-rank races. 6,815 explicit archived-beforeinfo contract, 555 realtime-reuse, 62,205 legacy `official_beforeinfo_historical` rows without modern contract tags. Legacy generation path was verified to fetch BOAT RACE official target-race `beforeinfo` page only.
- Historical rows are retrospective pre-race truth for backtest; synthetic historical timestamps are NEVER prospective timing proof. Deployment must use genuine pre-deadline capture.

## National place3 latest redundancy result
Standalone and lane+class increment were strong, BUT when added to current stronger baseline
**lane + class + recent_form + exhibition_time_rank**:
- baseline LL 1.25873744 → candidate 1.26867421 = **dLL +0.00993677 (worse)**
- Brier 0.61194640 → 0.60934024 = dBrier -0.00260616
- LL better only 7/24 venues; Brier 21/24.
Decision: **HOLD / do not add to current core now**. Do not reject/delete the information; revisit only during calibrated weight/redundancy phase.

## Other important screening
- motor/boat raw race-card rates often harmful; motor family remains HOLD because exchange-generation handling is required.
- official-generation prior-top3 motor subset: HOLD寄りKEEP候補, limited 5 venues.
- local raw place2/place3 and raw boat place2/place3 direct formulations REJECT; underlying data retained.
- exhibition ST rank direct formulation REJECT; raw exact start_timing over lane+class was zero incremental → HOLD.
- weather exact formulations mostly HOLD / weak; keep data.

## Current active command — DO NOT DUPLICATE
Issue #581 command id **6051221908**:
`/railway v5-lc-rf-exrank-racer-course-run`

It is intended to test racer-course residual on top of the current strong baseline:
**lane + class + recent_form + exhibition_time_rank**.

At handoff creation time, no bot result was present yet.

## Next ONE task
1. Fetch only Issue #581 comments at/after id **6051221908**.
2. If result exists, parse dLogLoss/dBrier, venue sign counts, coverage and decide KEEP/HOLD for racer-course on the current strong core.
3. **Do not rerun** if a result exists.
4. If no result, check unfiltered Actions once for the matching workflow/run; only reissue after proving no run exists.
5. Do not start another DB-heavy test in the same turn if this one is still running.

After that, continue redundancy/core incrementals for remaining strong candidates (avg_st, opponent composition, F/L, small venue residual) against the evolving strong core, then limited interaction/weight tuning. Keep exhibition_time_rank in the core candidate set.

## Infrastructure
Repo: `kenshoushouri-cloud/boat-ai-v2`
Bridge Issue: **#581**
Research DB service: `postgres-hobby-fullhistory-candidate-v4`
Production DB/service must not be restarted/changed without separate approval.
Research DBs have serverless sleep enabled when unused.

COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN
