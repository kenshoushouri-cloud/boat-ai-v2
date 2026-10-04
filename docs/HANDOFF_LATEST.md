# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261004_COMPACT.md`

次チャットでは次の3点だけ読む:
1. `docs/HANDOFF_LATEST.md`
2. 上記current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

要点:
- Production=V4 / V5・V5.1=research-only / 運用開始目標=2026年10月中旬 / Railway<=USD20/month。
- Live gatesはV4 9/20、S03_M2 66/100でBLOCKED。gateは下げず、economics未実行。
- Recent Formはblind VAL/OOSで不採用、収集継続。
- Exhibition Time OOS missing=4,703。低コスト専用mode実装済み。
- Jul旧pilotはparser 0行→DB write 0で安全停止。その後PR #546でhistorical parser v3 + fail-closed quality gateへ修正し、安全CI/Jul plan-onlyはPASS。Aug/Sep未実行。
- **Next ONE task:** Jul missing 53件だけ再pilotし、parse成功・missing-fill・DB/WAL/volume増分を確認。Aug/Sepはまだしない。

`COMPACT_ONLY / PARSER_V3_FIXED / JULY_53_REPILOT_NEXT / ONE_TASK_ONLY / COST_LE_20`
