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
- Jul 53件は **39 partial / 14 absent** で確定。PR #561でterminal/unfillable manifest化し、Exhibition-Time-onlyではHTTP前に除外。July plan-onlyはtarget=0 / HTTP=0 / DB write=0でPASS。Aug/Sep未実行。
- Aug 2026-08-01 plan-only: **target=1 / HTTP=0 / DB write=0 / PASS**。
- **Next ONE task:** 2026-08-01のtarget 1件だけをExhibition-Time-onlyで実データpilotする。Aug全体はまだ実行しない。

`COMPACT_ONLY / AUG01_TARGET_1 / AUG01_ONE_RACE_PILOT_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
