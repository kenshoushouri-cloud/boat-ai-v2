# boat-ai-v2 Current State

## LATEST OVERRIDE — 2026-09-30 14:21 JST

**Read the comprehensive handoff first:**
- `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

Current operational source of truth at this checkpoint:
- GitHub main before this docs update: `647a43e60d627938e55de4239af15265819659bd`
- latest main: #496 long-range historical beforeinfo campaign
- Railway fallback: **08:20 JST / `20 23 * * *`**
- fallback latest deploy: `839be48f-af8f-4a53-8ba4-5b8abdc13f8a` — **SUCCESS**
- staged Railway config: none
- Production V4 model/selector/threshold/stake unchanged
- `purchase_action=false`

Settled evidence currently recorded through 2026-09-28:
- V4 formal TOP2: **8/20**, ROI **147.7273%**, profit **+4,200 JPY**
- S03_M2: **63/100**, ROI **160.6349%**, profit **+3,820 JPY**
- S03 second-half ROI: **56.5625%**
- 2026-09-29 formal V4: **UNAVAILABLE**, never reconstruct/backfill/count
- V5 core review target: **2026-10-15**

Operational objectives:
- roughly **1–3 quality notification races/day** when naturally available;
- monthly planning target **+50,000 JPY net profit**;
- prove edge first, then volume/risk, then stake scaling separately;
- never loosen thresholds merely to create volume/profit.

Data policy:
- prospective F-count companion capture is active;
- historical missing-data acquisition is active;
- official target-day pre-race F-count is allowed as historical predeadline input;
- historical target features must use only information available before target deadline;
- historical reconstructed evidence remains separate from prospective gate counts;
- current acquisition includes official racelist/B/beforeinfo/racer-term/prior-only Opponent and recent_form work;
- external pre-race archives and 艇国 may supplement under the documented provenance/access rules.

Important active/open work:
- #500 July 2025 historical pre-race raw acquisition — 31/31 Race Cards/Recent Local, 31/31 Recent National days with 59-row shortfall; no DB import yet;
- #498 prior-day official-K recent_form reconstruction;
- #497 isolate historical beforeinfo write lane;
- #459 LINE/candidate-volume near-miss diagnostic;
- #458 unavailable-day V4-count regression;
- older #405/#409/#412/#413 remain evidence/provenance research records.

Before doing new work:
1. read `PROJECT_HANDOFF.md`, this file, and `SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`;
2. re-fetch main/open PRs/CI/Railway Production/current evidence;
3. inspect issue #42 before starting duplicate historical campaigns.

`READ_20260930_COMPREHENSIVE_HANDOFF / MAIN_647A43E / FALLBACK_0820_SUCCESS / V5_8_OF_20_63_OF_100_SETTLED_0928 / HISTORICAL_ACQUISITION_ACTIVE / MONTHLY_PLUS_50000 / PROD_UNCHANGED / PURCHASE_FALSE`


## LATEST OVERRIDE — 2026-09-30 09:50 JST

Historical acquisition is now an active priority.

Approved interpretation:
- for historical backtests, the correct feature value is the value that would have been available before the target race deadline;
- BOAT RACE official target-day pre-race program/racelist data are accepted as historical predeadline-by-nature inputs;
- deterministic reconstruction is accepted only from events strictly before the target deadline;
- target-race outcomes must never enter feature construction;
- historical replay remains separate from prospective V4/S03 gate counts.

Source order:
1. BOAT RACE official program/racelist/B files;
2. BOAT RACE official prior-only reconstruction;
3. 艇国データバンク as a supplemental source under its published access rules.

艇国 usage:
- >=3 seconds between automated accesses;
- known existing URLs only;
- one IP;
- no repeated static asset retrieval;
- official BOAT RACE download remains preferred for program/result/racer-term categories;
- present-day aggregate values are cross-check only unless a historical as-of cutoff can be proven;
- dated motor histories may be used for prior-only reconstruction/cross-check.

Historical F-count policy changed by explicit user direction:
- target-day official racelist/B-file F-count may be acquired and used as historical predeadline input;
- this does NOT authorize outcome-guided F-count coefficient search or Production model changes;
- future prospective F-count companion capture remains active and separately labeled.

Completed/active acquisition:
- official entry/racelist numeric backfill confirmed through 2025-08-11;
- additional 2025-08-12 onward entry batches are running;
- racer_name / branch / origin were added to fill-missing-only official racelist backfill by merged PR #474;
- 2025-07-01..07-07 metadata-aware pilot is running;
- Course applied-term proxy 2025H2 completed;
- Course 2026H1 acquisition is running;
- Opponent prior-only replay completed for 2025-07 and 2025-08;
- 2025-09 Opponent replay hit a statement timeout while concurrent entry writes were active; retry after entry I/O settles, without changing scoring logic;
- PR #475 is testing one-day official daily B-file parity to reduce future HTTP load.

Production V4 model/selector/threshold/LINE/stake remain unchanged.
`purchase_action=false`.

`HISTORICAL_BACKFILL_ACTIVE / PREDEADLINE_BY_NATURE_ACCEPTED / FCOUNT_HIST_INPUT_ALLOWED_NO_COEF_SEARCH / TEIKOKU_SUPPLEMENTAL / PROSPECTIVE_GATES_SEPARATE / PROD_UNCHANGED`


## LATEST OVERRIDE — 2026-09-30 00:55 JST

Current source of truth:
- main before this override: `33333a6952043071297a34a617da17075be07146`
- PR #452 fallback internal 08:20 fix: **merged**
- PR #460 future-only F-count companion capture: **merged / active for future successful formal freezes**
- Railway fallback Cron: **08:20 JST / `20 23 * * *`**
- latest successful fallback dispatcher deployment on current main: `f7dd7219-5ecf-4976-ba40-85d51957bfea` — **SUCCESS**
- latest same-main Railway redeploy `8c14f309-99f3-4332-a487-511225f03104`: **SUCCESS**; staged config: none
- 2026-09-29 formal V4 remains **UNAVAILABLE**; no reconstruction/backfill
- settled V4 through 2026-09-28: **8/20**, ROI **147.7273%**, profit **+4,200 JPY**
- settled S03_M2 through 2026-09-28: **63/100**, ROI **160.6349%**, profit **+3,820 JPY**
- S03_M2 second-half ROI: **56.5625%**
- V5 core target: **2026-10-15**
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- automatic purchase disabled / `purchase_action=false`

### Monthly profit target is now explicit

Operational planning target:
- **monthly net profit +50,000 JPY**

The target is a scaling objective, not a selector-retuning objective.

At 100 JPY/ticket, 30 days/month, TOP2:
- 1 notified race/day -> monthly investment 6,000 JPY -> required ROI **933.33%**
- 2/day -> 12,000 JPY -> required ROI **516.67%**
- 3/day -> 18,000 JPY -> required ROI **377.78%**

Current V4 formal 6R/day x TOP2, if the present overall ROI 147.7273% persisted for 30 days at 100 JPY/ticket:
- monthly investment: 36,000 JPY
- descriptive projected profit: about **+17,182 JPY**
- still below the +50,000 JPY target

Therefore:
1. prove prospective edge first;
2. measure natural high-quality notification volume;
3. review conservative ROI / drawdown / losing streak;
4. only then consider a separately approved stake scale.

PR #461 adds this feasibility gate to the routine combined V5 checkpoint.
It explicitly keeps:
- threshold relaxation for profit/volume: forbidden;
- stake change authorization: false;
- Production change: false;
- `purchase_action=false`.

### F-count activation

F-count collection is future-only and separate from the formal V4 artifact:
- only after a valid formal V4 freeze;
- exact formal six races x lanes 1..6 = 36 rows;
- PostgreSQL READ ONLY;
- only `race_id,lane,f_count`;
- no result/payout/odds read;
- companion failure cannot invalidate the formal V4 day;
- no historical F-count backfill or coefficient search;
- no model/LINE/stake/purchase change.

`FALLBACK_0820_CODE_AND_CRON_ALIGNED / FCOUNT_FUTURE_CAPTURE_ACTIVE / MONTHLY_PLUS_50000_GATE_ADDED / V4_8_OF_20 / S03_63_OF_100 / NO_RETUNE / NO_STAKE_CHANGE / PURCHASE_FALSE`


## LATEST OVERRIDE — 2026-09-29 17:10 JST

High-level handoff guide added:
- `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260929.md`

Current:
- Production fallback: **08:25 JST**
- latest dispatcher deployment: SUCCESS
- Draft #452: green / not merged
- 9/29 formal prospective evidence: unavailable / no reconstruction
- settled V4: **8/20**, ROI 147.7273%, +4,200 JPY
- settled S03_M2: **63/100**, ROI 160.6349%, +3,820 JPY
- V5 target: **2026-10-15**
- Production V4 model/selector/stake unchanged
- `purchase_action=false`

The handoff guide now contains:
- system purpose;
- daily timing;
- V5 milestone;
- current work priorities;
- approval boundaries;
- next-chat checklist.

`READ_SYSTEM_PURPOSE_TIMELINE_HANDOFF / PROD_0825_SAFE / V5_8_OF_20_63_OF_100`

## LATEST OVERRIDE — 2026-09-29 16:59 JST

Current source of truth:
- main: `aa9e9d3a1ad18d174be9b16a871eba5037990fe7`
- Production fallback Cron: **08:25 JST** / `25 23 * * *`
- latest dispatcher deployment `5b967767-0300-4795-a81b-213410610d90`: SUCCESS
- pending/staged: none
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

9/29 incident:
- 08:20 Cron activation hit old internal 08:25 checkpoint
- log at 08:23:33 JST: `NOT_DUE / before_0825_checkpoint`
- fallback did not dispatch
- natural GitHub schedule started ~11:33 JST and failed closed
- **9/29 formal prospective artifact unavailable**
- no reconstruction/backfill
- no day-strength label for 9/29

Rollback:
- Production restored to **08:25 JST**
- rollback deployment SUCCESS
- current read-back confirms 08:25

#452:
- Draft open
- head `73dd7f593be1199edf32bb0710458548a6d2d32d`
- all CI SUCCESS
- aligns internal checkpoint to 08:20
- **not merged**
- explicit approval required before Production reactivation

Settled through 9/28:
- V4: **8 resolved days**, ROI **147.7273%**, profit **+4,200 JPY**
- V4 9/28 single day: ROI 55.0%, -540 JPY
- 9/28 preregistered SKIP_SHADOW would have avoided that loss; one-day descriptive only
- S03_M2: **63 evaluated**, ROI **160.6349%**, profit **+3,820 JPY**
- S03 second half ROI **56.5625%**
- V5 core: V4 **8/20**, S03 **63/100**
- 9/29 does not count

`PROD_0825_SAFE / PR452_GREEN_NOT_MERGED / 929_UNAVAILABLE / V5_8_OF_20_63_OF_100 / PROD_MODEL_UNCHANGED`

## LATEST OVERRIDE — 2026-09-29 16:45 JST

- Production fallback Cron is **08:25 JST** after safe rollback.
- rollback deployment `26973382-903c-4d50-9a78-9c079d8c5577`: SUCCESS
- reason: 08:20 Cron hit old internal `before_0825_checkpoint` guard
- #452 fixes internal checkpoint to 08:20 and is all-green Draft, **not merged**
- 2026-09-29 formal prospective artifact: **UNAVAILABLE**
- no reconstruction/backfill
- natural GitHub schedule started ~11:33 JST and failed closed

2026-09-28 settled evidence:
- V4: **8 resolved days**, ROI **147.7273%**, profit **+4,200 JPY**
- 9/28 single day: ROI **55.0%**, profit **-540 JPY**
- preregistered 9/28 `SKIP_SHADOW` would have avoided that one-day loss
- S03_M2: **63 evaluated**, ROI **160.6349%**, profit **+3,820 JPY**
- S03 second half ROI **56.5625%**
- V5 core: V4 **8/20**, S03 **63/100**

Production V4 model/selector/stake unchanged.
`purchase_action=false`.

## LATEST OVERRIDE — 2026-09-28 21:43 JST

- main before docs update: `f7115240122da782375affe6dcb3be1798081812`
- explicit approval received for fallback Cron change
- Production fallback Cron changed:
  - before 08:25 JST / `25 23 * * *`
  - now **08:20 JST / `20 23 * * *`**
- only `cronSchedule` changed
- activation deployment `2141e0fa-0897-4b2d-b5c7-94f2b03e571d`: **SUCCESS**
- source/build/startCommand/runtime/region/replica unchanged
- staged/unmerged config: none
- rollback = restore `25 23 * * *`
- first live 08:20 cycle: target 2026-09-29

Reason:
- GitHub natural schedule delivery remains severely late;
- 9/28 natural run started ~10:37 JST;
- old 08:25 fallback still succeeded but formal freeze reached 08:31:28;
- #412 projected 08:20 worst feed headroom ~6m21s.

Evidence counts unchanged before 9/28 settlement:
- V4 7/20
- S03 61/100
- day-strength 1 day / KEEP 0 / SKIP 1

Production V4 model/selector/TOP6/TOP2/stake unchanged.
`purchase_action=false`.

## LATEST OVERRIDE — 2026-09-28 15:12 JST

- main before docs update: `29571653276b6c31fc8321c81cfaf52c135cd090`
- 9/28 valid formal source: fallback run `36358843505`
- fallback completed 08:31:28 JST before earliest 10:02 deadline
- natural schedule run at ~10:37 JST failed closed as too late
- first future-only day-strength evidence: PASS_RESULT_BLIND
- target strength **0.93618881**
- reference **0.93817204**
- classification **SKIP_SHADOW**
- formal action unchanged
- day-strength progress: 1 future day / KEEP 0 / SKIP 1

V5 core mandatory counts are not advanced before settlement:
- V4 7/20
- S03 61/100
- target 2026-10-15

Next: after 9/28 nightly settlement, run combined checkpoint with no retune.

`DAY_STRENGTH_FIRST_SKIP / FALLBACK_VALID / CORE_COUNTS_UNCHANGED / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-28 01:12 JST

