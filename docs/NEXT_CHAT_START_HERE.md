# Next Chat Start Here — 2026-10-01 06:09 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読む順番:
1. `docs/HANDOFF_LATEST.md`
2. **`docs/LIVE_HANDOFF_20261001_0609.md` を全文**
3. 必要な場合だけ `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

GitHub `main` = code Source of Truth、Railway PostgreSQL Production = data Source of Truthです。  
**SHA / run / coverage / deploymentは古い値を信用せず、作業前に必ず再取得してください。**

タイムアウトが頻発するため、**一度に1〜2確認ずつ、一つ一つ進めてください。途中経過の長文表示は不要です。**  
read-only監査、research/backtest/Forward、safe evidence、Draft PR、CI、docs更新は確認不要で継続し、Production-effect merge等の承認境界だけ止めてください。

最初の順番:
1. current main / Issue #42 latest / open Draft / Actions / Railwayを再取得
2. **2026-10-01朝のprospective運用を最優先**。08:15 cutoff → 08:20 Railway fallback → 08:32 guardを守り、朝運用前にProduction変更しない
3. **2026-09-30 V4+S03 combined checkpointのterminal evidenceを確認**し、cleanならgateを更新
4. matched-readinessをread-only確認
5. #529 / #528 / #526をcurrent mainで比較し、**beforeinfo routingは1案だけ**採用。追加beforeinfo commandは禁止
6. beforeinfo active/pending runを確認
7. shared writer laneが空いてから、Opponent不足 `2025-12-03..2025-12-16` と `2026-04-29..2026-05-05` を重複なしで回復
8. residual不足 → recent_form → matched-contract backtestの順で進める

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
- Railway plaintext variable値は列挙しない / `list_variables`禁止

最新read-only readiness:
- races 70,026
- motor6 70,026
- opponent_replay 56,599
- complete_beforeinfo 14,547
- core_plus_beforeinfo 7,871 / 11.24%
- reconstructed full core 47,431 / 67.73%
- recent_form6 0
- historical値はprospective gateへ加算しない

`READ_LIVE_HANDOFF_20261001_0609 / REFETCH_BEFORE_ACTION / ONE_BY_ONE / TODAY_PROSPECTIVE_FIRST / V5_20261015 / PURCHASE_FALSE`

---
