# boat-ai-v2 Project Handoff

## LATEST OVERRIDE — 2026-09-30 11:51 JST

### HISTORICAL BACKFILL EXECUTION / TEIKOKU SUPPLEMENT CONFIRMED
Treat this as the newest historical-data execution state.

User-approved historical truth:
- use the pre-deadline value for historical backtests;
- aggressively acquire missing historical data;
- use 艇国データバンク where useful without replacing official BOAT RACE bulk sources.

Official B-file path:
- PR #480 merged to main;
- field-level parity validated against official archived racelist data;
- bulk importer writes only missing values on existing `v2_race_entries`;
- no overwrite, no INSERT, no result/odds/payout read.

Completed batch:
- 2025-09-01..09-07
- complete races: 936
- entry rows: 5,616
- fillable missing values: 11,344
- DB rows updated: 5,616
- result: `PASS_FILL_MISSING_ONLY`

Next batch already started:
- 2025-09-08..09-30
- GitHub Actions run: 36662632600
- same safety contract.

艇国:
- #478 merged for pre-race historical-table cross-check;
- #479 merged for strict prior-only dated motor-history reconstruction probe;
- #481 merged with the reusable official B-file bridge and fixed-URL connectivity probe;
- direct Railway-cloud connection to boatrace-db.net:443 timed out, matching GitHub-hosted runner behavior;
- do not bypass this with proxies or multi-IP access;
- test-beforeinfo-extra was restored to `python -u collect_candidate_filter_shadow_pg.py`, original watch patterns, and restore deployment `91402614-e57f-4552-874d-c3f55c7e32f5` succeeded;
- access rule encoded: >=3 seconds, known URLs, sequential use;
- do not source program/result/racer-term bulk data from 艇国 when BOAT RACE official downloads exist;
- do not back-project present-day aggregate values;
- dated rows strictly before the target cutoff may be used for supplemental reconstruction after source-specific validation.

Data-source order:
1. BOAT RACE official daily B / archived racelist;
2. official prior-only reconstruction;
3. 艇国 supplemental prior-only / cross-check;
4. unresolved fields remain missing rather than inferred from future information.

Historical evidence can improve research/backtests but does not increment V4 20-day or S03_M2 100-observation prospective gates.

Production model/selector/threshold/LINE/stake/purchase unchanged.
`purchase_action=false`.

`PREDEADLINE_HISTORICAL_TRUTH / OFFICIAL_BULK_FIRST / TEIKOKU_PRIOR_ONLY_SUPPLEMENT / BACKFILL_ACTIVE / NO_FUTURE_LEAKAGE / PROD_UNCHANGED`


## LATEST OVERRIDE — 2026-09-30 09:50 JST

### HISTORICAL DATA ACQUISITION EXPANDED
Treat this as the newest historical-data policy. Older "no historical F-count backfill" statements are superseded.

User direction:
- acquire missing historical data aggressively;
- use the pre-deadline value as historical truth;
- use 艇国データバンク where useful.

Accepted provenance:
1. BOAT RACE official target-day pre-race program/racelist/B data;
2. BOAT RACE official prior-only reconstruction using only events before the target deadline;
3. 艇国 supplemental historical data when its historical cutoff is provable/reconstructable and its access rules are obeyed.

Never use target-race outcomes while constructing historical features.

Historical F-count:
- official target-day F-count is now allowed as a historical predeadline input;
- do not perform outcome-guided coefficient/threshold search merely because historical F-count is available;
- prospective F-count companion evidence remains independently collected and separately labeled.

艇国:
- minimum 3-second automated access interval;
- known URLs only, single IP, avoid repeated static assets;
- do not substitute 艇国 for BOAT RACE official program/result/racer-term downloads;
- use primarily for gap-fill/cross-check and dated motor/venue/course ledgers where an as-of cutoff can be established.

Current execution:
- official racelist backfill through 2025-08-11 confirmed;
- 2025-08-12 onward batches running;
- PR #474 merged: racer_name/branch/origin fill-missing-only added;
- metadata-aware 2025-07-01..07-07 pilot running;
- historical Course 2025H2 complete; 2026H1 running;
- historical Opponent 2025-07/08 complete; 2025-09 retry after concurrent entry-write load settles;
- PR #475 Draft tests official daily B-file parity for a lower-load bulk path.

Historical evidence informs model research but does not count toward V4 20-day or S03_M2 100-observation prospective gates.

Production prediction/selector/threshold/LINE/stake/purchase unchanged.
`purchase_action=false`.

`HISTORICAL_ACQUISITION_EXPANDED / PREDEADLINE_IS_TRUTH / OFFICIAL_FIRST / TEIKOKU_SUPPLEMENT / FCOUNT_HIST_ALLOWED_NO_OUTCOME_SEARCH / PROD_UNCHANGED`


## LATEST OVERRIDE — 2026-09-30 00:55 JST

### MID-OCTOBER EXECUTION PATH / MONTHLY +50,000 JPY TARGET ADDED
Treat this section as the newest source of truth. Older override sections below are history.

#### GitHub / Railway
- main before this override: `33333a6952043071297a34a617da17075be07146`
- PR #452: merged — fallback dispatcher internal checkpoint aligned to **08:20 JST**
- PR #460: merged — isolated future-only F-count companion capture activated
- fallback service: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- fallback Cron read-back: **`20 23 * * *` = 08:20 JST**
- latest successful current-main deploy: `f7dd7219-5ecf-4976-ba40-85d51957bfea` — **SUCCESS**
- latest same-main redeploy `8c14f309-99f3-4332-a487-511225f03104`: **SUCCESS**
- staged config: none
- 9/29 formal prospective V4: **UNAVAILABLE**, immutable; no reconstruction/backfill

#### Core evidence
Through 2026-09-28:
- V4 formal TOP2: **8/20 days**, ROI **147.7273%**, profit **+4,200 JPY**
- S03_M2: **63/100 observations**, ROI **160.6349%**, profit **+3,820 JPY**
- S03 second-half ROI: **56.5625%**
- V5 core target review: **2026-10-15**

#### Monthly economics objective
Operational planning target:
- **+50,000 JPY net profit/month**

Do not optimize the selector directly for this target.

At 100 JPY/ticket and TOP2:
- 1 race/day requires ROI 933.33% for +50,000/month
- 2 races/day requires ROI 516.67%
- 3 races/day requires ROI 377.78%

At the current V4 formal 6R/day x TOP2 volume and ROI 147.7273%, the descriptive 30-day/100-JPY projection is about **+17,182 JPY**, not +50,000 JPY.

This means the correct order is:
1. complete prospective profitability evidence;
2. confirm natural notification volume;
3. use conservative economics, not headline ROI alone;
4. define bankroll/DD constraints;
5. only then make a separate Production stake proposal.

PR #461 adds the +50,000 JPY feasibility block to `research/forward_combined_checkpoint.py`.
Every routine combined checkpoint will expose the target gap while keeping:
- selector retune for profit target: false;
- stake change authorized: false;
- purchase action: false.

#### F-count
Future-only companion evidence is now active:
- valid formal freeze first;
- exact 36 `race_id/lane/f_count` rows;
- DB READ ONLY;
- separate hash-bound artifact;
- failure isolated from formal V4;
- no historical backfill;
- no coefficient search;
- no Production model/selector/LINE/stake change.

#### Immediate priorities
1. Do not miss future V4 formal days; preserve 08:20 fallback operation.
2. Continue frozen S03_M2 to 100 officially evaluated observations.
3. Accumulate F-count prospectively without adding it to V5 core.
4. Run monthly-profit feasibility on every combined checkpoint.
5. Do not raise stake merely to force +50,000 JPY before evidence gates and risk limits are satisfied.
6. Keep `purchase_action=false`.

`MID_OCTOBER_PATH_ACTIVE / FALLBACK_0820_ALIGNED / FCOUNT_CAPTURE_ACTIVE / MONTHLY_PLUS_50000_SCALING_TARGET / V4_8_OF_20 / S03_63_OF_100 / PROD_MODEL_UNCHANGED / PURCHASE_FALSE`


## LATEST OVERRIDE — 2026-09-29 17:10 JST

### SYSTEM PURPOSE / TIMELINE HANDOFF ADDED
Treat this section and the linked handoff guide as the newest orientation layer.

Read first:
1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260929.md`

The new guide records:
- the system-building objective;
- Production V4 vs V5 research-candidate scope;
- the 2026-10-15 V5 core target;
- mandatory V4 20-day / S03 100-observation gates;
- daily 08:15 / 08:16 / 08:25 / 08:32 / 23:30 operating timeline;
- current settled economics;
- the 2026-09-29 fallback incident;
- current safe 08:25 rollback state;
- Draft #452 08:20 code alignment status;
- work priorities;
- approval boundaries;
- next-chat checklist.

Current operational source of truth:
- main immediately before this docs update: `0dfe3518ea2789a701ffad90da170bf2b7d9f798`
- Railway fallback current Cron: **08:25 JST / `25 23 * * *`**
- latest dispatcher deployment: `0cc94e40-71af-4cb6-85c0-19e60532ea2e` — SUCCESS
- pending work: none
- Draft #452: all-green, **not merged**
- 2026-09-29 formal prospective artifact: **UNAVAILABLE**
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Current settled evidence through 2026-09-28:
- V4: **8/20**, ROI **147.7273%**, profit **+4,200 JPY**
- S03_M2: **63/100**, ROI **160.6349%**, profit **+3,820 JPY**
- V5 core target: **2026-10-15**

Do not reactivate 08:20 merely from the earlier approval.
A fresh explicit approval is required for the #452 code+Cron activation cycle.

`SYSTEM_HANDOFF_GUIDE_ADDED / PROD_0825_SAFE / PR452_NOT_MERGED / 929_UNAVAILABLE / V5_TARGET_20261015 / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-29 16:59 JST

### FINAL HANDOFF — fallback rollback safe / #452 green Draft / 2026-09-29 formal unavailable
Treat this section as the current source of truth. Older override sections below are history.

#### GitHub / Railway current state
- GitHub main: `aa9e9d3a1ad18d174be9b16a871eba5037990fe7`
- latest main commit: merge PR #454 `Docs: record fallback rollback and 9/28 refresh`
- Railway project: `268a5b17-0712-440a-884d-27f7fa887a2d`
- Production environment: `5ffb02f6-5ec8-4268-9bda-8e30431ff625`
- fallback dispatcher service: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- current fallback Cron: **`25 23 * * *` = 08:25 JST**
- latest dispatcher deployment: `5b967767-0300-4795-a81b-213410610d90`
- latest dispatcher deployment status: **SUCCESS**
- pending work: none
- staged/unmerged config: none
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

#### 2026-09-29 fallback incident
The explicitly approved 08:20 Cron activation exposed a code/config mismatch.

Observed:
- Railway Cron was changed to 08:20 JST;
- dispatcher process reached decision at **08:23:33 JST**;
- code returned:
  `action=NOT_DUE reason=before_0825_checkpoint`;
- no fallback `workflow_dispatch` was created.

Root cause:
- `research/candidate_discovery_v4_fallback_dispatcher.py` still had internal checkpoint **08:25**.

Natural GitHub schedule was also unusable:
- run `36513182505`
- created approximately **11:33 JST**
- availability hard-stop: 08:32 JST
- earliest frozen-feed deadline: 08:44 JST
- correctly failed closed.

Result:
- **2026-09-29 has no valid formal prospective V4 artifact**
- do not reconstruct
- do not backfill
- do not create a 9/29 day-strength label
- do not count 9/29 toward V4 resolved-day or optional day-strength gates

#### Production rollback
Rollback was applied immediately:
- 08:20 -> **08:25 JST**
- rollback deployment `26973382-903c-4d50-9a78-9c079d8c5577`: SUCCESS
- later docs-triggered dispatcher deployment `5b967767-0300-4795-a81b-213410610d90`: SUCCESS
- current Cron read-back remains **08:25 JST**

This is the current safe Production state.

#### Draft PR #452 — 08:20 code alignment
Open Draft:
- PR #452 `Fix: align fallback dispatcher checkpoint to 08:20 JST`
- head: `73dd7f593be1199edf32bb0710458548a6d2d32d`
- mergeable: true
- all CI SUCCESS

#452 changes:
- internal dispatcher checkpoint 08:25 -> 08:20;
- activation manifest aligned to 08:20;
- tests prove:
  - 08:19:59 => NOT_DUE / no GitHub call;
  - exactly 08:20 => fallback dispatch permitted.

**#452 is NOT merged.**

A new explicit approval is required before:
1. merging #452 if it will affect Production fallback behavior; and/or
2. changing Production fallback Cron back to 08:20.

Do not assume the previous approval authorizes this new code+Cron activation cycle.

#### Latest settled economics — through 2026-09-28
Canonical read-only refresh:
- workflow run `36538181451`
- job `109307018169`
- artifact `11018808467`
- digest `sha256:72eb6b5d309859f1b3ad82d886b2603c2006f59fb1af2365debbb97145cb6d21`

Formal V4 TOP2:
- resolved formal days: **8**
- settled races: 44
- head accuracy: **63.6364%**
- 88 bets / 12 hits
- investment: 8,800 JPY
- return: 13,000 JPY
- profit: **+4,200 JPY**
- ROI: **147.7273%**
- second chronological half ROI: **135.2083%**
- leave-one-day worst ROI: **112.3684%**
- leave-one-hit min ROI: **109.4186%**
- bootstrap P(ROI>100%): **85.63%**
- remaining to 10-day review: **2**

