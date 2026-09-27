# boat-ai-v2 Current State

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
