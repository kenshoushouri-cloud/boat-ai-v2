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
- read-only実データsampleは既知1件+追加5件=**6/6 official_partial（各5艇）、parser_failure=0**。追加診断はHTTP5、DB write 0。Aug/Sep未実行。
- **Next ONE task:** Jul missing 53のDB側 `exhibition_time` 件数/欠損lane分布だけread-only確認。追加HTTPなし、DB writeなし。

`COMPACT_ONLY / JUL_SAMPLE_6_OF_6_PARTIAL / NO_MORE_HTTP_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