2026-09-28 single day:
- 12 bets / 1 hit
- investment 1,200 JPY
- return 660 JPY
- profit **-540 JPY**
- ROI **55.0%**
- preregistered `SKIP_SHADOW` would have avoided this one-day loss
- this is one-day descriptive evidence only; no promotion

S03_M2:
- evaluated: **63**
- invalid: 1
- pending: 0
- hits: 4
- investment: 6,300 JPY
- return: 10,120 JPY
- profit: **+3,820 JPY**
- ROI: **160.6349%**
- max DD: 2,000 JPY
- max losing streak: 20
- first half ROI: 268.0645%
- second half ROI: **56.5625%**
- bootstrap P(ROI>100%): **77.61%**
- remaining to 100-review: **37**

#### V5 core progress
Target:
- **2026-10-15 V5 core freeze review**

Current mandatory progress:
- V4: **8 / 20**, remaining 12
- S03_M2: **63 / 100**, remaining 37
- evidence contract: clean
- status: `COLLECTING_CORE_EVIDENCE`

2026-09-29 does not count because formal prospective evidence is unavailable.

Optional day-strength:
- resolved/classified future days: 1
- KEEP: 0
- SKIP: 1
- 9/28 = `SKIP_SHADOW`
- 9/29 = unavailable / no label

#### Immediate next work
Safe without new approval:
1. continue read-only audits / CI / Draft work on #452;
2. inspect dispatcher timing and add regression/safety tests;
3. continue nightly settlement / combined read-only evidence;
4. continue V5 milestone tracking;
5. preserve 9/29 as unavailable without reconstruction.

Requires explicit approval:
- merge/activate #452 if Production behavior changes;
- Production fallback Cron 08:25 -> 08:20 again;
- F-count live capture/persistence/schedule;
- Production DB writes/schema;
- Production model/selector/threshold/candidate/stake changes;
- LINE real-send;
- purchase activation.

Current gate:
`PROD_FALLBACK_0825_SAFE / 929_FORMAL_UNAVAILABLE / PR452_GREEN_DRAFT_NOT_MERGED / V4_8_OF_20_ROI_147_73 / S03_63_OF_100_ROI_160_63 / V5_TARGET_20261015 / NO_RETUNE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-29 16:45 JST

### 2026-09-29 fallback incident: 08:20 activation rolled back safely
- main before docs update: `ba71da8ae25b56b24942bb40df56dc1991f49505`
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

Approved 08:20 Cron activation exposed an internal-code mismatch:
- Railway Cron ran under 08:20 schedule;
- dispatcher log at **08:23:33 JST**:
  `action=NOT_DUE reason=before_0825_checkpoint`
- root cause: `research/candidate_discovery_v4_fallback_dispatcher.py` still had `CHECKPOINT = 08:25`
- therefore fallback did not create workflow_dispatch on 2026-09-29.

Natural GitHub schedule also remained severely late:
- run `36513182505`
- created approximately 11:33:44 JST
- availability hard-stop 08:32 JST
- freeze started 11:33:56 JST
- earliest frozen-feed deadline 08:44 JST
- correctly failed closed.

Result:
- **2026-09-29 has no valid formal prospective V4 artifact**
- do not reconstruct or backfill this date
- no day-strength classification for 9/29

### Production rollback complete
Production fallback Cron restored to:
- `25 23 * * *` = **08:25 JST**

Rollback deployment:
- `26973382-903c-4d50-9a78-9c079d8c5577`
- status **SUCCESS**

Current read-back:
- fallback Cron 08:25 JST
- pending/staged config none

### 08:20 code fix prepared, not activated
Draft PR #452:
- changes internal dispatcher checkpoint 08:25 -> 08:20
- updates activation manifest to 08:20
- tests:
  - 08:19:59 = NOT_DUE/no GitHub call
  - exactly 08:20 = fallback dispatch permitted
- all CI SUCCESS

#452 is **not merged**.
Reactivation of Production 08:20 remains explicit-approval only.

### 2026-09-28 settlement refresh
Canonical read-only run:
- workflow run `36538181451`
- job `109307018169`
- artifact `11018808467`
- digest `sha256:72eb6b5d309859f1b3ad82d886b2603c2006f59fb1af2365debbb97145cb6d21`

Readiness:
- 144/144 terminal
- official 144
- pending/missing 0

Formal V4 TOP2 through 9/28:
- resolved days: **8**
- settled races: 44
- head accuracy: **63.6364%**
- 88 bets / 12 hits
- investment 8,800 JPY
- return 13,000 JPY
- profit **+4,200 JPY**
- ROI **147.7273%**
- second chronological half ROI **135.2083%**
- leave-one-day worst ROI **112.3684%**
- leave-one-hit min ROI **109.4186%**
- bootstrap P(ROI>100%) **85.63%**
- remaining to 10-day review: **2**

2026-09-28 single-day formal TOP2:
- 12 bets / 1 hit
- investment 1,200 JPY
- return 660 JPY
- profit **-540 JPY**
- ROI **55.0%**

The pre-result day-strength label for 9/28 was `SKIP_SHADOW`.
For this one resolved day, SKIP would have avoided the -540 JPY formal loss.
This is descriptive one-day evidence only; no promotion or rule change.

S03_M2 through 9/28:
- evaluated **63**
- invalid 1 / pending 0
- hits 4
- investment 6,300 JPY
- return 10,120 JPY
- profit **+3,820 JPY**
- ROI **160.6349%**
- max DD 2,000 JPY
- max losing streak 20
- first half ROI 268.0645%
- second half ROI **56.5625%**
- bootstrap P(ROI>100%) **77.61%**
- remaining to 100-review: **37**

### V5 core progress
- formal V4: **8 / 20**, remaining **12**
- S03_M2: **63 / 100**, remaining **37**
- target: 2026-10-15
- status: `COLLECTING_CORE_EVIDENCE`

9/29 is unavailable and does not count.

`FALLBACK_ROLLBACK_0825 / 929_FORMAL_UNAVAILABLE / FIX_452_GREEN_NOT_MERGED / V4_8_OF_20_ROI_147_73 / S03_63_OF_100_ROI_160_63 / NO_RETUNE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-28 21:43 JST

### Production fallback Cron moved to 08:20 JST with explicit approval
- GitHub main before this docs update: `f7115240122da782375affe6dcb3be1798081812`
- user explicitly approved the prepared #412 Railway Cron change
- Railway project: `268a5b17-0712-440a-884d-27f7fa887a2d`
- environment: production `5ffb02f6-5ec8-4268-9bda-8e30431ff625`
- service: `candidate-discovery-v4-fallback-dispatcher`
- service ID: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

### Exact applied delta
Before:
- `cronSchedule = 25 23 * * *`
- 08:25 JST

After:
- `cronSchedule = 20 23 * * *`
- **08:20 JST**

Only `cronSchedule` was changed.

Pre/post config invariants:
- source repo: `kenshoushouri-cloud/boat-ai-v2`
- source branch: `main`
- builder: `RAILPACK`
- buildEnvironment: `V3`
- startCommand: `python -u research/candidate_discovery_v4_fallback_dispatcher.py`
- restartPolicyType: `NEVER`
- runtime: `V2`
- region: `us-west2`
- replicas: 1
- variable values were not read or displayed
- unmerged/staged config: none

### Activation deployment
- deployment: `2141e0fa-0897-4b2d-b5c7-94f2b03e571d`
- commit: `f7115240122da782375affe6dcb3be1798081812`
- final status: **SUCCESS**
- completed around 21:42 JST

Post-change read-back:
- Railway service Cron: `20 23 * * *`
- service config invariants above unchanged
- unmerged/staged config count: none

Rollback:
- `20 23 * * * -> 25 23 * * *`

### Why 08:20
This is the already-preregistered #412 candidate.

Frozen timing audit:
- 08:20 was the only candidate satisfying:
  1. >=5 minutes after the 08:15 source cutoff;
  2. >=4 minutes after nominal 08:16 primary;
  3. projected worst observed schedule-to-freeze latency still leaves >=5 minutes before the earliest observed feed deadline.
- projected worst feed headroom at 08:20: about **380.604 sec (~6m21s)**.

Latest 2026-09-28 evidence strengthened the rationale:
- natural GitHub schedule expected around 08:16 but started around 10:37 JST and failed closed;
- old 08:25 fallback dispatched around 08:29:08;
- formal freeze started 08:31:26 and completed 08:31:28;
- the old fallback therefore succeeded but ran close to its 08:32 availability hard-stop.

The 08:20 change does not fix GitHub schedule delivery latency.
It increases fallback safety margin.

### First live observation under 08:20
The first natural Production fallback cycle using the new Cron will be the 2026-09-29 target-day cycle.

Observe:
- actual Railway dispatcher action time;
- workflow_dispatch creation time;
- formal freeze start/completion;
- earliest feed deadline;
- whether headroom improves as expected.

Do not retune the V4 model from this operational change.

### Current evidence state remains
Before 9/28 settlement:
- V4: 7 / 20 resolved formal days
- S03_M2: 61 / 100 evaluated
- day-strength: 1 future day / KEEP 0 / SKIP 1
- 9/28 classification: SKIP_SHADOW
- V5 core target: 2026-10-15

`FALLBACK_CRON_0820_ACTIVE / ACTIVATION_DEPLOYMENT_SUCCESS / ONLY_CRON_CHANGED / FIRST_LIVE_CHECK_20260929 / PROD_MODEL_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-28 15:12 JST

### 2026-09-28 first future-only day-strength shadow is captured
- main before this docs update: `29571653276b6c31fc8321c81cfaf52c135cd090`
- Production remains V4
- V5 core mandatory progress remains **V4 7/20, S03_M2 61/100** until 9/28 results settle
- `purchase_action=false`

### Valid 2026-09-28 formal artifact
Natural schedule run:
- run `36366680495`
- started approximately 10:37 JST
- availability hard-stop 08:32 JST
- earliest frozen-feed deadline 10:02 JST
- correctly failed closed because it was too late
- do not use this failed scheduled run as formal evidence

Valid fallback provider run:
- workflow_dispatch run `36358843505`
- success
- artifact `10945160972`
- artifact digest `sha256:34341de57e1090771692db425cbc1416d3dabe97f4d391feb244a6397958ed05`
- prospective artifact SHA256 `1c080acc70d138f85466269b337892b9ad5eccd797d45d1158c6bcb3596345d1`
- canonical core SHA256 `7fce9e849f66dca82b8ba4c358bc68a131e858c0749216ca7e21f68bb822a93f`
- started 08:31:26 JST
- completed 08:31:28 JST
- earliest core/feed deadline 10:02 JST
- prospective evidence eligible=true
- availability gate `PASS_ACTIVE_CORE`
- result/payout read=0
- purchase_action=false

### First day-strength classification
Canonical one-off evidence:
- PR #449, closed unmerged
- run `36384993197`
- job `108808405878`
- result: `PASS_RESULT_BLIND`

Frozen rule:
- target day_strength = mean formal TOP6 race_score
- reference = median immediately prior 7 FORMAL_AVAILABLE day strengths

2026-09-28:
- target strength: **0.93618881**
- frozen reference: **0.93817204**
- classification: **SKIP_SHADOW**
- margin target-reference: **-0.00198323**
- formal_action_changed=false
- promotion_allowed=false
- DB/result/payout/odds reads=0

Optional day-strength progress:
- future classified days: **1**
- KEEP: **0**
- SKIP: **1**

Admission gate remains unchanged:
- >=10 future resolved days
- >=3 KEEP
- >=3 SKIP

This first SKIP is descriptive shadow evidence only. It does not cancel or alter the formal TOP6/TOP2 action.

### V5 core status
Mandatory counts remain unchanged until 9/28 settlement:
- formal V4: **7 / 20**, remaining 13
- S03_M2: **61 / 100**, remaining 39
- status: `COLLECTING_CORE_EVIDENCE`
- target core freeze review: 2026-10-15

Next:
- wait for natural 9/28 nightly settlement;
- then run combined checkpoint for end_date=2026-09-28;
- evaluate V4/S03/V5 progress without retuning;
- separately record whether the first SKIP day would have been economically helpful only after results are officially available.

No Production action follows automatically from that comparison.

`928_FORMAL_FALLBACK_VALID / DAY_STRENGTH_1D_SKIP / V5_CORE_7_OF_20_61_OF_100 / WAIT_928_SETTLEMENT / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-28 01:12 JST

### 2026-09-27 natural settlement is complete
- main before this docs update: `6e82ee37961c3e83f867be0773b8f0ac94d6842b`
- nightly results completed 2026-09-27 23:38:50 JST
- target readiness: 156/156 terminal, official 156, pending/missing 0
- #446 merged: S03 exact-parity baseline separated from live checkpoint
- #447 canonical post-nightly refresh: PASS_READ_ONLY, closed unmerged as evidence-only
- Production model/selector/TOP6/TOP2/stake unchanged
- fallback Cron remains 08:25 JST
- `purchase_action=false`

### Formal V4 TOP2 — 7 resolved days
Through 2026-09-27:
- resolved formal days: **7**
- official settled races: 38
- head accuracy: **65.7895%**
- TOP2 bets: 76
- hits: 11
- investment 7,600 JPY
- return 12,340 JPY
- profit **+4,740 JPY**
- ROI **162.3684%**

Robustness:
- first block 9/21..9/23 ROI 191.0714%
- later block 9/24..9/27 ROI **145.6250%**
- largest-hit share 29.0924%
- leave-one-day worst ROI **123.1250%**
- leave-one-hit min ROI **118.2432%**
- whole-day bootstrap P(ROI>100%) **89.64%**

