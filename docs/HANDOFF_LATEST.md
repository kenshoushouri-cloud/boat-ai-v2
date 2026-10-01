# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_2128.md`

Read only:
1. this pointer
2. current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current focus:
- `postgres-recovery` = current data SoT until cutover
- 5GB cutover candidate = `postgres-hobby-fullhistory-candidate-v4`
- required odds unique index = VALID/READY; do not rebuild
- Railway-only history DB `postgres-history-archive` = PostgreSQL 18 + 5GB, SUCCESS, empty/reserved
- retention = **FULL_HISTORY_PINNED**; historical research完了前は履歴を移動/削除しない
- next = read-only source vs candidate-v4 current parity/delta baseline
- then freeze -> final sync -> zero-delta parity -> writer retarget -> explicit cutover -> smoke -> rollback/resource整理 -> Hobby
- TOTO is separate and protected
- `Postgres` / `Postgres-AbWo` remain unverified; do not delete/resize
- target Pro -> Hobby = 2026-10-02; billing boundary = 2026-10-03

Fixed:
- GitHub `main` = code SoT
- Railway-only storage design preferred
- `purchase_action=false`
- never call `list_variables`
- one task at a time / short output

`READ_CURRENT_COMPACT / RAILWAY_ONLY_2DB / FULL_HISTORY_PINNED / PARITY_NEXT / PROTECT_TOTO / PURCHASE_FALSE`