- main before docs update: `6e82ee37961c3e83f867be0773b8f0ac94d6842b`
- 9/27 nightly result load: PASS
- readiness: 156/156 terminal
- #446 S03 live-checkpoint fix: merged
- #447 post-nightly combined refresh: PASS_READ_ONLY

V4 formal TOP2:
- 7 resolved days
- 38 settled races
- ROI **162.3684%**
- profit **+4,740 JPY**
- later block ROI **145.6250%**
- leave-one-day worst 123.1250%
- 3 days remaining to 10-day review

S03_M2:
- 61 evaluated / 1 invalid / 0 pending
- ROI **165.9016%**
- profit **+4,020 JPY**
- second half ROI **58.3871%**
- bootstrap P>100 **79.50%**
- 39 remaining to 100-review
- no retune

V5 core:
- V4 7/20
- S03 61/100
- target 2026-10-15
- status COLLECTING_CORE_EVIDENCE

Production model/selector/stake unchanged.
`purchase_action=false`.

## LATEST OVERRIDE — 2026-09-27 22:40 JST

- main: `41fbe4f4b3cf1da5d6a48df98d4c2714ab26ece4`
- #437 milestone: merged
- #438 combined V5 progress: merged
- #439 roadmap: merged
- #440 freeze-review packet: merged
- #441 scope lock: merged
- Production remains V4
- target V5 core freeze review: **2026-10-15**
- `purchase_action=false`