Next frozen formal review:
- 10 resolved days
- remaining **3**

### S03_M2 — 61 evaluated
Natural 9/27 settlement increased evaluated count from 53 to **61**.

Current:
- positive rows 62
- evaluated 61
- invalid 1
- pending 0
- hits 4
- investment 6,100 JPY
- return 10,120 JPY
- profit **+4,020 JPY**
- ROI **165.9016%**
- max DD 1,800 JPY
- max losing streak 18

Stability:
- first half ROI 277.0%
- second half ROI **58.3871%**
- bootstrap P(ROI>100%) **79.50%**

Interpretation:
- overall remains >100%;
- recent-half weakness increased;
- do not retune;
- continue unchanged to the frozen 100-evaluated review.

Remaining:
- **39** observations.

### S03 checkpoint bug fixed
The first post-nightly refresh exposed that `research/s03_m2_common_economics_pg.py` incorrectly treated END=2026-09-27 as an immutable 53-evaluated parity baseline.

#446 fixed this safely:
- exact parity is now pinned to fully settled 2026-09-13..09-26;
- later dates are dynamic read-only checkpoints;
- scoring/timing rule unchanged.

### V5 core progress
Target:
- **2026-10-15** core freeze review.

Mandatory current progress:
- V4: **7 / 20**, remaining **13**
- S03_M2: **61 / 100**, remaining **39**
- evidence contract: clean
- status: `COLLECTING_CORE_EVIDENCE`

No automatic promotion is authorized.

### Next
- continue formal V4 daily evidence unchanged;
- continue S03_M2 unchanged;
- 2026-09-28 day-strength shadow remains result-blind/manual with frozen first reference 0.93817204;
- do not add new V5-core features before 2026-10-15 scope review.

`V4_7D_ROI_162_37 / S03_61_ROI_165_90_RECENT_WEAK / V5_7_OF_20_61_OF_100 / NO_RETUNE / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 22:40 JST

### V5 mid-October completion framework is fully main-integrated
- main: `41fbe4f4b3cf1da5d6a48df98d4c2714ab26ece4`
- #437 merged: V5 core milestone contract
- #438 merged: V5 core progress in combined checkpoint
- #439 merged: V5 Oct 15 roadmap in handoff/current-state
- #440 merged: pure V5 freeze review packet builder
- #441 merged: V5 scope lock through 2026-10-15
- Production remains V4
- `purchase_action=false`

### What "V5 complete by mid-October" means
Target:
- **2026-10-15 V5 core research-candidate freeze review**

Completion at this milestone means:
1. mandatory prospective evidence gates are reached;
2. the review packet can be generated from frozen evidence;
3. the V5 core research specification can be deliberately frozen for a new Forward phase.

It does not mean:
- long-run ROI >100% is proven;
- automatic Production promotion;
- purchase activation.

### Mandatory gates
- formal V4 >=20 resolved FORMAL_AVAILABLE days;
- S03_M2 >=100 officially evaluated observations;
- evidence contract clean.

Current pre-9/27-nightly baseline:
- V4: 6 / 20;
- S03_M2: 53 / 100.

If 9/27 settles naturally:
- V4 becomes 7 / 20;
- daily formal evidence would place 20 days around 2026-10-10.

Recent S03 observation pace suggests:
- 100 evaluated around 2026-10-09..10 if the pace remains similar.

These are schedule estimates only.

### #440 — V5 freeze review packet
Main:
- `research/v5_freeze_review_packet.py`
- `docs/V5_FREEZE_REVIEW_PACKET_20261015.md`

Input:
- combined Forward checkpoint JSON;
- optional day-strength summary.

Output includes:
- V4 economics/robustness;
- S03 economics/risk/halves/bootstrap;
- V5 core milestone status;
- optional-layer admission state;
- descriptive ROI>100 flags.

Even when counts are ready, output is only:
`CORE_EVIDENCE_READY_FOR_HUMAN_FREEZE_REVIEW`

Never automatic:
- Production activation;
- model/selector/stake changes;
- LINE;
- purchase.

### #441 — V5 scope lock
Main:
- `research/v5_scope_lock.py`
- `docs/V5_RESEARCH_SCOPE_LOCK_20260927.md`

Until 2026-10-15:
- no new feature enters V5 core;
- mandatory gates are not lowered to meet the date;
- no post-outcome retuning;
- current V4 probability/selector contract remains the baseline.

Optional/nonblocking:
- day-strength only if its existing 10 future resolved + 3 KEEP + 3 SKIP gate is naturally satisfied;
- F-count remains separately approval-gated.

Deferred from the 10/15 core:
- recent_form;
- L-count;
- exhibition ST/time;
- weather/water;
- odds/EV selector;
- any new unpreregistered feature.

These can become later V5.1 research instead of delaying the V5 core milestone.

### Operational path
Tonight after natural result completion:
- run the repaired combined checkpoint for `end_date=2026-09-27`;
- it now emits V5 core remaining counts/status directly;
- terminal result readiness remains fail-closed;
- do not retune.

From 2026-09-28:
- continue result-blind day-strength shadow;
- frozen first reference = 0.93817204;
- day-strength remains optional for V5 core.

### Approval boundaries unchanged
Explicit approval remains required for:
- fallback Cron 08:25 -> 08:20;
- F-count live read/capture/persistence/schedule;
- Production DB writes/schema;
- Production model/selector/threshold/candidate/stake changes;
- LINE real-send;
- purchase activation.

`V5_TARGET_20261015 / FREEZE_PACKET_MAIN / SCOPE_LOCK_MAIN / NO_FEATURE_CREEP / CORE_V4_20_S03_100 / PROD_V4_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 22:33 JST

### V5 research-candidate roadmap is now main-integrated
- main: `56a968c9fb7d0ba05a7e04a54f50fd4a25268b84`
- #437 merged: V5 research-candidate milestone contract
- #438 merged: V5 core progress exposed by the combined manual checkpoint
- Production V4 model/selector/TOP6/TOP2/stake unchanged
- fallback Cron remains 08:25 JST
- `purchase_action=false`

### Naming / scope
Production is still V4.

However the project is now explicitly tracking a **V5 research candidate** rather than treating all work as another V4 coefficient tweak.

Target:
- **2026-10-15 V5 core freeze review**

This target means:
- enough independent prospective evidence exists to freeze a V5 core research specification;
- that specification can enter a new Forward phase.

It does **not** mean:
- long-run ROI >100% has been proven;
- Production is automatically promoted;
- purchase is enabled.

### Mandatory V5 core gates
Both are required:
1. formal V4 >= **20 resolved FORMAL_AVAILABLE days**;
2. S03_M2 >= **100 officially evaluated observations**;
3. evidence contract remains clean.

Current pre-9/27-nightly baseline:
- V4: **6 / 20**, remaining 14;
- S03_M2: **53 / 100**, remaining 47;
- evidence contract: clean.

If 2026-09-27 settles naturally:
- V4 becomes 7/20;
- at one resolved formal day/day, the 20-day point is approximately **2026-10-10**.

S03 recent pace:
- 53 evaluated observations accumulated over 2026-09-13..09-26;
- if roughly the recent pace continues, 47 remaining is approximately another 12-13 days;
- practical estimate: around **2026-10-09..10**.

These are observation-count schedule estimates only, not ROI forecasts.

### Optional layers do not block the 10/15 core milestone
#### Day-strength
Frozen admission gate remains unchanged:
- >=10 future resolved days from 2026-09-28;
- >=3 KEEP_SHADOW;
- >=3 SKIP_SHADOW.

If those labels do not occur naturally by 10/15:
- do not loosen the gate;
- do not manufacture volume;
- freeze the V5 core without day-strength;
- keep day-strength shadow-only until its own gate is reached.

#### F-count
- not required for 10/15 core freeze;
- live capture remains separately approval-gated;
- no historical backfill;
- no historical coefficient search.

This avoids delaying V5 just to force an unproven input into the architecture.

### V5 architecture principle
Start from the existing V4 baseline rather than replacing it wholesale.

Core baseline:
- racer class;
- national win rate;
- national place2 rate;
- local place2 rate;
- average ST;
- venue/course bias;
- Racer Course coefficient 0.50;
- Opponent Pressure 1.0 first-place-only;
- Motor2 beta 0.06;
- probability temperature 2.20;
- structural selector head_p1 / head_margin / top3_mass / concentration;
- TOP6 races / formal TOP2 tickets.

V5 candidate review may admit only evidence that survives its own prospective contract.

Do not automatically blend:
- S03_M2;
- day-strength;
- F-count;
- exhibition/weather/other late features.

### Combined checkpoint now reports V5 core progress
Main workflow:
`.github/workflows/research-forward-combined-checkpoint-manual.yml`

The combined output now includes:
- V4 resolved formal days remaining to 20;
- S03_M2 evaluated observations remaining to 100;
- target freeze date 2026-10-15;
- `COLLECTING_CORE_EVIDENCE` or `V5_CORE_FREEZE_REVIEW_READY`.

Optional layers are deliberately not inferred by the combined core progress field.

### Schedule assessment
10/15 is **achievable as a research-candidate freeze target**, provided:
- formal artifacts continue to be available on most days;
- nightly result/data operations remain healthy;
- S03 observation rate does not collapse;
- neither frozen evidence stream fails its economics/robustness review.

The schedule is not compatible with claiming long-run profitability by 10/15.

### Immediate work remains
Tonight:
- after natural 23:30 JST nightly results and terminal readiness, run the combined checkpoint for end_date=2026-09-27;
- update actual V4/S03/V5 progress only from that output;
- do not retune.

2026-09-28:
- run the result-blind day-strength shadow after the immutable formal artifact exists;
- frozen first reference remains 0.93817204.

### Approval boundaries unchanged
Still explicit approval required for:
- fallback Cron 08:25 -> 08:20;
- F-count live read/capture/persistence/schedule;
- Production DB writes/schema;
- Production model/selector/threshold/candidate/stake changes;
- LINE real-send;
- purchase activation.

`V5_TARGET_20261015 / CORE_GATES_V4_20_S03_100 / OPTIONAL_LAYERS_NONBLOCKING / COMBINED_V5_PROGRESS_MAIN / PROD_V4_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 21:55 JST

### Combined checkpoint repaired and end-to-end proven
- main: `e14821db4c82bd7ed66cd8314a323095224366c8`
- #434 merged: repaired malformed combined manual workflow + added YAML structural CI
- #435 one-off E2E audit: PASS, closed unmerged as evidence-only
- Railway dispatcher deployment `174b2317-85d5-4f98-a2c7-93cc144f165e`: SUCCESS
- Railway staged changes: none
- pending work: none
- fallback Cron remains `25 23 * * *` UTC = 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

### Important repair
A malformed #431 insertion had left the main combined manual workflow duplicated/truncated.

Impact:
- manual research checkpoint workflow only;
- no Production cron/model/selector/purchase behavior was affected;
- no broken manual run was used as evidence.

#434 restored one clean workflow and strengthened CI to:
- parse YAML with PyYAML;
- require every critical step exactly once;
- enforce order:
  terminal readiness -> V4 settlement -> S03 checkpoint -> combined scorecard;
- require each PASS sentinel exactly once.

Current workflow:
`.github/workflows/research-forward-combined-checkpoint-manual.yml`

### Canonical E2E audit — #435
Run:
- workflow run `36320499779`
- job `108623282063`
- fixed known-completed target: 2026-09-26
- result: `PASS_READ_ONLY`

Readiness:
- races 156
- official 156
- void 0
- pending 0
- missing 0
- READY=true

V4 formal exact parity:
- resolved formal days: 6
- official races: 32
- predicted-head accuracy: 20/32 = 62.5%
- TOP2: 64 bets / 10 hits
- investment 6,400 JPY
- return 10,970 JPY
- profit +4,570 JPY
- ROI **171.4062%**
- next review: 10 resolved days
- remaining: 4

S03_M2 exact parity:
- evaluated 53
- invalid 1
- pending 0
- hits 4
- investment 5,300 JPY
- return 10,120 JPY
- profit +4,820 JPY
- ROI **190.9434%**
- max DD 1,600 JPY
- max losing streak 16
- first-half ROI 319.6154%
- second-half ROI 67.0370%
- bootstrap P(ROI>100%) 86.13%
- next review: 100 evaluated
- remaining: 47

Combined gates:
- V4 = COLLECTING / current 6 / next 10 / remaining 4
- S03 = COLLECTING / current 53 / next 100 / remaining 47
- promotion_allowed=false
- production_change=false

### Tonight / next operational step
Natural Production nightly results:
- Cron 23:30 JST
- recent full completion around 23:38..23:42

After ~23:45 JST:
- run the repaired combined manual checkpoint with `end_date=2026-09-27`;
- terminal readiness is authoritative and fails closed if loading is incomplete;
- use actual output only;
- do not retune from one new day.

### 2026-09-28 day-strength
Main-integrated #432 remains ready:
`.github/workflows/research-v4-day-strength-shadow-manual.yml`

Frozen first reference:
- **0.93817204**

No result/DB access; shadow label only; formal action unchanged.

### Approval boundaries unchanged
Explicit approval still required for:
- fallback Cron 08:25 -> 08:20
- F-count live read/capture/persistence/schedule
- Production DB writes/schema
- Production model/selector/threshold/candidate/stake changes
- LINE real-send
- purchase activation

`COMBINED_WORKFLOW_REPAIRED / YAML_STRUCTURAL_CI_GREEN / E2E_PASS_READ_ONLY / V4_6_TO_10 / S03_53_TO_100 / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 21:36 JST

