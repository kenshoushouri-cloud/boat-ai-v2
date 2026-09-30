# Next Chat Start Here — 2026-09-30 23:51 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20260930_2351.md` を全文**
3. 必要な場合だけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

GitHub `main` = code Source of Truth、Railway PostgreSQL Production = data Source of Truthです。古いSHA / run / coverage / deploymentを現在値と決めつけず、**行動前に必ず再取得**してください。

タイムアウトが多いため、**一度に1〜2確認ずつ、一つ一つ進めてください。** read-only監査・Draft PR・CI・docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初にこの順で確認してください:
1. current main / Issue #42 latest / open Draft PR
2. **2026-09-30 23:30 nightly settlement / V4+S03 combined checkpoint**
3. #529 / #528 / #526 のcurrent差分・supersession・CI。3本を重複mergeしない
4. beforeinfo: `36667954064`, `36703692641`, pending `36716743130`, `36716742695`
5. historical-production-write lane / Opponent active-pending
6. Railway fallback latest deployment / Cron

固定ルール:
- 目的は締切前情報だけで、結果漏洩・後知恵・過学習を避け、再現性あるプラス期待値を構築すること
- V5 gates = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 officially evaluated / evidence clean
- historical reconstructionはprospective gateへ加算しない
- **2026-09-29 formal V4は永久UNAVAILABLE。修復・再構築・formal day加算禁止**
- `purchase_action=false`
- 月間純利益 +50,000円はedge確認後のscaling目標。利益目標のためにselector/thresholdを緩めない

日次JST:
08:15 cutoff → 08:16 GitHub nominal → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 nightly settlement → V4+S03 checkpoint。

最新確定prospective baseline:
- V4 8/20 through 9/28、ROI 147.7273%、+4,200円
- S03_M2 63/100 through 9/29、ROI 160.6349%、+3,820円
- 9/30 settlementは未確認。terminal evidenceまで加算しない

Historical要点:
- `36680306690` = completed/cancelled。Phase 1全8 chunk PASS、Phase 2は5/17までPASS確認、5/18以降は未完了扱い、Phase 3 Opponent skipped
- 全campaignを再実行せず、fill-missing-onlyで不足分だけ回復
- Opponent PASS through 2025-10-07、latest count 11,183、recovery起点は原則10/08
- beforeinfo old long segment 2とlegacy monthly 2025-09が現在in_progress。さらにpending duplicate 2本が残る
- beforeinfo routing整理前に追加commandを盲目的に投稿しない
- recent_form6=0

Latest historical readiness:
- motor6 70,002
- opponent_replay 11,183
- complete_beforeinfo 8,290
- core_plus_beforeinfo 3,718 / 5.31%
- recent_form6 0
- reconstructed core 9,911 / 14.15%

open Draft:
- #529 = legacy `issue_comment` listener削除
- #528 = legacy command分離 + sentinel
- #526 = routing + shared writer lane + cleanup
- 現在はdocs-only main進行後なので、そのままmergeしない。current mainへ追随させ、差分とCIを再確認し、Production-effect mergeは明示承認を取る
- #527はclosed unmerged / superseded

禁止:
9/29 formal修復、target-race outcome leakage、outcome-guided tuning、V5 gate lowering、`purchase_action=true`、Railway plaintext variable列挙。

まずは **9/30 settlement確認 → beforeinfo Draft整理 → historical run整理** の順で、一つずつ進めてください。

`READ_LIVE_HANDOFF_2351_FINAL / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
