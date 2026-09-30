# Next Chat Start Here — 2026-09-30 17:06 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@Railway  
@GitHub

新競艇AI開発プロジェクトの続きです。

最初に GitHub repository

`kenshoushouri-cloud/boat-ai-v2`

の以下を最優先で確認してください。

1. **`docs/LIVE_HANDOFF_20260930_1706.md` — 最新の完全引き継ぎ。最優先で全文読む**
2. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
3. `docs/PROJECT_HANDOFF.md`
4. `docs/CURRENT_STATE.md`
5. `docs/NEXT_CHAT_START_HERE.md`

古い `LATEST OVERRIDE` や旧 `LIVE_HANDOFF_*` と内容が矛盾する場合は、**`LIVE_HANDOFF_20260930_1706.md` を優先**してください。

その後、必ずread-onlyで以下を再取得して、引き継ぎとの差分を確認してください。

- Issue #42 latest comments
- current `main`
- open PR / Draft PR
- CI / GitHub Actions
- Railway Production status / fallback service
- Production PostgreSQL evidence needed for the current task

GitHub `main` = code Source of Truth。  
Railway PostgreSQL Production = data Source of Truth。  
古いSHA、件数、Cron、workflow run、deployment、coverageを現在値と決めつけないでください。

## 目的

締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値を持つ競艇AIを構築し、実運用で安定収益を目指します。

目標:
- 2026-10-15前後にV5 core freeze / operational-readiness review
- 質優先で概ね1日1〜3レース、質がなければ0でも可
- 月間純利益 +50,000円はedge確認後のscaling目標
- 通知数や月収目標のためだけにselector/thresholdを緩めない
- `purchase_action=false`

## 日次JST

- 08:15 source cutoff
- 08:16 nominal GitHub schedule
- 08:20 Railway fallback
- 08:32 availability hard-stop
- race deadline前にformal freeze / companion evidence
- 23:30 nightly results / settlement
- nightly後にcombined V4 + S03 checkpoint

2026-09-29 formal V4は永久にUNAVAILABLEです。historical reconstructionで復活させないでください。

## V5 core gates

- V4 >= 20 resolved FORMAL_AVAILABLE days
- S03_M2 >= 100 officially evaluated observations
- evidence contract clean

gateを10/15のために緩めないでください。

引き継ぎ時点の最後のsettled baseline:
- V4 8/20、ROI 147.7273%、+4,200円
- S03_M2 63/100、ROI 160.6349%、+3,820円
- S03 second-half ROI 56.5625%

9/30はformal evidence自体は有効ですが、この引き継ぎ時点ではnightly settlement前です。23:30後に必ず最新settlementへ更新してください。

## 現在の重要作業

- Historical acquisition run `36667832406`
  - Phase 2 archived-racelist residual fill が実行中
  - 次が prior-only Opponent replay
  - 重複trigger禁止
- Historical beforeinfo long run `36667954064`
  - segment 1 `2025-07-01..2026-02-05` 実行中
  - segment 2/3 queued
  - 重複trigger禁止
- Railway `postgres-recovery` は直近read-only metricsで活動を確認済み
- Historical acquisition completion後にcoverage/readinessを再監査
- broad matched-contract economicsはcoverageの時間偏りが改善するまで急がない

## PR / branch

- #517 Draft: historical writer concurrency command-aware、CI green
- #519 Draft: beforeinfo long concurrency isolation、CI green
- 直前に最新mainから統合branchを作成済み:
  - `ops/command-aware-historical-concurrency-20260930-v2`
  - handoff時head `54d5aa8730abebc92f83ccecc8ed31900de882ad`
  - #517 + #519相当を3 workflowへ統合
  - **まだPR未作成**
  - current mainとの差分を再確認し、妥当ならDraft PR化→CI
  - Production workflow behaviorに関係するmergeは承認境界を守る

## 作業権限

確認なしで継続可:
- read-only監査
- research / historical backtest / Forward評価
- safe evidence collection
- Draft PR作成・更新
- CI
- docs / handoff更新
- Issue #42 / Actions / Railway read-only
- 既承認contract内のprovenance-safe / fill-missing-only historical acquisition

新しい明示承認が必要:
- Production model/prediction変更
- selector/threshold/candidate logic変更
- stake変更
- real LINE送信behavior変更
- purchase有効化
- Railway Production service/Cron/variables変更
- 承認contract外のProduction DB書換え/schema/VACUUM
- Production-effect PR merge

禁止:
- 9/29 formal dayの修復
- target-race result leakage
- outcome-guided coefficient/threshold探索
- gate lowering
- 通知数目的のthreshold緩和
- `purchase_action=true`
- Railway plaintext variable列挙

## 進め方

タイムアウトが頻発するため、**1〜2確認ずつ短く区切って進めてください。**
ユーザー確認が不要な範囲はそのまま継続し、承認が必要な操作だけ止めて確認してください。

まずは:
1. current main / run 36667832406 / run 36667954064 を再確認
2. 統合branch `ops/command-aware-historical-concurrency-20260930-v2` を再確認
3. 必要ならDraft PR化してCI
4. historical acquisitionを妨げず進行
5. 23:30後に9/30 settlementとcombined checkpointを更新

---

`READ_LIVE_HANDOFF_1706 / REFETCH_BEFORE_ACTION / SHORT_CHUNKS / V5_20261015 / MONTHLY_PLUS_50000 / PURCHASE_FALSE`
