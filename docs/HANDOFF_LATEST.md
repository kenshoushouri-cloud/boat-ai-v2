# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_POST_CLEANUP.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current focus:
- protect `postgres-recovery`, V4/V5 evidence, historical collection, and backtests
- 5 GB candidate = `postgres-hobby-fullhistory-candidate-v4`
- obsolete Hobby migration resources were cleaned up; pending staged changes are empty
- unsafe v4 current-refresh is disabled
- fixed-artifact restore has succeeded; current v4 is compact but the ~303 MB odds unique index is intentionally absent
- do not omit that index permanently; first look for truly redundant/duplicate indexes
- **next single task = run/read candidate-v4 read-only index-layout diagnostic**
- no cutover until required index, exact parity, final writer freeze/sync, and explicit approval
- target Pro -> Hobby completion = 2026-10-02; billing boundary = 2026-10-03

Fixed:
- GitHub `main` = code SoT
- `postgres-recovery` = current data SoT
- needed historical/backtest data stays until testing determines external-archive policy
- unnecessary resources/data may be deleted only after dependency review
- `purchase_action=false`
- never enumerate Railway plaintext Variables / never call `list_variables`
- Railway Agent only when normal MCP cannot perform the task
- one task at a time / avoid bulk output

`READ_CURRENT_COMPACT / ONE_TASK_AT_A_TIME / PROTECT_HISTORY / 5GB_V4 / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`
