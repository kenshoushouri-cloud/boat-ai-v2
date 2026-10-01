# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_2129.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current focus:
- `postgres-recovery` = current data SoT until explicit cutover
- 5GB cutover candidate = `postgres-hobby-fullhistory-candidate-v4`
- required odds unique index = VALID/READY; do not rebuild
- Railway-only `postgres-history-archive` = PostgreSQL 18 + 5GB, SUCCESS, empty/reserved
- retention = **FULL_HISTORY_PINNED**; historical research完了前は履歴を移動/削除しない
- next = read-only historical/backtest dependency + retention inventory
- then parity -> writer freeze -> final sync -> zero-delta parity -> retarget -> cutover -> smoke -> legacy cleanup -> Hobby
- TOTO is separate and protected
- Keirin Railway project deleted by user
- `Postgres` / `Postgres-AbWo` unverified; do not delete/resize
- target Pro -> Hobby = 2026-10-02; billing boundary = 2026-10-03

Fixed:
- GitHub `main` = code SoT
- Railway-only storage design preferred
- `purchase_action=false`
- never call `list_variables`
- one task at a time / short output

`READ_CURRENT_COMPACT / RAILWAY_ONLY_2DB / FULL_HISTORY_PINNED / HISTORY_INVENTORY_NEXT / PROTECT_TOTO / PURCHASE_FALSE`
