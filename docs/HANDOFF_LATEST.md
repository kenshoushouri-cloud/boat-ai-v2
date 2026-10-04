# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261004_COMPACT.md`

次チャットでは次の3点だけ読む:
1. `docs/HANDOFF_LATEST.md`
2. 上記current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

要点:
- Production=V4 / V5・V5.1=research-only / 運用開始目標=2026年10月中旬。
- Railway費用は**月USD20以下を上限**とし、精度・安定性・必要なデータ取得を損なわない範囲で**可能な限り安くする**。USD15以下にできる場合も積極的に削減する。
- Live gatesはV4 9/20、S03_M2 66/100でBLOCKED。gateは下げず、economics未実行。
- Recent Formはblind VAL/OOSで不採用、収集継続。
- Exhibition Time OOS missing=4,703。低コスト専用mode実装済み。
- Jul 53件再pilotは既に実行済み。historical parser v3使用53/53、HTTP53、fetch失敗0だがusable 6艇=0、quality gateで53件すべてwrite禁止、DB write=0、FAIL_PARSE_QUALITY。Aug/Sep未実行。
- PR #549で1件read-only診断を追加。sample `20260701_10_08` は公式beforeinfo自体が1号艇展示タイム空欄で候補値5艇分のみ。少なくともこの例はparser故障ではなく**official partial data**でfail-closedが正しい。
- **Next ONE task:** historical parser/backfillに「official partial data」と「parser failure」の判別を追加し、6艇write gateは維持したまま安全テストのみ。53件再HTTPはまだしない。

`COMPACT_ONLY / JULY_REPILOT_ZERO_WRITE / OFFICIAL_PARTIAL_CONFIRMED_SAMPLE / CLASSIFY_PARTIAL_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
