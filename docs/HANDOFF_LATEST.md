# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261008_1155_COMPACT.md`

次チャットで読むのは次の3点だけ:
1. `docs/HANDOFF_LATEST.md`
2. current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

最優先:
- 古いhandoff / PROJECT_HISTORY / 長いworkflow / 過去chatは大量参照しない。
- 1回に1作業、tool call最小限。pending commandを重複実行しない。
- SHA/run/件数/容量は必要時だけlive取得。
- Production=V4、V5/V5.1=research-only。
- Railway費用 <= USD20、理想 <= USD15。Agent/AI禁止。

**Next ONE task:** Issue #581 command id `6051221908` の結果だけ確認。結果があれば判定、再実行禁止。

`COMPACT_ONLY / ONE_TASK_ONLY / NO_BULK_HISTORY / NO_DUPLICATE_RUN`
