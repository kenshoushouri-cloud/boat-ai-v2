# Next Chat Start Here — 2026-09-30 23:59 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20260930_2359.md` を全文**
3. 必要な場合だけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

GitHub `main` = code Source of Truth、Railway PostgreSQL Production = data Source of Truthです。  
**SHA / run / coverage / deploymentは古い値を信用せず、作業前に必ず再取得してください。**

タイムアウト対策として、**一度に1〜2確認ずつ、一つ一つ進めてください。途中経過の長文表示は不要です。**  
read-only監査、research/backtest/Forward、safe evidence、Draft PR、CI、docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初の順番:
1. current main / Issue #42 latest / open Draft / Actions / Railwayを再取得
2. **2026-09-30 V4+S03 combined checkpointのterminal evidenceを最優先確認**
3. matched-readinessをread-only再監査
4. #529 / #528 / #526をcurrent mainで比較し、**1案だけ**残す
5. beforeinfo `36667954064` / `36703692641` / pending `36716743130` / `36716742695` を確認。追加command禁止
6. shared writer laneとOpponent `36715551720` を確認
7. residual不足 → Opponent → recent_form を重複なしで進める

固定目的:
締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避け、再現性のあるプラス期待値を持つ競艇AIを構築し、安定運用へ進める。

固定ルール:
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / evidence contract clean
- historical reconstructionはprospective gateへ加算しない
- 2026-09-29 formal V4は永久UNAVAILABLE。修復・再構築・formal day加算禁止
- `purchase_action=false`
- 月間純利益 +50,000円はedge確認後のscaling目標。selector/thresholdを利益目標で緩めない
- Production V4 model/selector/stake/LINE/purchaseは承認なしで変更しない
- target-race outcome leakage / outcome-guided tuningは禁止
- Railway plaintext variable値は列挙しない

日次JST:
08:15 cutoff → 08:16 nominal GitHub → 08:20 Railway fallback → 08:32 hard-stop → deadline前formal freeze → 23:30 nightly → combined checkpoint。

9/30:
- formalはRailway fallbackで有効
- nightly resultsは23:39:45 JSTまでに完了確認
- combined checkpoint未確認なので、V4 8/20・S03 63/100のbaselineは勝手に更新しない

Historical:
- acquisition `36680306690` = cancelled。Phase1全PASS、Phase2は2026-05-17までPASS、以降不足。全再実行禁止
- Opponent PASS through 2025-10-07、last `opponent_replay=11,183`、recovery run `36715551720` queued
- beforeinfo old long seg2 in_progress、legacy 2025-09 in_progress、pending duplicate 2本あり。routing整理前に追加command禁止
- last audit: motor6 70,002 / complete_beforeinfo 8,290 / core+beforeinfo 3,718 (5.31%) / recent_form6 0 / reconstructed core 9,911 (14.15%)

Open Draft:
- #529 = legacy Issue listenerを外す最小案
- #528 = legacy command分離 + sentinel
- #526 = routing + shared writer lane + cleanup
- 3案同時merge禁止。current mainへ追従して比較し、1案だけ採用。Production-effect mergeは明示承認必須

`READ_LIVE_HANDOFF_2359 / REFETCH_BEFORE_ACTION / ONE_BY_ONE / V5_20261015 / PURCHASE_FALSE`

---
