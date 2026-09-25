# boat-ai-v2 Project Handoff

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