Mandatory core:
- V4 >=20 resolved days
- S03_M2 >=100 evaluated
- clean evidence

Current pre-nightly:
- V4 6/20
- S03 53/100

Schedule estimate if current evidence flow continues:
- V4 20 around 2026-10-10
- S03 100 around 2026-10-09..10

Scope through 10/15:
- no new V5-core feature
- no gate lowering
- no post-outcome retune
- day-strength optional at its unchanged gate
- F-count separately approval-gated
- recent_form/L/exhibition/weather/odds-EV/new features deferred to later research

V5 freeze packet is ready on main and remains review-only.

`V5_MID_OCT_FRAMEWORK_COMPLETE / EVIDENCE_COLLECTION_NEXT / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 22:33 JST

- main: `56a968c9fb7d0ba05a7e04a54f50fd4a25268b84`
- #437 V5 milestone: merged
- #438 V5 progress in combined checkpoint: merged
- Production remains V4
- V5 is research-candidate terminology only
- target V5 core freeze review: **2026-10-15**
- fallback Cron 08:25 JST unchanged
- `purchase_action=false`

Mandatory V5 core gates:
- formal V4: 20 resolved days
- S03_M2: 100 evaluated observations
- evidence contract clean

Current pre-nightly:
- V4 6/20
- S03 53/100

Count-based planning:
- if 9/27 settles and daily formal evidence continues, V4 20-day point ~2026-10-10
- recent S03 pace suggests 100 observations ~2026-10-09..10
- these are schedule estimates, not ROI forecasts

Optional/nonblocking:
- day-strength keeps its own 10-day + 3 KEEP + 3 SKIP gate
- F-count remains separately approval-gated
- do not lower optional gates to meet 10/15

Combined manual checkpoint now emits V5 core remaining counts/status.

`V5_CORE_TARGET_REALISTIC_NOT_GUARANTEED / PROD_V4_UNCHANGED / NO_AUTO_PROMOTION`

## LATEST OVERRIDE — 2026-09-27 21:55 JST

- main: `e14821db4c82bd7ed66cd8314a323095224366c8`
- #434 repaired combined manual checkpoint: merged
- YAML structural/order CI: green
- #435 E2E read-only audit on 2026-09-26: PASS, closed unmerged
- Railway dispatcher deployment: SUCCESS
- staged/pending: none
- fallback Cron 08:25 JST unchanged
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

E2E parity:
- readiness 156/156 terminal
- V4 TOP2: 6 days / ROI 171.4062% / +4,570 JPY / 4 days to review
- S03_M2: 53 evaluated / ROI 190.9434% / +4,820 JPY / 47 to review

Tonight:
- use repaired combined checkpoint after ~23:45 JST
- target-day terminal guard is authoritative
- no retune from one added day

2026-09-28:
- #432 day-strength manual remains ready
- frozen reference 0.93817204
- result-blind / shadow-only

`COMBINED_E2E_GREEN / WAIT_NATURAL_927_RESULTS / DAY_STRENGTH_READY / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 21:36 JST

