# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261004_COMPACT.md`

次チャットで読むのは次の3点だけ:
1. `docs/HANDOFF_LATEST.md`
2. current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

要点:
- Production=V4。V5/V5.1=research-only。運用開始目標=2026年10月中旬。
- Railwayは月USD20を上限に、必要品質を損なわない範囲で可能な限り安くする。
- Live gateはV4 9/20、S03_M2 66/100でBLOCKED。gateは下げない。
- Exhibition Time OOS missing=4,703。Jul 53再pilotはwrite 0で停止。
- PR #555 merged。historical parser/backfillは `complete / official_partial / official_absent / parser_failure` をfail-closed分類。`official_absent`は6艇行あり＋展示値0件でwrite禁止。
- Jul 53件は確定: **official_partial 39 / official_absent 14 / complete 0 / parser_failure 0**。追加11件も11/11 official_absent。DB write0、Aug/Sep未実行。
- **Next ONE task:** Jul 53を再取得対象から外せる低コストなterminal/unfillable扱いを実装し、安全テストのみ。

`COMPACT_ONLY / JUL_53_UNFILLABLE_CONFIRMED / TERMINAL_SKIP_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
