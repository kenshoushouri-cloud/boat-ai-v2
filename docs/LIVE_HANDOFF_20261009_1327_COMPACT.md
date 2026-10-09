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
- Participant-incident eligibility now also guards **V5 weight tuning**; only calibration and venue-lane among these 4 still have 71-VOID-only guards. No real frozen-range V5 backtest after these changes, no Production changes.

## V5 weight tuning participant incidents — COMPLETE / PASS
- Updated `research/v5_strong_core_weight_tuning_pg.py` commit `12a1c035965a881761ef43e6b56c45835305942a`: shared `b.filter_postrace_primary_training` with result-entry lane/finish_status/F/L flags and optional result_status/race_status; exclude incident/unknown evidence from **both** scored races and racer-course history, after K-verified 71 VOID filter. Report reason counts and indicate result-side ≠ predeadline evidence.
- Extended `tests/test_v5_weight_tuning_void_guard.py` commit `aedfc1f27bee02d6eab78d84c8b2b4be275bccc3`: synthetic K0 train, S1 May, F Sep21 excluded, preserve 5 healthy races including Sep21 津4R / 三国9R, retain train-Apr-May-late boundaries. No DB connection.
- GitHub-only workflow `.github/workflows/research-v5-weight-tuning-incident-offline-tests.yml`, commit `7a44e8e1c086be5c06738f751d709c9ac2064cd8`; Issue #581 command `6078557157` bot response **`6078559956`**: `V5_WEIGHT_TUNING_INCIDENT_PASS`, 14/14 (13 classifier + 1 V5 integration), no Railway, DB, Production, stake or BUY changes, **no command pending**.

## Next ONE task
Integrate participant-level historical incident eligibility into **only** `research/v5_strong_core_calibration_pg.py`, using shared `b.filter_postrace_primary_training()` after K-71 VOID filter on scoring outcomes and all historical result-entry rows; leave temperature/OOS split unchanged. Adapt and run bounded offline fake-DB tests covering K0/F/S1, proper races retained and no predeadline leakage. Then venue-lane; after both pass, design a low-cost read-only full-range V5 research backtest. Never alter real betting economics, Production V4, Railway plans/volumes/AI, or RAW data. Show runtime estimates, no duplicate commands.
`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN / SHOW_ESTIMATED_RUNTIME`