- main: `c0e0c4336150a85f76d8abe00ac640247b5a2ba8`
- #429 combined manual Forward checkpoint: merged
- #431 terminal result-day readiness guard: merged
- #432 future-only day-strength tooling/manual workflow: merged
- #411 closed as superseded
- Railway dispatcher: SUCCESS
- staged/pending: none
- fallback Cron 08:25 JST unchanged
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Tonight:
- combined checkpoint waits for target-day all-race terminal READY
- 9/27 pre-nightly baseline: V4 6 resolved / S03 53 evaluated
- run after ~23:45 JST; readiness guard remains authoritative

2026-09-28:
- manual day-strength workflow is on main
- result-blind / no DB
- frozen prior-7 reference = **0.93817204**
- KEEP_SHADOW iff target TOP6 mean race_score >= reference
- formal action never changes

`COMBINED_READY_GUARD / DAY_STRENGTH_READY / NO_AUTO_PROMOTION / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 21:25 JST

- main: `c9d9731cd0c96929aee671987eb5c97ea26e9d4e`
- #425/#426 individual manual checkpoints: merged
- #427 frozen review gates: merged
- #429 combined manual checkpoint: merged
- combined workflow: `.github/workflows/research-forward-combined-checkpoint-manual.yml`
- manual only / no schedule / read-only
- fallback Cron remains 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Current pre-nightly review progress:
- V4: 6 resolved formal days; 4 to 10-day review
- S03_M2: 53 evaluated; 47 to 100-review
- day-strength: starts 2026-09-28

Nightly:
- results Cron 23:30 JST
- recent completion ~23:38..23:42
- use combined checkpoint after 23:45 JST for 2026-09-27 refresh

`COMBINED_CHECKPOINT_READY / WAIT_NATURAL_RESULTS / NO_RETUNE / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 21:18 JST

