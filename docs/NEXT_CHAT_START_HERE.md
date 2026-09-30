# Next Chat Start Here — 2026-09-30 23:44 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20260930_2344.md` を全文**
3. 必要なときだけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

GitHub `main` = code Source of Truth。Railway PostgreSQL Production = data Source of Truth。SHA / run / coverage / deployment は古い値を信用せず、必ず再取得してください。

タイムアウトが多いため、**一度に1〜2確認ずつ、一つ一つ進めてください。** read-only監査・Draft PR・CI・docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初に順番どおり確認:
1. current main / Issue #42 latest / open Draft PR
2. **2026-09-30 23:30 nightly settlement / combined checkpoint**
3. #529 / #528 / #526 のcurrent差分とsupersession関係
4. run `36680306690` / `36667954064` のjob-level state
5. current Opponent / beforeinfo pending runs
6. Railway fallback latest deployment / Cron

固定目的:
締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避け、再現性のあるプラス期待値を持つ競艇AIを構築し、安定運用へ進める。

V5 mandatory gates:
- V4 >= 20 resolved `FORMAL_AVAILABLE` days
- S03_M2 >= 100 officially evaluated observations
- evidence contract clean

historical reconstructionはprospective gateへ加算しない。  
2026-09-29 formal V4は永久UNAVAILABLE。修復・再構築・formal day加算禁止。  
`purchase_action=false` を維持。  
月間純利益 +50,000円はedge確認後のscaling目標で、selector/thresholdを緩める理由にしない。

日次JST:
08:15 cutoff → 08:16 nominal GitHub → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 nightly settlement → V4+S03 checkpoint。

最新確定prospective baseline:
- V4 8/20 through 9/28、ROI 147.7273%、+4,200円
- S03_M2 63/100 through 9/29、ROI 160.6349%、+3,820円
- 9/30 settlementは未確認。terminal evidenceが出るまで加算しない

最新historical readiness:
- motor6 70,002
- opponent_replay 11,183
- complete_beforeinfo 8,290
- core_plus_beforeinfo 3,718 / 5.31%
- recent_form6 0
- reconstructed core 9,911 / 14.15%

Historical current facts:
- `36680306690` = **completed / cancelled**
  - Phase 1 B-file全8 chunk PASS
  - Phase 2は2026-02-14..2026-05-17までPASS確認
  - 2026-05-18以降は未完了扱い
  - Phase 3 OpponentはSKIPPED
  - 全campaign再実行は禁止。fill-missing-onlyで不足分だけ回復
- Opponent PASSは2025-10-07まで、recovery起点は原則2025-10-08。新規trigger前にwriter laneを再取得
- `36667954064` old beforeinfo run:
  - segment 1 cancelled
  - segment 2 in progress
  - segment 3 queued
- current-main pending beforeinfo duplicates:
  - `36716743130`
  - `36716742695`
- beforeinfo duplicate listenerは未解消。追加commandを盲目的に投稿しない

open Draft:
- #529 = duplicate beforeinfo Issue listenerを外す最新・最小案
- #528 = legacy command分離案
- #526 = routing/shared writer laneまで含む広い案
- 3本を同時・無検討でmergeしない。current mainとの差分を再取得し、Production-effect mergeは明示承認を取る
- #527はclosed unmerged / superseded

禁止:
9/29 formal修復、target-race outcome leakage、outcome-guided tuning、V5 gate lowering、`purchase_action=true`、Railway plaintext variable列挙。

まずは **9/30 nightly settlement確認 → Draft比較 → historical run整理** の順で、一つずつ進めてください。

`READ_LIVE_HANDOFF_2344_FINAL / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
