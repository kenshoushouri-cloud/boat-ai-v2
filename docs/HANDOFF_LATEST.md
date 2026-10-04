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
Diagnosis: V4 workflowがstaleな `postgres-recovery` を参照しており、現SoT `postgres-hobby-fullhistory-candidate-v4` と不整合。S03は停止せず収集中で、positive+official条件により増加が遅い。
Next ONE task: **V4 prospective-freeze workflowのDB service参照だけをcandidate-v4へ修正し、安全確認する。**

`SELECTION_FROZEN / LIVE_GATES_NEXT / ONE_TASK_ONLY / COST_LE_20`