- main: `d33460822cecf7bc6f92b68b8ba153343da57bad`
- #425 manual V4 provider-selected checkpoint: merged
- #426 manual S03_M2 checkpoint: merged
- #427 frozen review-gate helper: merged
- Railway dispatcher deployment: SUCCESS
- staged/pending: none
- fallback Cron: 08:25 JST unchanged
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Current review baseline:
- V4 formal: 6 resolved days -> 4 remaining to 10-day review
- S03_M2: 53 evaluated -> 47 remaining to 100-review
- day-strength future evidence: 0; starts 2026-09-28

Nightly results:
- Production Cron 23:30 JST
- recent observed starts 23:30:14..23:34:01
- recent completion roughly 23:38..23:42
- safe manual refresh target: after 23:45 JST
- no automation/schedule added

Next:
- after natural 9/27 results, run #425/#426 manual checkpoints with end_date=2026-09-27;
- update counts from actual outputs only;
- no retune / Production change.

`MANUAL_CHECKPOINTS_READY / REVIEW_GATES_READY / WAIT_927_NIGHTLY / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 20:12 JST

- main: `19cb1f0cff51509bbb39346b499af33f7280ecf7`
- #422 common Forward economics: merged
- #423 exact validation suite: merged
- #415/#416/#419/#420: closed as superseded
- Railway staged/pending: none
- fallback Cron: 08:25 JST unchanged
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Validated common scorecard:
- V4 TOP2: ROI 171.4062%, +4,570 JPY, DD 2,200, max losing 11
- S03_M2: ROI 190.9434%, +4,820 JPY, DD 1,600, max losing 16
- invalid_result / non-official = void, zero investment

`COMMON_ECON_ON_MAIN / EXACT_VALIDATION_ON_MAIN / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 20:03 JST

- main: `2e89e81f00b02a66c7a99ac0f6b02e2d43bf406b`
- Production staged/pending: none
- fallback Cron remains 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Common Forward economics:
- #415 pure contract: green
- #416 existing N02/S03 semantics parity: green
- #419 formal V4 TOP2 exact common parity: green
  - 32 evaluated / 4 invalid
  - ROI 171.4062% / +4,570 JPY
  - DD 2,200 / max losing 11
  - halves 203.4375% / 139.375%
  - bootstrap P>100 = 89.13%
- #420 S03_M2 exact common parity: green
  - 53 evaluated / 1 invalid / 8 pending
  - ROI 190.9434% / +4,820 JPY
  - DD 1,600 / max losing 16
  - halves 319.6154% / 67.0370%
  - bootstrap P>100 = 86.13%

No promotion or retune is authorized by the common scorecard.

`SAME_ECONOMIC_DENOMINATOR / INVALID_RESULT_VOID / EXACT_V4_S03_PARITY / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 19:53 JST

- main: `809f47ec618a29b2f6b356173b286ec70181777d`
- Production staged/pending: none
- fallback remains 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Evaluation infrastructure:
- #415 common Forward economics: all CI SUCCESS
  - evaluated = economic settlement
  - invalid_result = void / zero investment
  - pending = zero investment
  - V4 official/non-official normalization included
- #416 read-only parity: PASS
  - S03 rows 116 / evaluated 102 / invalid 2 / pending 12
  - common vs existing metrics/risk exact match
- main registry: `docs/RESEARCH_PR_REGISTRY_20260927.md`
- failure runbook: `docs/FORWARD_EVIDENCE_FAILURE_RUNBOOK_20260927.md`

No research result is promoted by the common evaluator itself.

`INVALID_RESULT_VOID / COMMON_FORWARD_METRICS / EXACT_S03_PARITY / PR_AMBIGUITY_REDUCED / PROD_UNCHANGED`

## LATEST OVERRIDE — 2026-09-27 19:10 JST

- main: `a50afa2f166da498b25f03f09383be14ab78b044`
- Railway Production staged changes/pending work: none
- dispatcher Cron remains `25 23 * * *` UTC (08:25 JST)
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

New safe research:
- #411 future-only day-strength shadow: all CI SUCCESS
  - starts 2026-09-28
  - mean formal TOP6 `race_score`
  - compare to prior-7 formal-day median
  - shadow label only; no Production action
- #412 fallback timing: all CI SUCCESS
  - 08:20 JST is the only frozen candidate passing cutoff/primary/worst-headroom criteria
  - projected worst feed headroom ~6m21s
  - **not applied**
  - current Cron remains 08:25 JST
- #413 F-count current-artifact compatibility: all CI SUCCESS
  - exact 2026-09-27 formal artifact accepted by #400/#398 using synthetic 36-row sentinel input
  - formal core hash remains `8907e244...8d3`
  - no real F-count read or persistence
  - live F-count remains unapproved

Next:
- refresh #409 after natural 9/27 results load;
- evaluate #411 only on 9/28+ future formal days;
- continue S03 to 100;
- any fallback Cron change or F-count activation requires explicit approval.

`SHADOW_PREREG_GREEN / 0820_TIMING_CANDIDATE_ONLY / FCOUNT_COMPAT_GREEN / NO_PROD_CHANGE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 18:36 JST