### Post-nightly and next-day Forward operations are now main-integrated
- main: `c0e0c4336150a85f76d8abe00ac640247b5a2ba8`
- #429: combined manual V4 + S03 checkpoint — merged
- #431: result-day terminal readiness guard — merged
- #432: future-only V4 day-strength shadow tooling/manual workflow — merged
- #411: closed as superseded by #432; original preregistration preserved
- Railway dispatcher latest deployment: SUCCESS
- staged changes: none
- pending work: none
- fallback Cron remains 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

### Tonight: combined Forward refresh
Preferred workflow:
`.github/workflows/research-forward-combined-checkpoint-manual.yml`

For `end_date=2026-09-27` it now:
1. freezes provider inventory before any result access;
2. requires all 2026-09-27 races to be terminal via #431 readiness guard;
3. if not terminal, fails closed before V4/S03 counts advance;
4. settles immutable V4 artifacts read-only;
5. evaluates frozen S03_M2 read-only;
6. computes the existing review-gate status locally.

Terminal readiness definition:
- OFFICIAL = official/official + valid trifecta + positive payout
- VOID = cancelled/cancelled
- missing/no_result_page/partial/unknown = NOT_READY_FAIL_CLOSED

Validation:
- known completed 2026-09-26 = 156/156 terminal, READY.

Nightly Production results remain:
- Cron 23:30 JST
- recent starts 23:30:14..23:34:01
- recent completion around 23:38..23:42

Operationally, use the combined checkpoint after ~23:45 JST; the DB readiness guard is authoritative and will still fail closed if loading is incomplete.

Current pre-nightly gates:
- V4 formal: 6 resolved days; 4 remaining to 10-day review
- S03_M2: 53 evaluated; 47 remaining to 100-review

### Tomorrow 2026-09-28: future-only day-strength shadow
Main workflow:
`.github/workflows/research-v4-day-strength-shadow-manual.yml`

Contract:
- manual `workflow_dispatch` only
- no schedule
- no Railway/DB/result/payout/odds access
- provider-selected immutable FORMAL_AVAILABLE artifacts only
- archive SHA256 verified
- target date must be >=2026-09-28
- `day_strength = mean(formal TOP6 race_score)`
- reference = median immediately prior 7 FORMAL_AVAILABLE strengths
- KEEP_SHADOW iff target >= reference, else SKIP_SHADOW
- unavailable days never reconstructed
- formal action unchanged
- promotion false

Frozen first target reference, independently reproduced in #432 CI:
- 2026-09-21: 0.93817204
- 2026-09-22: 0.92814371
- 2026-09-23: 0.95483871
- 2026-09-24: 0.94166667
- 2026-09-25: 0.96153846
- 2026-09-26: 0.90618279
- 2026-09-27: 0.91720430
- **2026-09-28 reference = 0.93817204**

The 9/28 shadow may be classified as soon as its valid immutable formal artifact exists; it does not need race results.

First descriptive day-strength review remains:
- >=10 future resolved formal days
- >=3 KEEP
- >=3 SKIP

No shadow label can alter formal TOP6/TOP2 without a separate explicit Production proposal/approval.

### Approval boundaries unchanged
Still explicit approval required for:
- fallback Cron 08:25 -> 08:20
- F-count live read/capture/persistence/schedule
- Production DB writes/schema
- Production model/selector/threshold/candidate/stake changes
- LINE real-send
- purchase activation

`POST_NIGHTLY_COMBINED_MAIN / RESULT_READY_GUARD_MAIN / DAY_STRENGTH_MAIN / 928_REFERENCE_0_93817204 / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 21:25 JST

### Combined Forward checkpoint is integrated on main
- main: `c9d9731cd0c96929aee671987eb5c97ea26e9d4e`
- #425 merged: manual provider-selected V4 checkpoint
- #426 merged: manual S03_M2 checkpoint
- #427 merged: frozen review-gate helper
- #429 merged: combined manual Forward checkpoint
- Production model/selector/TOP6/TOP2/stake unchanged
- fallback Cron remains 08:25 JST
- `purchase_action=false`

Primary operational entry point:
`.github/workflows/research-forward-combined-checkpoint-manual.yml`

The combined checkpoint is:
- `workflow_dispatch` only;
- no schedule;
- optional `end_date=YYYY-MM-DD`;
- V4 provider inventory/hash freeze occurs before result access;
- V4 settlement uses PostgreSQL READ ONLY;
- S03_M2 uses the frozen rule and PostgreSQL READ ONLY;
- review-gate status is computed locally after both reports;
- no promotion / DB write / Railway config mutation / LINE / BUY / Production change.

Current pre-9/27-settlement baseline:
- V4 formal resolved days: 6 -> 4 remaining to 10-day review
- S03_M2 evaluated: 53 -> 47 remaining to 100-review
- day-strength future evidence: 0; begins 2026-09-28

Nightly result timing remains:
- `cron-nightly-results`: 23:30 JST
- recent Stage 1 starts: 23:30:14..23:34:01
- recent full pipeline completion: approximately 23:38..23:42
- operational checkpoint refresh target: after 23:45 JST

After natural 2026-09-27 result completion:
1. run the combined manual checkpoint with `end_date=2026-09-27`;
2. read actual V4/S03 outputs and review-gate counts;
3. do not retune from the single added day;
4. preserve 2026-09-28+ day-strength shadow as future-only evidence.

Evidence provenance:
- #409 remains the V4 formal historical/prospective evidence PR;
- #405 remains the S03_M2 evidence PR;
- operational refresh should now use main-integrated #429 rather than rebuilding ad hoc checkpoint branches.

Still explicit-approval only:
- fallback 08:25 -> 08:20 Cron activation
- F-count live read/capture/persistence/schedule
- Production model/selector/threshold/stake changes
- LINE real-send / purchase

`COMBINED_MANUAL_CHECKPOINT_MAIN / V4_6_TO_10 / S03_53_TO_100 / WAIT_927_NIGHTLY / REFRESH_AFTER_2345 / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 21:18 JST

### Manual Forward checkpoint infrastructure is ready on main
- main: `d33460822cecf7bc6f92b68b8ba153343da57bad`
- #425 merged: manual provider-selected V4 Forward checkpoint
- #426 merged: manual S03_M2 Forward checkpoint
- #427 merged: pure frozen review-gate status helper
- Railway dispatcher deployment `7d6c5fdb-33aa-4112-878e-0940a108d3cf`: SUCCESS
- Railway staged changes: none
- pending work: none
- fallback Cron remains `25 23 * * *` UTC = 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

### #425 — manual provider-selected V4 checkpoint
Main workflow:
`.github/workflows/research-v4-provider-selected-forward-checkpoint-manual.yml`

Contract:
- `workflow_dispatch` only
- no `schedule`
- optional `end_date=YYYY-MM-DD`
- enumerate provider runs before result access
- frozen arbiter selects only FORMAL_AVAILABLE artifacts
- selected artifact archives are SHA256-verified
- only after freeze, PostgreSQL result query opens in READ ONLY transaction
- unavailable dates are never reconstructed
- no odds / DB write / Railway config mutation / LINE / BUY / Production change

Current pre-2026-09-27-settlement baseline:
- resolved formal days: **6**
- next frozen review gate: **10**
- remaining: **4**

The 2026-09-27 formal artifact exists but must not count as resolved until official settlement is naturally available.

### #426 — manual S03_M2 checkpoint
Main workflow:
`.github/workflows/research-s03-m2-forward-checkpoint-manual.yml`

Contract:
- `workflow_dispatch` only
- no `schedule`
- optional `end_date=YYYY-MM-DD`
- frozen `S03_M2_POSITIVE_V1`
- exact Motor2 score / `score > 0`
- strict stored `snapshot_at < deadline_at`
- common Forward economics
- `invalid_result` remains void / zero investment
- no retune / DB write / Railway mutation / LINE / BUY / Production change

Current baseline:
- evaluated: **53**
- full review gate: **100**
- remaining: **47**

### #427 — frozen review-gate helper
Main:
- `research/forward_review_gates.py`
- `docs/FORWARD_REVIEW_GATES_20260927.md`

Mirrors existing gates only:
- V4 formal: 10 / 20 / 30 resolved FORMAL_AVAILABLE days
- S03_M2: 100 evaluated observations
- day-strength: >=10 future resolved formal days and >=3 KEEP / >=3 SKIP

It has no I/O and no promotion authority.

### Nightly result timing / next safe refresh
Production `cron-nightly-results`:
- Cron: `30 14 * * *` UTC = **23:30 JST**
- latest service deployment: SUCCESS

Observed Stage 1 starts:
- 2026-09-23: 23:34:01 JST
- 2026-09-24: 23:30:14 JST
- 2026-09-25: 23:30:55 JST
- 2026-09-26: 23:30:20 JST

Recent full nightly pipelines completed around **23:38..23:42 JST**.

Therefore:
- do not treat 9/27 results as ready before the nightly pipeline;
- a manual #425/#426 refresh **after 23:45 JST** is operationally separated from recent completion times;
- this is not a new schedule and does not authorize automation.

### Immediate next evidence actions
After natural 2026-09-27 nightly result completion:
1. run the main manual V4 provider-selected checkpoint with `end_date=2026-09-27`;
2. run the main manual S03_M2 checkpoint with `end_date=2026-09-27`;
3. update review-gate counts from actual output only;
4. do not retune from one new day;
5. on 2026-09-28, classify the future-only day-strength shadow from the immutable target artifact.

Still explicit-approval only:
- fallback Cron 08:25 -> 08:20
- F-count live read/capture/persistence/schedule
- Production model/selector/threshold/stake changes
- LINE real-send / purchase

Current gate:
`MANUAL_V4_CHECKPOINT_MAIN / MANUAL_S03_CHECKPOINT_MAIN / REVIEW_GATES_MAIN / WAIT_NATURAL_927_RESULTS / REFRESH_AFTER_2345 / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 20:12 JST

### Common Forward economics is now integrated on main
- main: `19cb1f0cff51509bbb39346b499af33f7280ecf7`
- #422 merged: pure common Forward economics module/tests/contract/CI
- #423 merged: read-only validation suite for N02/S03 semantics, formal V4 TOP2, and S03_M2
- old stacked #415/#416/#419/#420 closed as superseded; evidence preserved
- Production model/selector/TOP6/TOP2/stake unchanged
- Railway staged changes: none
- pending work: none
- fallback Cron remains 08:25 JST
- `purchase_action=false`

Common exact checkpoints remain:
- formal V4 TOP2: 32 evaluated / 4 void / ROI 171.4062% / +4,570 JPY / DD 2,200 / max losing 11
- S03_M2: 53 evaluated / 1 invalid / 8 pending / ROI 190.9434% / +4,820 JPY / DD 1,600 / max losing 16
- common denominator treats invalid/cancelled as void, never as a losing 100 JPY bet

Main references:
- `research/forward_economics.py`
- `docs/FORWARD_ECONOMICS_COMMON_CONTRACT_20260927.md`
- `docs/RESEARCH_PR_REGISTRY_20260927.md`
- `docs/FORWARD_EVIDENCE_FAILURE_RUNBOOK_20260927.md`

Next evidence work remains unchanged:
1. refresh formal V4 only after natural 2026-09-27 result availability;
2. classify 2026-09-28 day-strength shadow from the immutable target artifact;
3. continue S03_M2 frozen to 100 evaluated observations;
4. no 08:20 Cron activation or F-count live activation without explicit approval.

`COMMON_ECON_MAIN_INTEGRATED / VALIDATION_SUITE_MAIN_INTEGRATED / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 20:03 JST

**共通Forward評価の最新確定。これより下の古い評価定義・件数は履歴。**

### Source of Truth / Production
- GitHub main: `2e89e81f00b02a66c7a99ac0f6b02e2d43bf406b`
- Railway Production staged changes: none
- pending work: none
- fallback Cron remains `25 23 * * *` UTC = 08:25 JST
- Production V4 model / selector / TOP6 / TOP2 / stake unchanged
- `purchase_action=false`

### Common economics contract — #415
All CI SUCCESS.

One settlement definition now covers prospective evidence:
- `evaluated`: investment-bearing official settlement
- `invalid_result`: void / zero investment
- pending/other: zero investment
- common ROI / profit / largest-hit share / max DD / max losing streak / halves / day-bootstrap
- immutable formal V4 `official` rows normalize into the same contract

### Exact Production-data parity — #416
Canonical run `36313916909`.

S03 all-row 2026-09-13..09-27:
- rows 116
- evaluated 102
- invalid 2
- pending 12
- legacy metrics == common metrics exactly
- legacy risk == common risk exactly

This proves reporting semantics only, not a candidate promotion.

### Formal V4 TOP2 common parity — #419
Canonical run `36314249617`.

Exact immutable formal evidence 2026-09-21..09-26:
- frozen races 36
- evaluated/official 32
- void/invalid 4
- hits 10
- investment 6,400 JPY
- return 10,970 JPY
- profit **+4,570 JPY**
- ROI **171.4062%**
- largest-hit share 32.7256%

Common observation-level risk:
- max DD **2,200 JPY**
- max losing streak **11**
- first 16 evaluated races ROI **203.4375%**
- second 16 evaluated races ROI **139.3750%**
- whole-day bootstrap P(ROI>100%) **89.13%**

Result: `PASS_EXACT_V4_TOP2`.

### S03_M2 common parity — #420
Canonical run `36314384084`.

