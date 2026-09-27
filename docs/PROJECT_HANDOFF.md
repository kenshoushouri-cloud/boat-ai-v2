# boat-ai-v2 Project Handoff

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

### NEXT SAFE ACTION — stronger current-form readiness, evidence only
Before defining another predictive feature, audit whether `v2_race_entries.recent_form` is actually usable:
1. coverage / non-empty rate in the canonical period;
2. exact structure and whether usable facts can be bound to the racer;
3. source/provenance;
4. whether every candidate fact is strictly known before the target race / 08:15 JST cutoff;
5. fail closed if chronology cannot be proven.

This next step is **coverage/provenance only**. Do not read outcomes to choose a recent-form transformation. Do not create coefficients until the readiness gate passes.

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