- main: `1d40d83b4cb0a2ecbf21a8555ea06d23a7ca1d6f`
- Production model/selector/threshold/candidate/stake unchanged.
- `purchase_action=false`.
- Railway staged changes: none; pending work: none.
- F-count live capture/persistence/schedule remains unapproved.

Research:
- #409 V4 immutable formal Forward:
  - formal available dates 2026-09-21..09-27;
  - 09-16..09-20 remain unavailable and must not be reconstructed;
  - through 09-26: 6 resolved formal days / 32 official races / 4 void;
  - formal TOP2: 64 bets / 10 hits / ROI **171.4062%** / **+4,570 JPY**;
  - first 3 days ROI 191.0714%, second 3 days 156.1111%;
  - leave-one-hit min ROI 119.0323%;
  - leave-one-day worst ROI 125.1923%;
  - bootstrap P(ROI>100%) 89.13%;
  - TOP1 ROI 80.3125%;
  - ticket-order attribution: order1 80.3125%, order2 262.5% — descriptive only, no policy change;
  - provider-selected dynamic checkpoint path validated;
  - next gates 10 / 20 / 30 resolved formal days.
- #405 S03_M2 prospective:
  - CONTRACT_CLEAN;
  - 53 officially evaluated / 4 hits / ROI **190.9434%** / **+4,820 JPY**;
  - bootstrap P(ROI>100%) 86.13%;
  - first half 319.6154%, second half **67.0370%**;
  - leave-one-hit min ROI 108.2692%;
  - 100-observation frozen review still required; 47 remain.
- #406 historical S03:
  - timing-valid original-window ROI 26.1842%;
  - all-available strict timing-safe ROI 19.5098%;
  - old ~126% profitability support rejected.
- #408 S02: 43 evaluated / ROI 16.7442% / -3,580 JPY; deprioritized.
- #407 GUARD05: 768 evaluated / affected 0; deprioritized.

`V4_TOP2_PROSPECTIVE_POSITIVE_SMALL_N / S03_PROSPECTIVE_POSITIVE_WITH_RECENT_WEAKNESS / HISTORICAL_PROFIT_SUPPORT_REJECTED / NO_RETUNE / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 17:22 JST

- main: `db8ab21270ea5bc8fd6872bed576d4ba196c43e8`
- PR #401 is **merged/activated** with explicit approval.
- active prospective-freeze workflow no longer enumerates Railway variables or writes `railway-vars.json`.
- DB injection now uses fixed project / `production` / `postgres-recovery` through `railway run`, with child-process `DATABASE_PUBLIC_URL -> DATABASE_URL`.
- schedule remains `16 23 * * *` UTC; 08:15 cutoff / V4 model / selector / formal tickets / availability guard unchanged.
- Railway Production staged changes: none; pending work: none.
- fallback dispatcher deployment `e7c51f36-3e5b-4f4d-85a3-7e872ec453c7`: SUCCESS at main `db8ab212...`.
- fallback dispatcher Cron remains `25 23 * * *` UTC.
- recent GitHub scheduled formal freezes 2026-09-23..09-27 failed closed due late schedule delivery.
- recent fallback workflow_dispatch formal freezes 2026-09-23..09-27 all succeeded.
- 2026-09-27 fallback run `36279479671`: 08:29:29 -> 08:29:31 JST, earliest feed deadline 08:32, eligible=true, guard PASS_ACTIVE_CORE.
- fallback completion headroom can be tight: recent minimum about 81 seconds.
- fallback Cron change remains a separate explicit approval gate.
- #397/#398/#400 F-count preparation remains research-only; live F-count capture/persistence/schedule is not approved.
- Production model / selector / threshold / candidate / stake unchanged.
- `purchase_action=false`.

`PR401_ACTIVATED / NON_ENUMERATING_ROUTE_LIVE / FALLBACK_CAPTURE_HEALTHY_WITH_TIGHT_MARGIN / FCOUNT_LIVE_CAPTURE_NOT_APPROVED / PRODUCTION_MODEL_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 16:52 JST

