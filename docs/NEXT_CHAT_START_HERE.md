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

GitHub `main` = code Source of Truth、Railway PostgreSQL Production = data Source of Truth。SHA・run・coverage・deploymentは必ず再取得してください。タイムアウトが多いため、**一度に1〜2確認ずつ**進めてください。

最初の順番:
1. current main / Issue #42 / open Draft PR / Actions / Railway
2. **2026-09-30 23:30 nightly settlement**
3. #529 / #528 / #526 のcurrent差分とsupersession関係
4. `36667954064` とcurrent beforeinfo pending runs
5. cancelled acquisition `36680306690` の未完了範囲
6. current Opponent writer / Railway fallback deployment

固定ルール:
- 締切前情報だけで、結果漏洩・後知恵・過学習を避ける
- V5 gates = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 officially evaluated / evidence clean
- historical reconstructionはprospective gateへ加算しない
- **2026-09-29 formal V4は永久UNAVAILABLE。修復・formal day加算禁止**
- `purchase_action=false`
- 月間純利益+50,000円はedge確認後のscaling目標。selector/thresholdを緩める理由にしない

日次JST:
08:15 cutoff → 08:16 GitHub nominal → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 settlement。

最新確定prospective baseline:
- V4 8/20 through 9/28
- S03_M2 63/100 through 9/29
- 9/30 settlementは未確認。terminal evidenceまで加算しない

最新historical readiness:
- motor6 70,002
- opponent 11,183
- complete_beforeinfo 8,290
- core_plus_beforeinfo 3,718 / 5.31%
- recent_form6 0
- reconstructed core 9,911 / 14.15%

Historical重要点:
- `36680306690` = **completed/cancelled**
  - Phase 1 B-file 全8 chunk PASS
  - Phase 2 residual PASS確認は2026-05-17まで
  - 2026-05-18以降は未完了扱い
  - Phase 3 Opponent未完了
- Opponent PASSは2025-10-07まで。新規trigger前にactive/pending writerを再取得
- `36667954064`: segment 1 cancelled / segment 2 in progress / segment 3 queued
- beforeinfo pending duplicates `36716743130`, `36716742695`
- #529/#528/#526は同じduplicate-listener問題の代替Draft。**重複mergeしない。Production-effect mergeは明示承認を取る**

確認なしで可:
read-only監査、research/backtest/Forward、safe evidence、Draft PR、CI、docs、既承認contract内fill-missing-only historical acquisition。

禁止:
9/29 formal修復、target-race outcome leakage、outcome-guided tuning、gate lowering、`purchase_action=true`、Railway plaintext variable列挙。

`READ_LIVE_HANDOFF_2344_FINAL / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
