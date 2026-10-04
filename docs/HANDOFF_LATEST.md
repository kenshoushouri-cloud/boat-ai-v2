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
- Jul 53件: **official_partial 39 / zero-value 14 / complete 0**。zero-value代表3件は新parserで**3/3 official_absent**。HTTP3 / DB write0。Aug/Sep未実行。
- **Next ONE task:** zero-value未確認11件だけread-only再分類し、14/14を確定。最大HTTP11。

`COMPACT_ONLY / OFFICIAL_ABSENT_3_OF_3 / VERIFY_11_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
