# Next Chat Start Here — 2026-09-30 23:53 JST

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

GitHub `main` = code Source of Truth、Railway PostgreSQL Production = data Source of Truthです。  
**SHA / run / coverage / deploymentは古い値を信用せず、作業前に必ず再取得してください。**

タイムアウト対策として、**一度に1〜2確認ずつ、一つ一つ進めてください。途中経過の長文報告は不要です。**  
read-only監査、research/backtest/Forward、safe evidence、Draft PR、CI、docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初の確認順:
1. current main / Issue #42 latest / open Draft PR / Actions / Railway
2. **2026-09-30 23:30 nightly settlement / combined checkpoint**
3. #529 / #528 / #526 のcurrent mainとの差分・supersession・CI
4. beforeinfo run `36667954064` / `36703692641` / pending `36716743130` / `36716742695`
5. writer laneを確認して、acquisition residual → Opponent → recent_formを重複なしで進める

固定目的:
締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避け、再現性のあるプラス期待値を持つ競艇AIを構築し、安定運用へ進める。

固定ルール:
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / evidence contract clean
- historical reconstructionはprospective gateへ加算しない
- 2026-09-29 formal V4は永久UNAVAILABLE。修復・再構築・formal day加算禁止
- `purchase_action=false`
- 月間純利益 +50,000円はedge確認後のscaling目標。利益目標でselector/thresholdを緩めない
- Production V4 model/selector/stake/LINE/purchaseは承認なしで変更しない
- target-race outcome leakage / outcome-guided tuningは禁止
- Railway plaintext variable値は列挙しない

日次JST:
08:15 cutoff → 08:16 nominal GitHub → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 nightly settlement → V4+S03 checkpoint。

最新確定baseline:
- V4 8/20 through 9/28、ROI 147.7273%、+4,200円
- S03_M2 63/100 through 9/29、ROI 160.6349%、+3,820円
- 9/30 formalはRailway fallbackで有効確認済みだが、settlementは未確認。terminal evidenceまで加算しない

Historical:
- acquisition `36680306690` = completed/cancelled。Phase1全PASS、Phase2は2026-05-17までPASS確認、以降不足。全再実行せず不足分だけfill-missing-onlyで回復
- Opponent PASS through 2025-10-07、`opponent_replay=11,183`、recovery起点は原則10/08
- beforeinfo old longはseg2 in_progress、legacy monthlyは2025-09 in_progress、pending duplicate 2本あり。duplicate listener未解消なので追加commandを盲目的に投稿しない
- readiness: motor6 70,002 / complete_beforeinfo 8,290 / core+beforeinfo 3,718 (5.31%) / recent_form6 0 / reconstructed core 9,911 (14.15%)

Open Draft:
- #529 = duplicate Issue listenerを外す最小案
- #528 = legacy command分離 + sentinel
- #526 = routing + shared writer lane + cleanup案
- 3案を同時mergeしない。current mainで再比較し、採用は1案だけ。Production-effect mergeは明示承認必須

まずは **9/30 settlement確認 → Draft整理 → historical run整理** の順で進めてください。

`READ_LIVE_HANDOFF_2351_FINAL_REFINED / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
