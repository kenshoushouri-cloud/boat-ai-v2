# Next Chat Start Here — 2026-09-30 23:36 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初にGitHub repository
`kenshoushouri-cloud/boat-ai-v2`
を確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20260930_2336.md` を全文**
3. 必要なときだけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

古い `LIVE_HANDOFF_*` / `LATEST OVERRIDE` と矛盾する場合は、23:36 handoffを優先してください。ただしSHA・run・coverage・deploymentは現在値を必ず再取得してください。

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

タイムアウトが多いため、**一度に1〜2確認ずつ**進めてください。確認不要なread-only監査・Draft PR・CI・docs更新は継続し、Production-effect merge等の承認境界だけ止めてください。

## 最初にread-only確認するもの

1. current `main`
2. Issue #42 latest comments
3. open Draft PR、特に **#526**
4. GitHub Actions:
   - `36680306690`
   - `36667954064`
   - current beforeinfo pending runs
5. Railway fallback current deployment / Cron
6. **2026-09-30 23:30 nightly settlement**

## 固定目的・ルール

目的:
締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避け、再現性のあるプラス期待値を持つ競艇AIを構築し、安定運用を目指す。

V5 mandatory gates:
- V4 >= 20 resolved FORMAL_AVAILABLE days
- S03_M2 >= 100 officially evaluated observations
- evidence contract clean

historical reconstructionはprospective gateへ加算しない。

日次JST:
- 08:15 source cutoff
- 08:16 nominal GitHub schedule
- 08:20 Railway fallback
- 08:32 availability hard-stop
- deadline前 formal freeze
- 23:30 nightly settlement

**2026-09-29 formal V4は永久にUNAVAILABLE。修復・再構築・formal day加算禁止。**

`purchase_action=false` を維持。

## handoff時点の重要状態

handoff作成前main:
`4a03de44b8d2a54c79ba822775c465725509bf25`
（handoff docs commit後はmain SHAが進んでいるので必ず再取得）

merge済み:
- #523 Opponent Phase 3 quote bug fix
- #524 long Opponent campaign
- #525 beforeinfo short-chunk化

次の承認境界:
- **Draft #526**
- beforeinfo command/routing deconflict
- last verified: mergeable=true / CI 6/6 SUCCESS
- 明示承認なしにmergeしない
- #527はsupersededでclosed unmerged

Historical acquisition `36680306690`:
- 2026-02-14..2026-09-29
- old-head run
- Phase 2 residual fill 実行中
- Phase 3 pending
- #523修正はこのold-head runへ遡及しない
- terminal後に必要ならOpponentを2025-10-08からmissing-only recovery
- Phase 1/2を無駄に全再実行しない

Beforeinfo `36667954064`:
- segment 1 cancelled
- segment 2 in progress
- segment 3 queued
- current-main側にもpending duplicatesあり
- #526 merge後もrun IDを再取得してからcleanupする

latest historical readiness:
- races 70,026
- motor6 70,002
- course_proxy6 58,287
- opponent_replay 11,183
- complete_beforeinfo 8,290
- core_plus_beforeinfo 3,718 / 5.31%
- recent_form6 0
- full reconstructed core 9,911 / 14.15%

主な残ボトルネック:
Opponent / beforeinfo / recent_form

Prospective baseline:
- V4 8/20 through 9/28
- S03_M2 63/100 through 9/29
- 9/30 settlementはhandoffでは未確認なので、最新nightlyから更新する

## 承認境界

確認なしで可:
read-only監査、research/backtest/Forward、safe evidence、Draft PR、CI、docs、Issue/Actions/Railway read-only、既承認contract内fill-missing-only historical acquisition。

明示承認が必要:
Production model/prediction、selector/threshold/candidate logic、stake、real LINE behavior、purchase、Railway Production設定変更、承認contract外DB変更、Production-effect PR merge。

禁止:
9/29 formal修復、target-race outcome leakage、outcome-guided tuning、gate lowering、`purchase_action=true`、Railway plaintext variable列挙。

まずは **9/30 nightly settlement確認 → #526 current state確認 → 2本のhistorical run確認** の順で、一つずつ進めてください。

---

`READ_LIVE_HANDOFF_2336 / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`
