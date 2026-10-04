# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261005_COMPACT.md`

次チャットで読むのは次の3点だけ:
1. `docs/HANDOFF_LATEST.md`
2. current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

要点:
- Production=V4、V5/V5.1=research-only、運用開始目標=2026年10月中旬。
- Railwayは月USD20以下、可能ならUSD15以下。1回に1作業。
- candidate-v4は5GB上限近く。不足データ補完は一時停止し、容量確保を優先。
- motor/boat固定OOSアブレーションは改善側で、archive候補ではない。
- Recent Form last5はblind VAL/OOS不採用。**archive退避+425,772行parityはPASS済み**。
- source direct UPDATE/VACUUM FULLは禁止継続。**Next ONE taskはfresh disposable compact target作成前のread-only cost/headroom gate**。

古いhandoffは履歴。SHA/run/件数/容量は必要時だけlive再取得。

`COMPACT_ONLY / CAPACITY_FIRST / RECENT_FORM_ARCHIVED / SOURCE_DIRECT_REWRITE_FORBIDDEN / COST_GATE_NEXT / ONE_TASK_ONLY / COST_MINIMIZE_LE_20`
