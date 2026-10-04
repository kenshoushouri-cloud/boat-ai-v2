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
- Jul 53件のread-only分類確定: **official_partial 39 / parser_failure 14 / complete 0**。partialは各5艇。HTTP追加47、DB write0。parser failureは **7/29 venue09全12R** + 7/28 venue09 12R + 7/17 venue01 12R。
- **Next ONE task:** parser failureの代表3件だけ公式beforeinfo構造をread-only診断し、実データ欠損かparser不適合か判別。Aug/Sepはまだしない。

`COMPACT_ONLY / JUL_39_PARTIAL_14_FAILURE / FAILURE_SAMPLE_DIAG_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
