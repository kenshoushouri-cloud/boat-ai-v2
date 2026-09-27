# boat-ai-v2 Project Handoff

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