Exact frozen M2-positive evidence 2026-09-13..09-27:
- source S03 116
- timing rejected 0
- missing Motor2 0
- positive rows 62
- evaluated 53
- invalid 1
- pending 8
- hits 4
- investment 5,300 JPY
- return 10,120 JPY
- profit **+4,820 JPY**
- ROI **190.9434%**
- largest-hit share 44.3676%

Common risk:
- max DD **1,600 JPY**
- max losing streak **16**
- first 26 ROI **319.6154%**
- second 27 ROI **67.0370%**
- whole-day bootstrap P(ROI>100%) **86.13%**

Result: `PASS_EXACT_FROZEN_SUBSET`.

### Standardized interpretation
Do not rank/promote from these small checkpoints.

Facts under the same definitions:
- V4 TOP2 has lower current ROI than S03_M2 but both chronological halves remain >100%.
- S03_M2 has higher current overall ROI, but its second half is <100%.
- V4 has lower largest-hit concentration, shorter max losing streak, and slightly higher bootstrap P(ROI>100%) at the current checkpoint.
- S03_M2 has lower max DD in yen at the current checkpoint.
- samples/exposure differ; neither comparison authorizes selector/stake changes.

Continue frozen evidence collection:
- V4 formal: next review 10 resolved formal days
- S03_M2: next full review 100 officially evaluated observations

### Main references
- `docs/RESEARCH_PR_REGISTRY_20260927.md`
- `docs/FORWARD_EVIDENCE_FAILURE_RUNBOOK_20260927.md`

Current gate:
`COMMON_ECON_EXACT_V4_AND_S03_PARITY / V4_TOP2_32_EVAL_ROI_171_41 / S03_M2_53_EVAL_ROI_190_94_RECENT_WEAKNESS / NO_RETUNE / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 19:53 JST

**評価基盤・研究PR整理の最新追記。これより下の古い評価定義・PR優先度は履歴。**

### Source of Truth
- main: `809f47ec618a29b2f6b356173b286ec70181777d`
- Production staged changes: none
- Production pending work: none
- fallback Cron: `25 23 * * *` UTC = 08:25 JST
- Production model/selector/TOP6/TOP2/stake unchanged
- `purchase_action=false`

### Common Forward economics — #415
Draft #415 defines one pure economic contract:
- `evaluation_status=evaluated`: investment-bearing settlement
- `evaluation_status=invalid_result`: void / zero investment
- other: pending / zero investment
- common ROI / profit / largest-hit share / DD / losing streak / halves / daily/monthly / bootstrap
- immutable V4 `official` rows can be normalized into the same semantics
- no I/O / promotion / Production behavior

All #415 CI SUCCESS.

### Production-data parity — #416
Read-only exact parity passed.

Canonical parity run:
- `36313916909`

S03 2026-09-13..09-27 all-row coverage:
- rows 116
- evaluated 102
- invalid_result 2
- pending 12
- legacy vs common metrics: exact match
- legacy vs common risk: exact match

This validates settlement/report semantics only; it is not the S03_M2 economic subset result.

### Research PR registry
Main now contains:
- `docs/RESEARCH_PR_REGISTRY_20260927.md`

Reading priority:
- ROI decision: #409 / #405 / #411
- common economics: #415 / #416
- operational timing prep: #412
- F-count chain: #397 / #398 / #400 / #413
- correction/deprioritized: #406 / #407 / #408
- old #376..#393: historical/reference unless explicitly reactivated

Do not mass-close historical Drafts while stacked dependencies/evidence provenance remain useful.

### Failure runbook
New docs:
- `docs/FORWARD_EVIDENCE_FAILURE_RUNBOOK_20260927.md`

Frozen handling:
- missing formal capture = unavailable, never reconstructed
- pending results = zero investment until official
- invalid/cancelled = void, not a loss
- F-count companion failure cannot invalidate formal V4
- day-strength missing artifact = no label
- unexpected non-Cron Railway config change = stop
- no discrepancy is resolved by outcome-driven threshold tuning

Current gate:
`COMMON_ECON_SEMANTICS_GREEN / S03_REAL_DATA_PARITY_GREEN / PR_REGISTRY_ACTIVE / FAILURE_RUNBOOK_FROZEN / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 19:10 JST

**Forward準備の最新追記。これより下の古い件数・時刻・候補は履歴。再開時はmain/open PR/CI/Railway Productionをread-onlyで再取得する。**

### Source of Truth / Production
- GitHub main: `a50afa2f166da498b25f03f09383be14ab78b044`
- Railway Production staged changes: none
- pending work: none
- fallback dispatcher current Cron: `25 23 * * *` UTC = 08:25 JST
- Production V4 model / selector / TOP6 / TOP2 / stake: unchanged
- `purchase_action=false`
- F-count live read/capture/persistence/schedule: **not approved / not started**

### PR #411 — future-only V4 day-strength shadow
Draft head: `832ed2c252b8a7cc13efe22ceea5965e0658a76a`
All CI: SUCCESS.

Frozen from target date **2026-09-28 onward**:
- artifact-native `race_score` only
- `day_strength = mean(race_score of formal TOP6)`
- reference = median of immediately prior 7 `FORMAL_AVAILABLE` day strengths
- `KEEP_SHADOW` iff current >= reference, otherwise `SKIP_SHADOW`
- unavailable dates stay unavailable
- 2026-09-21..09-27 outcomes are not retrospective evidence for the gate
- first review requires >=10 future resolved formal days, >=3 KEEP, >=3 SKIP
- no schedule/persistence/Production action in the Draft

This is a **shadow label only**. Formal TOP6/TOP2 remains unchanged.

### PR #412 — V4 fallback timing margin
Draft head: `a673dcc4f2880d963239e9837444b566995e819d`
All CI: SUCCESS.

Frozen evidence 2026-09-23..09-27:
- current 08:25 schedule produced narrowest completion-to-feed headroom ~80.604s
- observed schedule/dispatch latency is nontrivial

Frozen candidate criteria:
1. >=5m after 08:15 source cutoff
2. >=4m after nominal 08:16 primary
3. >=5m projected worst feed headroom under all five observed latencies

Candidate comparison:
- 08:18: spacing criteria fail
- **08:20: only candidate passing all criteria**
- projected worst feed headroom at 08:20: ~380.604s (~6m21s)
- 08:22: projected worst headroom criterion fail
- 08:25: projected worst headroom criterion fail

Preferred **separate-approval candidate**:
`20 23 * * *` UTC = **08:20 JST**

Important:
- Railway Cron is still `25 23 * * *`
- no timing change has been applied
- actual Cron change requires explicit user approval

### PR #413 — current formal artifact × F-count compatibility
Stacked on #400.
Draft head: `05ad45599738257eabc926d3cde6494a9784f246`
All CI: SUCCESS.

Exact formal source:
- 2026-09-27 formal run `36279479671`
- artifact `10918742073`
- formal core SHA256 `8907e2443a172d7938395145824497479f3f3bf23d3170943973545adc47f8d3`

Synthetic-only compatibility proof:
- exact 36 synthetic `race_id/lane/f_count` rows
- exact formal six races / lanes 1..6
- #400 adapter + #398 companion contract PASS
- formal canonical-core hash before == after
- synthetic companion SHA256 `0812a3fba760dd31db09609dc5682a99c24469a5ee9d35229cb7ed0e9fdff6a9`
- DB read/result/odds/payout = 0
- DB write/persistence/Production/BUY = 0

Synthetic values are **not evidence**.

Conclusion:
- current formal V4 artifact shape is technically compatible with the frozen F-count companion design;
- actual prospective F-count read/capture/persistence remains an explicit approval gate.

### Immediate safe priorities
1. After 2026-09-27 results are naturally loaded, refresh #409 provider-selected formal settlement; do not reconstruct.
2. From 2026-09-28 onward, preserve artifacts needed for #411 future-only shadow evaluation; do not change formal actions.
3. Continue S03 frozen evidence toward 100 officially evaluated observations.
4. Do not apply 08:20 fallback Cron without explicit approval.
5. Do not activate F-count live capture/persistence without explicit approval.

Current gate:
`V4_TOP2_FORWARD_ACTIVE_EVIDENCE / DAY_STRENGTH_SHADOW_PREREG_GREEN / FALLBACK_0820_DESIGN_GREEN_NOT_APPLIED / FCOUNT_CURRENT_ARTIFACT_COMPAT_GREEN_LIVE_NOT_APPROVED / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 18:36 JST

**回収率改善研究の最新状態。これより下の古いROI・件数・PR headは履歴。再開時はGitHub main / open PR / CI / Railway Productionをread-onlyで再取得する。**

### Production / main
- GitHub main: `1d40d83b4cb0a2ecbf21a8555ea06d23a7ca1d6f`
- #401 non-enumerating prospective-freeze route: activated
- Railway Production staged changes: none
- Production pending work: none
- Production model / selector / threshold / candidate / stake: unchanged
- automatic purchase disabled / `purchase_action=false`
- F-count live companion capture/persistence/schedule: not approved / not started

### ROI research — current strongest prospective evidence

#### A. Formal V4 immutable artifact Forward — Draft #409
Provider-wide artifact inventory scanned 60 prospective-freeze workflow runs and 10 formal artifact copies.

Frozen arbiter result:
- 2026-09-16..09-20: `UNAVAILABLE_NO_VALID_CAPTURE`
- 2026-09-21..09-27: `FORMAL_AVAILABLE`
- unavailable days remain unavailable; do not reconstruct from historical DB state

Canonical provider-selected checkpoint:
- run `36309872048`
- artifact `10928339152`
- artifact digest `sha256:5b1dddef797da2b3f899c3f115bc265849051b378ce5cf0135cb166e2f538870`
- artifact-set mode: `FROZEN_PROVIDER_INVENTORY`

Economically resolved through 2026-09-26:
- formal days: 6
- official races: 32
- void/cancelled races: 4
- predicted-head accuracy: 20/32 = 62.5%

Formal TOP2:
- bets: 64
- hits: 10
- investment: 6,400 JPY
- return: 10,970 JPY
- profit: **+4,570 JPY**
- ROI: **171.4062%**
- profitable formal days: 3/6

Robustness:
- first 3 formal days ROI: 191.0714%
- second 3 formal days ROI: 156.1111%
- largest-hit share: 32.7256%
- leave-one-hit-out minimum ROI: 119.0323%
- leave-one-day-out worst remaining ROI: 125.1923%
- whole-day bootstrap 20,000 samples:
  - median ROI 171.4062%
  - 95% interval [58.0%, 281.1765%]
  - P(ROI > 100%) 89.13%

Ticket-order attribution is descriptive only:
- order 1: 32 bets / 4 hits / ROI 80.3125% / -630 JPY
- order 2: 32 bets / 6 hits / ROI 262.5000% / +5,200 JPY
- **do not** create a ticket2-only policy from this six-day checkpoint
- frozen Production/formal contract remains TOP2

Dynamic provider-selected checkpoint path now exists in Draft #409:
inventory/arbitration -> selected-artifact hash validation -> freeze -> only then read official results.
This removes manual artifact-ID selection from future 10/20/30-day refreshes.

2026-09-27 formal artifact exists but results were still pending at this checkpoint. Do not synthesize/guess same-day results.

Next formal V4 review gates are frozen at 10 / 20 / 30 economically resolved formal days. No rule change before those reviews.

#### B. S03_M2_POSITIVE_V1 prospective Forward — Draft #405
Strict current prospective period: 2026-09-13..09-27.

Integrity:
- source S03 rows: 116
- pre-deadline rows: 116/116
- frozen-rule hard errors: 0
- raw metadata errors: 0
- settlement errors: 0
- classification: `CONTRACT_CLEAN`
- two all-S03 rows were expected `invalid_result`; invalid/cancelled rows are not charged as bets

Frozen Motor2-positive track:
- positive rows: 62
- positive invalid_result rows: 1
- officially evaluated: **53**
- hits: 4
- investment: 5,300 JPY
- return: 10,120 JPY
- profit: **+4,820 JPY**
- ROI: **190.9434%**
- largest-hit share: 44.3676%
- max drawdown: 1,600 JPY
- max losing streak: 16
- day-bootstrap P(ROI > 100%): 86.13%

Descriptive stability:
- first 26 observations ROI: 319.6154%
- second 27 observations ROI: **67.0370%**
- remove any one winning observation: minimum ROI 108.2692%
- remove any one active date: worst remaining ROI 119.7872%
- profitable active days: 4/14

Interpretation:
- prospective evidence remains economically positive;
- second-half deterioration is material;
- continue exact frozen rule to 100 officially evaluated observations;
- 47 more officially evaluated observations remain from the 53 checkpoint;
- no beta/threshold/subgroup/date/venue retune before 100.

#### Historical S03 correction — Draft #406
Old pre-freeze ~126% ROI must not be used as promotion support.

Original 2026-08-14..09-12 window after strict evaluation-status handling:
- timing-valid M2-positive: 76 evaluated / 1 hit
- ROI 26.1842%
- profit -5,610 JPY

All-available pre-freeze strict timing-safe:
- 102 evaluated / 1 hit
- ROI 19.5098%
- bootstrap P(ROI > 100%) 0.02%

Decision:
`HISTORICAL_S03_PROFITABILITY_SUPPORT_REJECTED`.
Only prospective 2026-09-13+ evidence remains valid.

### Deprioritized tracks
- #408 S02_FORWARD_V1:
  - 43 evaluated / 1 hit
  - ROI 16.7442%
  - profit -3,580 JPY
  - P(ROI > 100%) 0.01%
  - do not widen gates to rescue it
- #407 GUARD05:
  - 825 rows / 768 evaluated
  - affected_evaluated = 0
  - GUARD05 == FULL on all evaluated rows
  - do not loosen threshold 5 / PRIOR_DAY to manufacture affected cases

### Current research priority
1. preserve and extend immutable formal V4 TOP2 evidence to 10 resolved formal days;
2. preserve S03_M2_POSITIVE_V1 unchanged to 100 officially evaluated observations;
3. keep historical S03 profitability rejected;
4. avoid new same-history ROI filters while these two genuine prospective tracks mature;
5. F-count remains preparation-only until separately approved.

### Current gate
`V4_FORMAL_TOP2_6_DAYS_ROI_171.41 / S03_M2_53_FORWARD_ROI_190.94_BUT_SECOND_HALF_67.04 / HISTORICAL_S03_REJECTED / S02_DEPRIORITIZED / GUARD05_NO_AFFECTED / NO_RETUNE / FCOUNT_LIVE_NOT_APPROVED / PROD_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 17:22 JST

