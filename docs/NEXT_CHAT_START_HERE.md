# Next Chat Start Here — 2026-09-30 23:44 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

GitHub repository `kenshoushouri-cloud/boat-ai-v2` を最初に確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20260930_2344.md` を全文**
3. 必要なときだけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

GitHub `main` = code Source of Truth。Railway PostgreSQL Production = data Source of Truth。古いSHA/run/coverage/deploymentを現在値と決めつけず、必ず再取得してください。

タイムアウトが多いため、**一度に1〜2確認ずつ、一つ一つ進めてください。** read-only監査・Draft PR・CI・docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初に:
1. current main / Issue #42 latest / open Draft PR
2. **2026-09-30 23:30 nightly settlement**
3. #529 / #528 / #526 のcurrent差分（重複merge禁止）
4. run `36680306690` と `36667954064` のjob-level state
5. current Opponent / beforeinfo pending runs
6. Railway fallback latest deployment / Cron

固定ルール:
- 目的は締切前情報だけで結果漏洩・後知恵・過学習を避け、再現性あるプラス期待値を構築すること
- V5 gates: V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 officially evaluated / evidence clean
- historical reconstructionはprospective gateへ加算しない
- 2026-09-29 formal V4は永久UNAVAILABLE。修復禁止
- `purchase_action=false`
- 月間純利益+50,000円はedge確認後のscaling目標で、selector/thresholdを緩める理由にしない

日次JST:
08:15 cutoff → 08:16 GitHub nominal → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 nightly settlement。

最新確定readiness:
- motor6 70,002
- opponent 11,183
- complete_beforeinfo 8,290
- core_plus_beforeinfo 3,718 / 5.31%
- recent_form6 0
- reconstructed core 9,911 / 14.15%

最新確定prospective baseline:
- V4 8/20 through 9/28
- S03_M2 63/100 through 9/29
- 9/30 settlementは未確認なので、最新nightly evidenceが出るまで加算しない

open Draftの最新論点:
- #529 = duplicate beforeinfo Issue listenerを外す最新・最小案、CI green
- #528 / #526 =同問題の旧代替案
- 3本を無検討でmergeしない。current mainとの差分を比較し、Production-effect mergeは明示承認を取る

Historical:
- `36680306690` はold-head acquisition。last verified Phase 2 in progress / Phase 3 pending
- Opponent PASSは2025-10-07まで。新規recovery前にcurrent writerを再取得
- `36667954064` はbeforeinfo old long run。last verified segment 2 in progress / segment 3 queued
- stale run IDを前提にcleanupしない

禁止:
9/29 formal修復、target-race outcome leakage、outcome-guided tuning、gate lowering、`purchase_action=true`、Railway plaintext variable列挙。

`READ_LIVE_HANDOFF_2344 / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
