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
Next ONE task: **4,703 missing racesの最小コストbackfill計画を事前見積りする（まだ実行しない）。**

`EX_TIME_OOS_GAP_DIAG_DONE / BACKFILL_COST_PLAN_NEXT / ONE_TASK_ONLY / COST_LE_20`
