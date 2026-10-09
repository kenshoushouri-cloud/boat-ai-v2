# Current Compact Handoff — 2026-10-09 JST

## Operating contract / priorities
- Repository: `kenshoushouri-cloud/boat-ai-v2`. Read only `docs/HANDOFF_LATEST.md`, this compact handoff, `docs/NEXT_CHAT_START_HERE.md` on new chats; old handoff/PROJECT_HISTORY and lengthy workflow logs only if essential. This handoff was condensed from the prior verbose version; details remain in Git history.
- **Production V4 stays protected; V5/V5.1 research-only.** Build the system body first; automatic betting/purchase is the **very last** development phase. No Production selector, stake, LINE, BUY, Railway plan/volume changes without specific approval.
- **Railway Agent/AI prohibited.** Minimize CPU/RAM/network; aim <=USD15/month, cap <=USD20. One scoped task at a time; minimum tool calls; no blind retries or duplicate pending Issue commands; verify exact live SHA/run when needed. Present expected execution time before runs.
- Frozen research/backtest range: **2025-07-01..2026-10-05**; do not mix Oct06+ later operational evidence into frozen fitting. Preserve official raw data; exclusion never deletes. Model features selected strictly on data available before prediction cutoff.
- morning/day/night jobs and PRE computations remain active; PRE candidate LINE alerts are **disabled**, FINAL BUY LINE notification remains. Do NOT accidentally disable daypart jobs.

## System/data verified through 2026-10-09
- Oct01..05 `v2_results`: **792/792** fully restored; Oct05 144-results missing-only repair PASS, Issue #581 bot `6075638332`. Never rerun prior expensive 5-day repair.
- Oct01..05 official K `v2_result_entries`: **792 races / 4752 rows** PASS, bot `6075705473`.
- Aug01..Oct05 result-entry coverage: 10,380 base / 10,309 with complete6 / **71 no-entry races**, 0 partial, bot `6075857637`.
- All those **71 IDs explicitly say `中　止` in race-specific official K headers**, bot `6077502477`. Aug11 江戸川 12, Sep09 江戸川 12, Sep21 戸田 12 / 江戸川 12 / 津5–12 8 / 三国10–12 3, Sep22 津12. Sep21 津1–4 and 三国1–9 were not cancelled; preserve completed races. No synthetic result rows; research VOID/zero *hypothetical* stake, but real historical settled investments always retained.
- Read-only full frozen-range participant-incident inventory PASS, bot **`6078332204`**: 70,968 races, 70,268 with six result entry rows, 700 with zero, 99.014% detail coverage; DB dual-cancelled status calls 700 whole-race VOID (NOT all independently K-confirmed). Abnormal participant-status **4,655 distinct** races; categories overlap: withdrawals 715, F 1,146, L 36, incidents/disqualifications 2,820. Result-side incident record NEVER proves predeadline awareness.
- Incident policy `docs/RACE_INCIDENT_HANDLING_CONTRACT_20261009.md`: race canceled=>VOID/no training; F/L/accident/withdrawal=>initially exclude from main six-lane fitting, keep time-clean original prediction evidence and actual recorded betting outcomes; unknown evidence=>fail closed for primary fitting. Reduced 5/4 active-lane cases require separate verified research.

## V5 research and safety status
- Strong-core research weight candidate: lane + class + recent form 0.50 + exhibition time rank 1.00 + racer-course 0.75 + opponent 1.25 + venue-lane 0.75. Calibration T=1.00 in prior research. Research freeze/adoption still gated by V4 formal evidence, S03_M2 forward and safety/cleanliness; never automatically promote V5.
- Pure `research/historical_void_registry.py` verifies 71 K-confirmed cancellation race IDs. `research/historical_incident_eligibility.py` returns retrospective states for K VOID, DB-indicated cancellation, K0/K1/L0/L1/F/S0/S1/S2, textual accidents, boolean flags, missing/unknown data. `NO_INCIDENT_EVIDENCE` is NOT automatic fitness for prediction. Independent timestamp, six-boat feature/snapshot, training gates needed.
- Existing four core V5 research scripts protected against **71 VOID** and offline PASS:
  `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` (bot `6078124223`);
  `research/v5_strong_core_weight_tuning_pg.py` (`6078180261`);
  `research/v5_strong_core_calibration_pg.py` (`6078221781`);
  `research/v5_current_core_plus_venue_lane_pg.py` (`6078278314`).
- Pure historical incident classifier offline contract **19/19 PASS** (13 incident + 6 VOID) bot `6078409682`.
- **LATEST ONE TASK COMPLETE:** connected `research/historical_incident_eligibility.py` to representative `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` **for both scoring outcomes and racer-course historic training**. Uses every result entry's lane, finish_status, is_flying/is_late and optional retrospective result statuses; requires six normal participant records; unknown/incomplete=>excluded. Keeps first-stage official VOID guard and reports exclusion reason counts, no post-result evidence pretended as predeadline. Commit `d7f0c3df59c8f094f22dcec638136080f945f164`. Updated fake-DB integration regression `tests/test_v5_historical_void_integration.py` with synthetic F case; CI bot `6078485258`: **16/16 PASS** (13 classifier tests + 3 V5 integration tests), no DB/Railway access. Command comment `6078482608` completed; **NOT pending**.
- Only this **one** V5 representative script has the new wider participant-incident guard. Other 3 V5 scripts have the 71 VOID guard ONLY. No real frozen-range V5 backtest after these changes yet, and no Production changes.

## Next ONE task
Integrate the same **participant-level historical incident eligibility** into ONE adjacent V5 research script (prefer `research/v5_strong_core_weight_tuning_pg.py`) using the established `b.filter_postrace_primary_training()` shared function on both outcomes and historical ability rows, with small offline fake-DB regression covering F/K0/S1 and preserving completed Sep21 races. Do not modify many scripts at once. After proven, repeat for calibration/venue-lane; then run controlled read-only full-range V5 research validation and freeze review. Do not alter actual payout economics / live BUY.
`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