**PR #401 の承認済み live-route activation 後の最新状態。これより下の古いSHA・PR状態・Railway状態は履歴。再開時は必ず GitHub main / open PR / CI / Railway Production を read-only で再取得する。**

### Source of Truth / Production
- repo: `kenshoushouri-cloud/boat-ai-v2`
- GitHub main: `db8ab21270ea5bc8fd6872bed576d4ba196c43e8`
- main は承認済み PR #401「Research: remove Railway variable enumeration from V4 freeze」の merge commit
- Railway project: `boat-v2-postgres`
- Production environment staged changes: **none**
- Production pending work after merge-triggered redeploy: **none**
- `candidate-discovery-v4-fallback-dispatcher`
  - Cron: `25 23 * * *` UTC
  - latest deployment: `e7c51f36-3e5b-4f4d-85a3-7e872ec453c7`
  - commit: `db8ab21270ea5bc8fd6872bed576d4ba196c43e8`
  - status: **SUCCESS**
- Production model / coefficient / selector / threshold / candidate / stake: unchanged
- automatic purchase disabled / `purchase_action=false`

### PR #401 activation result
PR #401 is now merged and live on `main`.

The active `.github/workflows/candidate-discovery-v4-prospective-freeze.yml` now:
- contains **no** `railway variable list`;
- contains **no** local `railway-vars.json` variable dump;
- uses fixed project `268a5b17-0712-440a-884d-27f7fa887a2d`;
- uses environment `production`;
- uses service `postgres-recovery`;
- injects DB access through `railway run`;
- maps `DATABASE_PUBLIC_URL -> DATABASE_URL` only inside the child process.

Unchanged:
- schedule `16 23 * * *` UTC;
- 08:15 JST source cutoff;
- current V4 model / selector / tickets;
- availability guard;
- artifact contract / retention;
- result/payout reads remain blocked;
- `purchase_action=false`.

No Railway Variable/Cron/service/volume/migration change was made for #401 activation.

### Current formal V4 capture health
Natural GitHub scheduled runs for target dates 2026-09-23 through 2026-09-27 were FAILURE because GitHub schedule delivery occurred too late on recent days.

Latest example:
- scheduled run `36285417940` for 2026-09-27
- started around 10:24 JST
- earliest frozen-feed deadline: 08:32 JST
- availability capture rejected late start
- formal prospective freeze rejected completion after earliest frozen-feed deadline
- fail-closed behavior worked as designed

The independent Railway fallback is currently carrying the formal natural capture:
- 2026-09-27 dispatcher log: `DISPATCH_FALLBACK`
- workflow_dispatch run `36279479671`: SUCCESS
- formal freeze started `08:29:29 JST`
- completed `08:29:31 JST`
- earliest feed deadline `08:32:00 JST`
- `CANDIDATE_V4_PROSPECTIVE_EVIDENCE_ELIGIBLE=true`
- `CANDIDATE_V4_PROSPECTIVE_RESULT=PASS_PRE_RESULT_FREEZE`
- availability guard: `PASS_ACTIVE_CORE`
- canonical-core SHA256:
  `8907e2443a172d7938395145824497479f3f3bf23d3170943973545adc47f8d3`
- immutable prospective artifact uploaded
- `purchase_action=false`

Recent workflow_dispatch formal freezes for 2026-09-23..2026-09-27 were all SUCCESS.

Operational note:
- completion-to-earliest-feed-deadline headroom across those five fallback runs was approximately **81 seconds to 15m13s**;
- 2026-09-24, 09-26 and 09-27 had only about **85s / 81s / 148s** headroom;
- therefore the current 08:25 JST fallback is working, but timing margin can be narrow.

Any fallback Cron change still requires separate explicit approval.

### F-count research boundary remains unchanged
- #397 prospective diagnostic: no live capture/persistence
- #398 hash-bound companion contract: no live capture/persistence
- #400 exact-36-row pure adapter: no I/O/persistence
- F-count live companion capture/persistence/schedule has **not** been approved or started
- no historical F-count backfill or coefficient search
- formal V4 core remains immutable

### Current gate
`PR401_LIVE_ROUTE_ACTIVATED / NON_ENUMERATING_DB_ROUTE_ON_MAIN / DISPATCHER_SUCCESS / PRIMARY_GITHUB_SCHEDULE_LATE_RECENTLY / FALLBACK_FORMAL_CAPTURE_HEALTHY_BUT_HEADROOM_TIGHT / FCOUNT_LIVE_CAPTURE_NOT_APPROVED / PRODUCTION_MODEL_UNCHANGED / PURCHASE_FALSE`

### Safe next action without further Production approval
- observe the next natural formal V4 run and confirm the newly merged non-enumerating route executes successfully;
- continue read-only health checks and CI/docs evidence;
- do not change fallback Cron timing;
- do not start F-count companion persistence;
- do not change Production model/selector/threshold/candidate/stake/purchase behavior.

## LATEST OVERRIDE — 2026-09-27 16:52 JST

**このsectionを最新の引き継ぎ情報として扱うこと。これより下の古いSHA・PR状態・Railway状態・次アクションは履歴。再開時は必ずGitHub main / open PR / CI / Railway Productionをread-onlyで再取得する。**

### Source of Truth / Production
- repo: `kenshoushouri-cloud/boat-ai-v2`
- GitHub main: `e3272d23841aa1d3ce5459ba68841e48cddcf16f`
- mainはdocs-only PR #402「Docs: refresh Boat handoff through PR #401」のmerge commit
- Railway project: `boat-v2-postgres`
- Production environment staged changes: **none**
- `candidate-discovery-v4-fallback-dispatcher`
  - Cron: `25 23 * * *` UTC
  - latest deployment: `85791bd2-dc70-4aa5-a6ae-aee7790d33de`
  - commit: `e3272d23841aa1d3ce5459ba68841e48cddcf16f`
  - status: **SUCCESS**
- main Production Cron群（data-prepare / final-check / nightly-results / window morning/day/night）latest known deployment: SUCCESS
- Production model / coefficient / selector / threshold / candidate / stake: unchanged
- automatic purchase disabled / `purchase_action=false`

### Current V4 production contract
- Course coefficient `0.50`
- Opponent Pressure coefficient `1.0` first-place-only
- Motor2 beta `0.06`
- probability temperature `2.20`
- daily structural selector: `head_p1 / head_margin / top3_mass / concentration`
- core: TOP6 races / formal TOP2 tickets
- odds / EV are not used by the main selector
- missing Course/Opponent/Motor is neutral
- formal V4 core evidence must remain immutable

### Recent evidence chain
#### PR #394 — recent_form readiness
- canonical run `36300918133` SUCCESS
- artifact `10925970218`
- canonical-period entry rows: **413,820**
- non-empty `recent_form`: **0**
- strong source-capture timestamp: none
- conclusion: `NOT_READY_FAIL_CLOSED`
- do not reconstruct historical recent_form after outcomes

#### PR #395 — unused entry inventory
- canonical run `36301606766` SUCCESS
- artifact `10926285564`
- exact-six races: **68,970**
- unused numeric entry fields broadly present
- F/L full-six coverage: 100%
- branch/origin coverage: 6.59%
- historical row-level 08:15 capture timestamp: not proven

#### PR #396 — result-blind input novelty
- canonical run `36302265912` SUCCESS
- artifact `10926306186`
- result JSON SHA256 `bf7ef418a2d0568cec17fd2af6c52eca329e68b7adbf72dd1c88730218f33b48`
- F count:
  - full-six 100%
  - within-race variation 57.0741%
  - F>0 rows 15.0826%
  - shape gate PASS
- L count:
  - within-race variation 0.8221%
  - positive rows 0.1382%
  - shape gate FAIL
- no outcome/odds/payout read
- no historical F-count coefficient search authorized

#### PR #397 — prospective F-count head-error diagnostic
- Draft
- head `844d0f4961367e21213f99579678fd1e20bd7937`
- pure contract/tests/docs only
- final contract CI SUCCESS
- frozen question: current V4 predicted head with `F>=1` vs `F=0` head accuracy
- minimum interpretation gate:
  - >=200 finalized core races
  - >=30 F-positive predicted heads
  - >=100 F-zero predicted heads
- future coefficient experiment can only be preregistered separately if:
  - F-zero head accuracy exceeds F-positive by >=5.0pt
  - same direction in >=3/4 chronological quarters
- no collection/persistence/coefficient/Production change
- current PR may show mergeable=false because main advanced by docs-only merges; rebase before any future merge

#### PR #398 — hash-bound F-count companion artifact
- Draft
- head `f55403cfa33e9ad6fc27d69872927711c4856af0`
- pure in-memory contract/tests/docs only
- all CI SUCCESS
- F-count evidence is a **separate companion artifact**
- companion binds to formal V4 canonical-core SHA256
- exact same six core race IDs / daily ranks / predicted heads
- capture must be target-day, >=08:15 JST, >=formal freeze, and before every core deadline
- exactly six non-negative integer F counts per race
- tests prove research metadata does not alter formal V4 canonical-core hash
- no capture/upload/persistence/schedule/coefficient
- current PR may show mergeable=false because main advanced by docs-only merges; rebase before any future merge

#### PR #400 — pure F-count companion row adapter
- stacked Draft on #398
- head `5d0c0481658bfe16f2660d2fbd491845a0753469`
- base: `research/v4-fcount-companion-contract-20260927`
- mergeable=true at latest check
- all 5 CI workflows SUCCESS:
  - V4 F-count companion adapter validation
  - Production shadow isolation
  - Critical mojibake guard
  - Critical Python syntax
  - V21 parser sanity
- pure adapter only; **no I/O / no persistence**
- requires exact 36 rows: `race_id/lane/f_count`
- exact formal six races and lanes 1..6
- duplicate/missing/extra/outcome-like rows fail closed
- non-integer or negative F counts fail closed
- formal canonical-core SHA256 verified unchanged before/after
- future approved DB read is frozen narrowly as:
  `select race_id,lane,f_count from v2_race_entries where race_id=any(%s) order by race_id,lane`
- query string is contract only; PR #400 does not execute it

#### PR #401 — remove Railway variable enumeration from V4 freeze
- Draft / **not merged**
- head `787a0bc4554c1cf6bac4a36b77105d300dd9a9e4`
- proposed safety hardening for the existing scheduled V4 prospective-freeze route
- removes Railway variable enumeration / local variable JSON
- uses non-enumerating `railway run` against fixed `postgres-recovery`
- schedule `16 23 * * *` UTC unchanged
- 08:15 cutoff / V4 model / selector / tickets / availability guard unchanged
- all CI SUCCESS, including Candidate Discovery V4 Prospective Freeze PR safety job
- live freeze job was **SKIPPED** on PR event
- no live route activation occurred
- current PR may show mergeable=false because main advanced by docs-only #402; rebase required before any future merge
- do **not** merge from a generic `進めて下さい`

### Current prospective source timing
- `cron-data-prepare` runs at `30 21 * * *` UTC = 06:30 JST
- current daily preparation obtains BOAT RACE official `racelist` entry data with result collection disabled in that path
- F count is therefore technically available for a **new future pre-result capture**
- this does **not** retroactively prove historical rows were available by 08:15 JST

### Explicit approval boundary
No live F-count capture/persistence has been started.

Explicit approval is required before any of the following:
1. merge/activation of a live Forward-route change such as #401;
2. F-count companion capture/persistence/scheduling;
3. creation/write of a Forward table or persistent artifact stream;
4. future settled F-count result evaluation using newly persisted snapshots;
5. Production model/coefficient/threshold/candidate/stake changes;
6. Railway Production Variables/Cron/service/volume/migration changes;
7. Production DB INSERT/UPDATE/DELETE/schema/VACUUM;
8. new LINE real-send behavior or automatic purchase.

Until approval:
- do not run historical F-count coefficient searches;
- do not backfill F-count snapshots after outcomes;
- do not modify formal V4 selector/rank/tickets;
- do not merge #397/#398/#400/#401 as Production-effect work;
- do not enable live F-count persistence.

### Safe next action without approval
- read-only audit of current formal V4 prospective-freeze health / recent natural captures;
- re-read current main/open PR/CI/Railway before any work;
- docs/handoff/CI/evidence cleanup;
- prepare a **non-executing** capture/persistence implementation Draft if needed, but do not activate it.

