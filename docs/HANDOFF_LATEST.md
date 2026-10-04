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
- read-only実データsampleは**6/6 official_partial（各5艇）**。DB分布はJul 53件すべて `exhibition_time=0艇`、全6lane未保持。DB単独では残り47件のofficial partial判定は不可。DB write 0、Aug/Sep未実行。
- **Next ONE task:** 既知6件を除くJul残り47件だけをread-only HTTP分類し、53/53を確定する。DB writeなし。

`COMPACT_ONLY / JUL_DB_ALL_ZERO / REMAINING_47_CLASSIFY_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
