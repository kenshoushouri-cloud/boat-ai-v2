# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261004_V5_BACKTEST_PREFLIGHT.md`

次チャットで読むのは3点だけ:
1. `docs/HANDOFF_LATEST.md`
2. 上記current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

Current: Production=V4 / V5=research-only / target=2026年10月中旬 / Railway<=USD20/month。
取得と採用は分離。精度向上featureのみ採用し、低コストで有用なpre-race情報は不採用でも収集継続。
Matched selectionは結果参照前に凍結済み: shared **70,164** / V4 **2,742** / V5 **1,522**、run `37185954388`。
Live gates: V4 **9/20** / S03_M2 **66/100** / evidence clean → **BLOCKED**。economics未実行。
V4 prospective-freeze修正済み: PR **#537** merged / candidate-v4 SoT参照 / safety全PASS。過去日のprospective再構築はしない。
S03は停止せず収集中で、positive+official条件により増加が遅い。
Recent Form readiness: **69,477/70,170=99.01%**、shared母集団 **69,471/70,164=99.01%**。same-day/future/bad-source/>5履歴すべて0、provenance clean。
Recent Form coefficient lock済み: **-0.50..+0.50 / 0.10刻み / 11候補**。TRAIN LogLossだけで1回選択し、VAL/OOSはfreeze後までblind。
Recent Form TRAIN fit: **coef +0.30** がLogLoss最良でfreeze。TRAINではLogLoss/Brier改善、mean rankは僅かに悪化。VAL/OOSは未読。
Recent Form blind result: **LogLoss/BrierはVAL/OOS両方改善したが、mean official-ticket rankが両方悪化**。事前gateに従い **不採用・収集継続**。
Exhibition Time readiness: **64,297/70,170=91.63%**。TRAIN 98.30%、VALIDATION 97.51%、OOS **67.60%**。unknown source=0、全て公式historical beforeinfo由来。
Exhibition Time OOS gap診断: Jul 98.93% / Aug 57.65% / Sep 44.93%。missing **4,703**。ZERO日が連続し、その後complete日が再出現。過去long campaignもcancelledしており、主因は**backfill未完/不連続**。
Exhibition Time min-cost plan: generic **12,424 HTTP**に対しtargeted **4,703 HTTP**（約62.15%削減）。Jul 53 / Aug 2,086 / Sep 2,564。DBは約4.67/5GBなので月別＋各回disk/WAL確認。
Exhibition-Time-only実装済み: PR **#544** merged / candidate-v4 target / weather・ST・tilt・course writeなし / July plan-only **53件・HTTP0・DB write0** / safety全PASS。
Jul pilot: target53/HTTP53/fetch失敗0だが、realtime parserでは展示parse **0行** → DB更新**0行**で安全停止。Jul coverageは53欠損のまま。post-check: DB 4,389,443,263B / WAL 83,886,080B / volume 4,670.824448/5,000MB。
Next ONE task: **Exhibition-Time-onlyをhistorical parser v3へ切替え、parse qualityをfail-closed化して安全テストのみ。再pilotはまだしない。**

`JULY_PILOT_SAFE_ZERO_WRITE / PARSER_V3_FIX_NEXT / AUG_SEP_BLOCKED / ONE_TASK_ONLY / COST_LE_20`
