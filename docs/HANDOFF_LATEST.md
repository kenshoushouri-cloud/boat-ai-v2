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
- PR #550で `complete / official_partial / parser_failure` をfail-closed分類。
- Jul 53件: **official_partial 39 / zero-value 14 / complete 0**。zero-value代表3件は全て6艇行あり・展示タイム全空欄で、parser不適合は確認されず公式値欠損。2件は「中止」表記。DB write0、Aug/Sep未実行。
- **Next ONE task:** parser/backfillに `official_absent` を追加し、6艇行あり＋展示値0件をparser failureと分離。安全テストのみ、HTTPなし。

`COMPACT_ONLY / JUL_39_PARTIAL_14_ZERO / OFFICIAL_ABSENT_CLASSIFY_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
