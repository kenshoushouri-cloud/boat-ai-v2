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
Next ONE task: **Recent Form係数探索の範囲・grid・採否基準を結果参照前に固定する。**

`V51_RF_READY / COEFFICIENT_GRID_FREEZE_NEXT / ONE_TASK_ONLY / COST_LE_20`