Safe state:
`FCOUNT_ACTIVATION_PREP_COMPLETE / RECENT_FORM_REJECTED / F_COUNT_SHAPE_READY / PROSPECTIVE_DIAGNOSTIC_PREREGISTERED / COMPANION_HASH_CONTRACT_GREEN / PURE_ROW_ADAPTER_GREEN / NON_ENUMERATING_ROUTE_DRAFT_GREEN / LIVE_CAPTURE_NOT_APPROVED / PRODUCTION_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 POST-PR401

**このsectionを最新の引き継ぎ情報として扱うこと。下の古いoverrideは履歴。再開時は必ずlive再取得する。**

### Live source / Production
- GitHub main at latest read-only check: `a255aa3a5d17cef953685f801b447ca6c80db28a` (docs-only PR #399 merge)
- Railway Production staged changes: none
- V4 fallback dispatcher latest deployment: SUCCESS
- dispatcher Cron: `25 23 * * *` UTC
- Production model / selector / threshold / candidate / stake unchanged
- `purchase_action=false`

### F-count evidence chain
- #394: `recent_form` empty in all 413,820 canonical-period entry rows -> reject / fail closed.
- #395: unused numeric entry fields broadly present; no strong historical row-level 08:15 capture timestamp.
- #396 canonical input-only audit:
  - F count full-six 100%
  - within-race variation 57.0741%
  - F>0 rows 15.0826%
  - L count within-race variation only 0.8221%
  - no outcomes read
- #397: prospective F-count head-error diagnostic preregistered; pure contract CI SUCCESS; no collection/persistence.
- #398: separate hash-bound F-count companion artifact contract; all CI SUCCESS; formal V4 canonical core remains immutable.
- #400: stacked pure row adapter on #398; all CI SUCCESS.
  - exact 36 `race_id/lane/f_count` rows only
  - exact formal six races / lanes 1..6
  - duplicates/extra races/missing lanes/non-integer or negative F counts rejected
  - outcome-like row fields rejected
  - formal canonical-core SHA256 verified unchanged before/after
  - no DB/network/file I/O and no persistence
- #401: existing formal V4 prospective-freeze DB-route hardening Draft; all CI SUCCESS.
  - proposed removal of Railway variable enumeration
  - proposed non-enumerating `railway run` route against fixed `postgres-recovery`
  - schedule `16 23 * * *` UTC unchanged
  - 08:15 cutoff / model / selector / tickets / availability guard unchanged
  - PR safety job SUCCESS; live freeze job SKIPPED on PR event
  - **not merged** because it changes the live scheduled Forward evidence route

### Current approval boundary
No F-count live capture has been started.

Explicit approval is still required before:
1. merging/activating a live Forward-route change such as #401;
2. adding or enabling F-count companion capture/persistence/scheduling;
3. writing a Forward table/artifact stream;
4. using future F-count snapshots for settled result evaluation.

Until approval:
- do not run historical F-count coefficient searches;
- do not alter formal V4 selector/rank/tickets;
- do not merge #401 solely from a generic "進めて下さい";
- do not enable F-count persistence.

Safe completed state:
`FCOUNT_INPUT_READY / PROSPECTIVE_DIAGNOSTIC_PREREGISTERED / COMPANION_HASH_CONTRACT_GREEN / PURE_ROW_ADAPTER_GREEN / NON_ENUMERATING_ROUTE_DRAFT_GREEN / LIVE_FCOUNT_CAPTURE_NOT_APPROVED / PRODUCTION_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 16:24 JST

**このsectionを最新の引き継ぎ情報として扱うこと。下の古いoverrideは履歴。再開時は必ずlive再取得する。**

