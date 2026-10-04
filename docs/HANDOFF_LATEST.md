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
- Jul 53件pilotはHTTP成功したがparser 0行 → DB write 0で安全停止。Aug/Sep未実行。
- **Next ONE task:** historical parser v3へ切替え、parse quality fail-closed化の安全テストのみ。再pilotはまだしない。

`COMPACT_ONLY / PARSER_V3_FIX_NEXT / ONE_TASK_ONLY / COST_LE_20`