- main: `e3272d23841aa1d3ce5459ba68841e48cddcf16f` (docs-only PR #402)
- Railway Production staged changes: none
- dispatcher deployment `85791bd2-dc70-4aa5-a6ae-aee7790d33de`: SUCCESS
- Production prediction/model/selector/threshold/candidate/stake unchanged
- `purchase_action=false`
- #394: recent_form = 0 / 413,820 -> reject
- #395: unused entry fields present, but historical 08:15 row timing not proven
- #396: F count shape-ready; L count degenerate; no outcome read
- #397: prospective F-count head-error diagnostic preregistered; pure contract green; no persistence
- #398: hash-bound separate companion contract green; formal V4 core immutable
- #400: exact-36-row pure adapter green; all 5 CI SUCCESS; no I/O/persistence
- #401: non-enumerating DB-route hardening Draft green; live freeze skipped; **not merged**
- #397/#398/#401 may show mergeable=false after docs-only main advances; rebase before any future merge
- next live step remains an **explicit approval gate**
- no historical F-count coefficient search/backfill is authorized

`FCOUNT_ACTIVATION_PREP_COMPLETE / LIVE_FCOUNT_CAPTURE_NOT_APPROVED / PRODUCTION_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 POST-PR401

- main: `a255aa3a5d17cef953685f801b447ca6c80db28a`
- Railway Production staged changes: none
- dispatcher latest deployment SUCCESS; Production prediction/purchase behavior unchanged
- #394 recent_form empty -> reject
- #395 unused entry data present but historical 08:15 row timing unproven
- #396 F count shape-ready; L count degenerate
- #397 prospective head-error diagnostic pure contract green; no persistence
- #398 hash-bound companion pure contract green; formal V4 core immutable
- #400 exact-36-row pure adapter green; no I/O/persistence
- #401 non-enumerating DB-route hardening Draft green; PR safety-only run confirmed; live freeze skipped
- next step remains an **explicit approval gate** for any live Forward-route activation or F-count companion persistence
- no historical F-count coefficient search is authorized
- `purchase_action=false`

`FCOUNT_ACTIVATION_PREP_COMPLETE / LIVE_CAPTURE_NOT_APPROVED / PRODUCTION_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 16:24 JST

- main: `dac9314f17035c424f5455ff604432150a276e13` (docs-only #393)
- Railway Production staged changes: none
- Production behavior unchanged / `purchase_action=false`
- #394: recent_form empty 0/413,820 -> reject
- #395: unused numeric entry fields high coverage, but historical 08:15 row timing unproven
- #396: F count shape-ready (100% full-six, 57.0741% within-race variation, 15.0826% positive); L count degenerate
- #397: pure prospective F-count head-error diagnostic preregistered, final CI SUCCESS, no collector/persistence
- #398: separate hash-bound F-count companion artifact pure contract; all CI SUCCESS; formal V4 core remains immutable
- next step is **explicit-approval gate** for prospective F-count companion capture/persistence; evidence format is already frozen in #398
- no historical F-count coefficient search is authorized

`F_COUNT_PROSPECTIVE_DIAGNOSTIC_READY_FOR_ACTIVATION_REVIEW / NO_FORWARD_PERSISTENCE_YET / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 15:30 JST

**現在の短期スナップショット。古いsectionは履歴として扱い、再開時はlive再取得する。**

### Current source / health
- main: `997b7cce30e1ce5c5a04905f9a22a95236930c6b`
- Railway Production staged changes: none at latest read-only check
- V4 fallback dispatcher: SUCCESS, Cron `25 23 * * *` UTC
- main Production cron群: latest deployments SUCCESS
- Production prediction/selector/purchase behavior unchanged
- `purchase_action=false`

### Research state
Canonical long history remains 432 exact-six days / 2,592 races through 2026-09-22.

Completed since the prior snapshot:
- #387 input ablation: no harmful current layer removal supported
- #389 strict-prior ST: 0/344 head classifications changed; tiny calibration-only gain, full reselection worse
- #390 course movement: broad movement not head-error concentration; predicted-head-moved n=19 too small/unstable
- #391 Exhibition ST Forward health: n=1,879, proper scores slightly worse overall; no promotion
- #392 exhibition-time-rank OOS: canonical run `36288864737`, artifact `10921393420`
  - Track A fixed-race LogLoss/Brier improved
  - head accuracy unchanged 57.558% -> 57.558%
  - head changed 0/344
  - preregistered primary head-accuracy gate failed
  - Track B descriptively improved but is not promotion authority
  - do not rerun or expand coefficient grid

### Immediate next action
Run a **result-blind recent-form readiness audit** before defining another model variant:
- canonical-period non-empty coverage;
- racer binding / structure;
- official source/provenance;
- strict-prior chronology relative to target race and current 08:15 JST cutoff;
- no result-based feature design.

If provenance/timing cannot be proven, reject `recent_form` as a current V4 input candidate and move to the next independent information family without tuning the failed families.

### Recent-form readiness result

PR #394 completed a result-blind read-only audit:
- run `36300918133` SUCCESS;
- 413,820 canonical-period entry rows scanned;
- non-empty `recent_form`: 0;
- full-six non-empty races: 0;
- strong source-capture timestamp column: none;
- classification: `NOT_READY_FAIL_CLOSED`;
- no result/odds/payout read, no collector, no DB write.

Do not define a recent-form transformation or coefficient and do not reconstruct historical values after outcomes.

### Immediate next action

Run a **result-blind unused pre-race information inventory**:
- identify entry fields not already consumed by current V4;
- measure non-null/full-six coverage;
- verify source/writer provenance and 08:15 availability;
- no outcome read and no performance-based feature selection.

Current V4 base already consumes racer class, national win rate, national place2 rate, local place2 rate and avg ST; Motor2 is separately used.

### Do not
- rerun #387/#389/#390/#391/#392 canonical experiments
- expand #392 coefficient grid
- create a Track-B-only promotion path from #392
- retune old weather/course/ST/exhibition families on the same history
- change Production without explicit approval

`FAIL_CLOSED / RESULT_BLIND_READINESS_FIRST / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-25 13:51 JST

**このsectionを現在の短期スナップショットとして扱う。古いsectionのSHA、PR状態、Railway staged状態、件数は歴史的背景であり、再開時は必ずlive再取得する。**

### Source of Truth

- repo: `kenshoushouri-cloud/boat-ai-v2`
- code: GitHub `main`
- Production data: Railway PostgreSQL
- Railway project: `boat-v2-postgres`
- current checked main: `903a55f5bcd4a6fe3bff6d39270e5b911878a83e`

### Production health at latest check

Boat Railway Production:
- environment staged changes: **none**
- `candidate-discovery-v4-fallback-dispatcher`: latest deployment SUCCESS
- `cron-data-prepare`: SUCCESS
- `cron-final-check`: SUCCESS
- `cron-nightly-results`: SUCCESS
- `cron-window-morning`: SUCCESS
- `cron-window-day`: SUCCESS
- `cron-window-night`: SUCCESS

No Production logic change was made during the latest research sequence.

### Current research focus

Goal remains long-run positive economics, not hit-rate alone.

Long-history canonical evidence:
- run `35851936772`
- artifact `10745234979`
- JSON SHA256 `4f814a4c5a89e7f014ca32a91ef9e477ce076ebd1527eeab306c96be5759b286`
- 432 evaluated days / 2,592 races
- current 2pt ROI 75.069%

Daily volume:
- #385 Draft / CI green
- 1R/day all-period ROI 97.083%, but pure blocks 3-10 only 75.131%
- 6R/day pure blocks 3-10 ROI 69.748%
- conclusion: 1R/day reduces loss/DD but is not proven profitable

One-race selector:
- #386 Draft / CI green
- structural selector blocks 3-10 ROI 71.40%
- fixed daily-rank-1 blocks 3-10 ROI 75.13%
- conclusion: selector FAILED

Head diagnosis on fixed daily-rank-1, blocks 3-10:
- 344 days
- Top1 head accuracy 57.6%
- Top2 head coverage 58.7%
- Top2 same-head 95.1%
- race_score head-correct AUC ~0.522
- main error bucket = first-place miss

### Immediate next action

PR #387:
`Research: preregister V4 input-information ablation`

- head `0cb6b0192a58ed41f9f644ea73c9c43f20cc8b32`
- Draft / mergeable
- 5 CI SUCCESS
- no evaluation run yet

Frozen variants:
`control / no_course / no_opponent / no_motor / base_only`

Run two tracks:
1. fixed current-control daily-rank-1 race, all variants recomputed on same race
2. variant-specific full daily reselection

Primary:
- head accuracy
- first-place logloss
- first-place Brier

Secondary:
- formal Top2 hit
- ROI/profit
- profitable-day rate
- max drawdown
- selector overlap

Period/block:
- 2025-07-01..2026-09-22
- 10 chronological blocks
- primary retrospective comparison blocks 3-10

Do not:
- add variants after results
- search coefficients
- introduce odds/EV
- add new information before this ablation is complete
- change Production

### Important research caution

The 2,592-race history has already been inspected many times. New same-history rules are development evidence only. A positive historical result must not be promoted without fresh prospective shadow evidence.

Current long-history information coverage is highly uneven:
- Motor ~97.8%
- Course any ~14.7%
- Opponent ~3.0%

Therefore lack of historical improvement can reflect both weak layers and missing coverage.

### Relevant open Draft PRs

Always refetch the full open list. Highest relevance now:

- #387 input-information ablation — next
- #386 one-race selector — evaluated, failed to beat rank1
- #385 daily 1-3 race count — evaluated
- #384 structural rank reranker — failed
- #383 structural conditional reranker
- #382 economic reranker — failed
- #381 timing-safe profit gate — no robust passing policy
- #380/#379 alpha025 prospective shadow overlap
- #378 long-history replay infrastructure/evidence

Do not merge merely because a PR is open/green.

### Safety / approval

No approval needed:
read-only audit, research/backtest, Draft PR, CI, docs, safe evidence collection.

Explicit approval required:
Production-effect merge; Railway Production change; Production DB writes/schema/VACUUM; model/coefficient/threshold/candidate/stake change; new LINE actual send; Forward persistence; auto-purchase; paid/external actions.

`FAIL_CLOSED / PURCHASE_FALSE / NO_RESULT_AFTER_FORWARD_RECONSTRUCTION / NO_SECRET_ENUMERATION / NO_CAPACITY_DRIVEN_DELETION`

### Parallel TOTO note

Separate repo `kenshoushouri-cloud/toto-ai-v1`:
- main `f78494159ad0c2d4a670f9c908a6710a65767a76`
- PR #164 team-alias fix merged and Production deployment SUCCESS
- Round 1656 natural 21:00 JST cron/LINE confirmation remains pending
- one old diagnostic-service Railway STAGED patch remains; do not touch

### Restart checklist

1. Read `docs/PROJECT_HANDOFF.md` LATEST OVERRIDE.
2. Refetch Boat main/open PR/CI.
3. Refetch Railway Production status/staged changes.
4. Confirm #387 head/CI still current.
5. If unchanged, run exactly one preregistered read-only input-ablation replay.
6. Record evidence before proposing any new feature.