### Live source / Production
- GitHub main at latest read-only check: `dac9314f17035c424f5455ff604432150a276e13` (docs-only PR #393 merge)
- Railway Production staged changes: none
- V4 fallback dispatcher: SUCCESS, Cron `25 23 * * *` UTC
- Production model / selector / threshold / candidate / stake unchanged
- `purchase_action=false`

### PR #394 — recent_form readiness
Canonical run `36300918133`, artifact `10925970218`.
- 413,820 canonical-period entry rows
- non-empty `recent_form`: 0
- strong capture timestamp: none
- conclusion: `NOT_READY_FAIL_CLOSED`
Do not reconstruct historical recent_form after outcomes.

### PR #395 — unused entry inventory
Canonical run `36301606766`, artifact `10926285564`.
- 68,970 exact-six races
- unused numeric fields generally ~97.8%–100% full-six coverage
- F/L counts full-six 100%
- branch/origin only 6.59%
- no strong historical row-level 08:15 capture timestamp
Conclusion: data exists, historical timestamp proof does not.

### PR #396 — input-only novelty
Canonical run `36302265912`, artifact `10926306186`, JSON SHA256 `bf7ef418a2d0568cec17fd2af6c52eca329e68b7adbf72dd1c88730218f33b48`.
- F count: full-six 100%, within-race variation 57.0741%, F>0 rows 15.0826% — shape gate PASS
- L count: variation 0.8221%, positive rows 0.1382% — shape gate FAIL
- fixed pair Pearson correlations all below preregistered |r|=0.95 redundancy line
- no outcomes read
Conclusion:
`F_COUNT_INPUT_SHAPE_READY / L_COUNT_TOO_DEGENERATE / HISTORICAL_0815_TIMING_STILL_UNPROVEN / NO_HISTORICAL_COEFFICIENT_SEARCH / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

### Current prospective source timing
- `cron-data-prepare` runs around 06:30 JST and executes daily pre-result data preparation.
- current code forces results collection off in that path and obtains official race-card entries from BOAT RACE `racelist`.
- F count is therefore technically available for a new future pre-result freeze before the current V4 08:15 boundary, subject to per-run integrity checks.
- this does not retroactively prove old DB rows were captured by 08:15.

### PR #397 — F-count prospective diagnostic DESIGN ONLY
Draft / mergeable / final contract CI SUCCESS.
- head `844d0f4961367e21213f99579678fd1e20bd7937`
- no collector / no schedule / no persistence
- no coefficient
- frozen question: does current V4 head accuracy materially worsen when predicted head has F>=1?
- primary population: unchanged V4 six core races
- minimum interpretation gate: 200 finalized core races, >=30 F-positive predicted heads, >=100 F-zero
- future coefficient preregistration only if F-zero head accuracy exceeds F-positive by >=5.0pt and direction agrees in >=3/4 chronological quarters
- passing diagnostic would still not authorize Production promotion

### PR #398 — hash-bound F-count companion artifact DESIGN ONLY
Draft / mergeable / all CI SUCCESS.
- head `f55403cfa33e9ad6fc27d69872927711c4856af0`
- pure in-memory contract only; no DB/network/Railway access
- F-count evidence stays in a separate companion artifact rather than modifying formal V4 evidence
- companion binds to the existing formal V4 canonical-core SHA256
- exact six race IDs / daily ranks / predicted heads must match the formal V4 freeze
- capture timing contract: target day, >=08:15 JST, >=formal freeze time, and < every core deadline
- exactly six non-negative integer F counts per race
- tests prove research-only metadata does not alter the formal V4 canonical-core hash
- no capture / no upload / no persistence / no schedule / no coefficient

Frozen gate:
`FCOUNT_COMPANION_HASH_BOUND / FORMAL_V4_CORE_IMMUTABLE / PURE_CONTRACT_GREEN / NO_CAPTURE / NO_PERSISTENCE / EXPLICIT_APPROVAL_REQUIRED_FOR_ACTIVATION / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

### Current approval boundary
**Next scientific step requires explicit approval** because it would activate prospective Forward persistence/collection for F-count snapshots.
Until approval:
- do not schedule F-count collection;
- do not write a new Forward table/artifact stream;
- do not run historical F-count coefficient searches;
- do not merge a Production-effect model change.

Safe completed state:
`RECENT_FORM_REJECTED_EMPTY / UNUSED_ENTRY_INVENTORY_COMPLETE / F_COUNT_NEXT_PROSPECTIVE_DIAGNOSTIC_PREREGISTERED / ACTIVATION_NOT_APPROVED / PRODUCTION_UNCHANGED / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-27 15:30 JST

**このsectionを最新の引き継ぎ情報として扱うこと。これより下の古いSHA・研究途中状態・Railway状態・次アクションは歴史的背景として扱い、再開時は必ずlive再取得すること。**

### Source of Truth / Production
- repo: `kenshoushouri-cloud/boat-ai-v2`
- current main: `997b7cce30e1ce5c5a04905f9a22a95236930c6b`
- GitHub main = code Source of Truth
- Railway PostgreSQL = Production data Source of Truth
- Railway project: `boat-v2-postgres`
- Production environment latest read-only check: staged changes none
- `candidate-discovery-v4-fallback-dispatcher`: Cron `25 23 * * *` UTC, latest deployment SUCCESS
- main Production cron群（data-prepare / final-check / nightly-results / window morning/day/night）latest deployment SUCCESS
- Production model / coefficient / threshold / candidate / stake logic: unchanged
- automatic purchase disabled / `purchase_action=false`

### Current V4 contract
- Course coefficient `0.50`
- Opponent Pressure coefficient `1.0` first-place-only
- Motor2 beta `0.06`
- probability temperature `2.20`
- daily structural selector: `head_p1 / head_margin / top3_mass / concentration`
- core: TOP6 races / formal TOP2 tickets
- odds / EV not used by the main selector
- missing Course/Opponent/Motor is neutral
- no automatic purchase

### Completed evidence chain after the 2026-09-25 handoff
#### PR #387 — input-information ablation
Canonical one-shot:
- run `36098761397` SUCCESS
- artifact `10847994618`
- ZIP SHA256 `2a775d97c8ed4c1495f33772699bae6aa50234c83a51ff09c115ba7a7edd6368`
- JSON SHA256 `277927e9a9a66f12797168cf4c7af4bb91684ae84f5f4a6853e6f54e4447e779`
- no harmful existing layer removal supported
- fixed-race head accuracy unchanged by every removal
- no_course / no_motor / base_only worsen proper scores
- no_opponent does not pass the fixed-race harmful-layer criterion
- conclusion: existing-input removal is not the next path; missing first-place information is the next hypothesis

#### PR #389 — strict-prior official ST
Canonical run `36254658202`, artifact `10910380430`.
Blocks 3-10 fixed current-V4 daily-rank-1:
- head accuracy 57.558% -> 57.558%
- LogLoss 1.340703 -> 1.339431
- Brier 0.655212 -> 0.654967
- head classification changed 0/344
Full reselection worsened head accuracy / LogLoss / Brier.
Conclusion: tiny calibration-only movement; not a missing head-classification signal. Do not promote.

#### PR #390 — actual course-movement error attribution
Canonical run `36255242556`, artifact `10910461830`.
Complete-course daily-rank-1 rows blocks 3-10: n=306.
- any course change n=76, head 57.895%
- no course change n=230, head 55.652%
- predicted-head moved n=19, head 42.105%, but small/unstable
Conclusion: broad course movement is not the dominant head-error concentration. Do not create a broad course-change filter from this history.

#### PR #391 — frozen Exhibition ST Forward health
Canonical run `36288188460`, artifact `10921021546`.
- n=1,879
- trifecta proper scores slightly worse overall
- first-place proper scores slightly worse overall
- venue signs heterogeneous
Conclusion: frozen beta=-0.02 Exhibition ST is not supported for promotion; no subgroup salvage.

#### PR #392 — current-V4 exhibition-time-rank chronological OOS
Canonical run:
- trigger head `6d5986f7889a8bb89cc0d32a95b2b1f50492bc0c`
- run `36288864737` SUCCESS
- artifact `10921393420`
- artifact ZIP SHA256 `8ddca8ff36a89452620a3a3e780ec959e8edfcc01f697f474145fbb98a92d33e`
- result JSON SHA256 `99f4d32e2bbbddaa698767d434ed37e57b43d290752d72d92b3897bd4d915498`
- read-only route: Railway non-enumerating local env injection
- secret enumeration 0 / collector execution 0 / Production change 0

Frozen coefficients were `0 / 0.05 / 0.10 / 0.20`; prior-block training selected 0.20 in all evaluation blocks 3-10. **Do not expand this grid after seeing the result.**

Track A, fixed control rank1, blocks 3-10:
- control: head 57.558%, LogLoss 1.340703, Brier 0.655212, ROI 75.131%
- exhibition time: head 57.558%, LogLoss 1.314880, Brier 0.643763, ROI 77.689%
- predicted head changed 0/344
- primary head-accuracy improvement gate FAILED

Track B full reselection:
- head 62.464%, LogLoss 1.278669, Brier 0.624626
- rank1 overlap 52.770%, mean Top6 overlap 63.994%
- economics did not improve correspondingly

Frozen conclusion:
`CURRENT_V4_EXHIBITION_TIME_CALIBRATION_SIGNAL_SUPPORTED / FIXED_RACE_HEAD_CLASSIFICATION_CHANGED_0_OF_344 / PRIMARY_HEAD_ACCURACY_GATE_FAILED / TRACK_B_RESELECTION_DESCRIPTIVELY_BETTER_BUT_NOT_PROMOTION_AUTHORITY / DO_NOT_EXPAND_COEFFICIENT_GRID / NO_NEW_FORWARD_FROM_THIS_REPLAY / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

### Current research interpretation
The dominant bottleneck remains first-place classification. The following have **not** supplied a robust missing classification signal:
- removing current Course/Opponent/Motor layers
- strict-prior ST
- broad course-movement hypothesis
- frozen Exhibition ST
- exhibition-time-rank on the fixed current-V4 race

Do not retune these families on the same 2025-07-01..2026-09-22 history.

Historical note already established:
- real `boat_place2_rate` contributed only a very small incremental improvement compared with Motor2 in PR #186/#187/#188, so Boat2 is low priority.
- weather/wave/exhibition interaction research exists from earlier generations; do not duplicate it blindly without first checking timing compatibility with current V4.

### PR #394 — recent-form readiness audit completed
Canonical result-blind one-shot:
- trigger head `1fec3d9c0ade35c48634ca1220ebcd2b188bd8d7`
- run `36300918133` SUCCESS
- artifact `10925970218`
- artifact ZIP digest `sha256:3a2fcb827916be87facbb7b4ccb40200ce5c512b96136d9fe66ec6c7a52df107`
- result JSON SHA256 `11dd669a7af7da690e13fde312be4725cef3c9baee80ff221b2492915bc61a19`
- canonical-period `v2_race_entries`: 413,820 rows
- non-empty `recent_form`: 0 rows
- full-six races with six non-empty values: 0
- strong source-capture timestamp column: none
- outcome/result read: 0
- collector execution: 0
- secret enumeration: 0
- PostgreSQL READ ONLY

Frozen conclusion:
`RECENT_FORM_EMPTY_IN_CANONICAL_PERIOD / NO_NONEMPTY_COVERAGE / NO_STRONG_CAPTURE_TIMESTAMP / NOT_READY_FAIL_CLOSED / DO_NOT_DEFINE_TRANSFORMATION_OR_COEFFICIENT / NO_OUTCOME_READ / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

Do not backfill or reconstruct historical `recent_form` after outcomes merely to create a test set.

### NEXT SAFE ACTION — unused pre-race information inventory
Before defining another model family, audit current V4's already-available entry information without reading outcomes:
1. enumerate current `v2_race_entries` fields not already consumed by V4 base/Course/Opponent/Motor2;
2. measure canonical-period non-null/full-six coverage;
3. map each field to current-main writer/source provenance;
4. confirm target-day availability and 08:15 JST compatibility;
5. reject fields that are redundant, post-race mutable, or provenance-unclear before any coefficient is defined.

Initial static mapping shows V4 base already consumes racer class, national win rate, national place2 rate, local place2 rate and avg ST; Motor2 is separately used. Candidate inventory therefore starts from remaining official entry fields such as place3/local-win/boat-related and operational counters, without presuming predictive value.

### Open Draft handling
Highest-relevance current Drafts:
- #387 completed input ablation — canonical evidence frozen, no rerun
- #389 strict-prior ST — completed, no promotion
- #390 course-movement attribution — completed diagnostic
- #391 Exhibition ST Forward health — completed, no promotion
- #392 exhibition-time-rank OOS — completed; primary gate failed; no rerun / no grid expansion

Always refetch the full open PR list and exact-head CI before acting.

### Safety / approval boundary
May continue without confirmation:
- read-only audits
- historical backtest / Forward evaluation
- Draft PR create/update
- CI
- docs/handoff updates
- safe evidence collection

Explicit approval required:
- Production-effect PR merge
- Railway Production Variables / Cron / service / volume / migration changes
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Production model / coefficient / threshold / candidate / stake logic changes
- new LINE real-send behavior
- Forward persistence
- automatic purchase
- paid data / external inquiry

Never:
- reconstruct Forward/candidates after seeing outcomes
- expand #392 coefficient grid after seeing the upper-edge selection
- adopt Track-B-only descriptive gains when the preregistered primary gate failed
- loosen thresholds merely for volume/profit
- expose secrets or enumerate Railway plaintext variables
- delete data for capacity pressure without the approved storage contract

### Restart instruction
> Read this LATEST OVERRIDE first. Refetch current main/open PR/CI/Railway Production read-only. Treat #392 as completed canonical evidence and do not rerun it. The next safe research task is a result-blind coverage/provenance audit of stronger current-form information, beginning with `recent_form`; only after timing-safe readiness is proven may a new preregistered predictive test be defined.

## LATEST OVERRIDE — 2026-09-25 13:51 JST

**このsectionを最新の引き継ぎ情報として扱うこと。これより下・過去PR・過去SHAに残る古いfallback状態、日付、件数、判断は歴史的背景として扱い、現在値と仮定しないこと。**

再開時は必ず次の順でread-only再取得する。

1. GitHub `kenshoushouri-cloud/boat-ai-v2` の current `main`
2. open PR
3. relevant CI
4. Railway project `boat-v2-postgres` Production status
5. 必要ならProduction PostgreSQLのSELECT-only evidence

GitHub `main` をコードのSource of Truth、Railway PostgreSQLをProduction dataのSource of Truthとする。

### Current Boat main / Production

- Boat main: `903a55f5bcd4a6fe3bff6d39270e5b911878a83e`
- latest main message: PR #374 merge、V4 pre-freeze availability guard
- Railway Production environment: no staged changes at latest check
- `candidate-discovery-v4-fallback-dispatcher`: Cron `25 23 * * *` UTC、latest deployment SUCCESS
- main Production cron群（data-prepare/final-check/nightly-results/window morning/day/night）もlatest deployment SUCCESS
- automatic purchase: disabled / `purchase_action=false`
- Production model / coefficient / threshold / candidate logicは今回変更していない

### V4 current contract

Current research contract:

- `COURSE_COEF=0.50`
- `OPPONENT_COEF=1.0`
- `MOTOR_BETA=0.06`
- `PROB_TEMP=2.20`
- daily selector: `head_p1 / head_margin / top3_mass / concentration` のpercentile-rank平均
- current core: TOP6 races / formal TOP2 tickets
- odds / EVはmain selectorには使わない
- Course/Opponent/Motorは欠損時neutral
- no automatic purchase

### Immutable long-history evidence

Canonical long-history run:

- workflow run: `35851936772`
- artifact: `10745234979`
- ZIP: `v4-long-history-35851936772.zip`
- inner JSON SHA256: `4f814a4c5a89e7f014ca32a91ef9e477ce076ebd1527eeab306c96be5759b286`
- period: `2025-07-01..2026-09-22`
- evaluated: 432 exact-six days / 2,592 races
- result/payout read only after daily six + Top5 freeze
- no odds/EV selection
- 17 unevaluable days

Fixed point-count economics:

- 1pt ROI 67.488%, profit -84,270
- 2pt ROI 75.069%, profit -129,240
- 3pt ROI 75.554%, profit -190,090
- 4pt ROI 75.395%
- 5pt ROI 73.542%

No fixed point count is historically profitable.

Feature coverage in this long history:

- Motor: 97.762%
- Course any: 14.699%
- Course full6: 7.215%
- Opponent: 3.009%

Important: this long history is a fail-neutral replay of the current contract, not a fully populated modern Course/Opponent regime.

### Daily purchase-volume research

Draft PR #385:
`Research: preregister V4 daily 1-3 race count`

- head: `4b05572fe7bbd48b40330a9789ca142c1e42b584`
- base: current main
- Draft / mergeable / 5 CI SUCCESS
- fixed formal Top2, 100 yen/ticket
- no odds/EV/rerank/stake change

Historical one-time evaluation:

All 432 days:
- 1R/day: ROI 97.083%, profit -2,520
- 2R/day: ROI 76.811%, profit -40,070
- 3R/day: ROI 78.009%, profit -57,000
- current 6R/day: ROI 75.069%, profit -129,240
- adaptive 1-3R: ROI 90.468%, profit -14,870

Pure evaluation blocks 3-10:
- 1R/day: ROI 75.131%, profit -17,110
- 2R/day: ROI 67.195%, profit -45,140
- 3R/day: ROI 65.475%, profit -71,260
- 6R/day: ROI 69.748%, profit -124,880
- adaptive: ROI 71.773%, profit -29,130

Conclusion:
Reducing 6R -> 1R sharply reduces loss magnitude and drawdown, but simple daily-rank-1 is **not proven profitable**. Do not interpret all-period 97.08% as prospective profitability; early blocks contribute heavily.

### One-race structural selector

Draft PR #386:
`Research: preregister V4 daily one-race selector`

- head: `4bdd57d197b7e61f0c1c15b8e303a87df9b94d46`
- base: current main
- Draft / mergeable / 5 CI SUCCESS
- exactly 1R/day, formal 2 tickets
- only four Top5 structural contexts: `H1_P0/H1_P1/HM_P0/HM_P1`
- no odds/EV/venue/race#/date filter

One-time historical evaluation:
- fixed daily-rank-1 all-period ROI: 97.08%
- structural selector all-period ROI: 94.11%
- fixed daily-rank-1 blocks 3-10 ROI: 75.13%
- structural selector blocks 3-10 ROI: 71.40%

Conclusion:
The four-context economic selector FAILED to improve fixed daily-rank-1. Do not tune these contexts further on the same history.

### Rank1 head-error diagnosis

For daily-rank-1 in pure evaluation blocks 3-10 (344 days):

- formal Top2 hit: 74 / 344 = 21.5%
- first-place miss: 142 / 344 = 41.3%
- first correct, second miss: 70 / 344 = 20.3%
- first+second correct, third miss: 58 / 344 = 16.9%

Head-specific diagnosis:

- Top1 first-place correct: 198 / 344 = 57.6%
- Top2 first-place coverage: 202 / 344 = 58.7%
- second formal ticket adds a different-head rescue on only 4 days
- Top2 share same first-place head: 327 / 344 = 95.1%
- race_score AUC for head-correct vs head-miss: about 0.522

Interpretation:
The dominant bottleneck is first-place/head prediction. Current race_score does not meaningfully discriminate head correctness once daily-rank-1 is selected. Two tickets are also heavily concentrated on the same head.

Saved-feature coverage on this 344-race slice:
- Motor available: 334
- Course available: 64
- Opponent available: 13

Course/Opponent coverage is too sparse/time-confounded to infer causal value from the saved artifact alone.

### NEXT HIGHEST PRIORITY — input-information ablation

Draft PR #387:
`Research: preregister V4 input-information ablation`

- head: `0cb6b0192a58ed41f9f644ea73c9c43f20cc8b32`
- base: current main
- Draft / mergeable / 5 CI SUCCESS
- **preregistration only; long-history replay has NOT yet been run**

Frozen variants:
- `control`
- `no_course`
- `no_opponent`
- `no_motor`
- `base_only`

Frozen evaluation design:

Track A — fixed control race:
- freeze current V4 daily six + daily-rank-1 before result
- recompute all variants on the exact same rank1 race
- isolates prediction-layer effect
- primary: Top1 head accuracy, first-place multiclass logloss, first-place Brier
- secondary: formal Top2 hit rate, 2-point ROI/profit

Track B — full variant reselection:
- each variant independently rebuilds distributions before result
- unchanged `select_daily` chooses its own six/rank1
- measures prediction + selector interaction

Rules:
- same `2025-07-01..2026-09-22` period / 10 blocks
- main retrospective comparison = blocks 3-10
- same 08:15 JST source cutoff
- result only after all freezes
- no odds/EV
- no threshold search
- no coefficient retune
- no new feature
- PostgreSQL read-only
- no LINE / no Production change / `purchase_action=false`

**Next safe action:** implement/run #387's read-only replay exactly once using the already established non-enumerating read-only connection route from PR #378. Do not add variants after seeing results.

### Other research conclusions to preserve

- #382 economic Top5 pair reranker: FAIL
- #384 structural rank reranker: FAIL
- simple high-retention structural filters did not reach robust ROI 100%
- timing-safe market/EV research #381 did not produce a robust profitable policy; `PASSED_POLICIES=[]`
- conservative alpha025 tail blend showed a small historical Top2 improvement but ROI remained <100 and uncertainty crossed zero; do not promote
- #379/#380 overlap; resolve before any future promotion
- repeated post-hoc tuning on the same 2,592R is now a serious overfitting risk

### Information strategy

Current working hypothesis is now split cleanly:

1. harmful/noisy existing information may be lowering head quality; test this with #387 ablation first
2. if removals do not improve fixed-race proper scoring/accuracy, the next hypothesis is **missing first-place information**
3. only after #387 should new features such as exhibition ST / entry-course movement / weather-water conditions / stronger current-form signals be considered

Do not add new feature families before the ablation result.

### Production approval boundary

May continue without asking:
- read-only audits
- historical backtest / Forward evaluation
- Draft PR create/update
- CI
- docs/handoff updates
- safe evidence collection

Explicit approval required:
- Production-effect PR merge
- Railway Production Variables / Cron / service / volume / migration change
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Production model / coefficient / threshold / candidate / stake logic change
- new LINE actual-send behavior
- Forward persistence
- automatic purchase
- paid data / external inquiry

Never:
- loosen thresholds only to increase volume/profit
- reconstruct Forward/candidates after seeing results
- mix evidence regimes
- expose secrets
- use Railway plaintext variable enumeration
- capacity-driven deletion
- touch unrelated staged patches

### Parallel TOTO status — separate repo

TOTO is a separate system:
`kenshoushouri-cloud/toto-ai-v1`

At latest check:
- TOTO main: `f78494159ad0c2d4a670f9c908a6710a65767a76`
- PR #164 merged: `栃木シティ -> 栃木Ｃ` team alias fix
- `toto-ai-core` Production deployment: SUCCESS
- next Round 1656 natural cron/LINE result still needs confirmation
- TOTO Railway has one old STAGED patch on diagnostic service `diagnostic-round-1654-reader`; **do not touch it**
- TOTO and Boat DB / services / variables remain separate

---

## Restart instruction

> Read this LATEST OVERRIDE first. Then refetch current Boat main/open PR/CI/Railway Production read-only. Treat main as code Source of Truth and Railway PostgreSQL as Production data Source of Truth. Do not assume any SHA/count/status above is still current. If #387 remains current and CI-green, continue with exactly one read-only V4 input-ablation replay; do not tune the preregistered family after seeing results.
