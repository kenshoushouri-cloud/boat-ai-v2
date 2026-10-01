# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_2117.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current focus:
- protect `postgres-recovery`, V4/V5 evidence, historical collection, backtests, and separate TOTO project
- 5GB cutover candidate = `postgres-hobby-fullhistory-candidate-v4`
- required odds unique index rebuilt and VALID/READY; do not rebuild again
- Railway-only `postgres-history-archive` = PostgreSQL 18 + 5GB, SUCCESS, empty/reserved
- latest retention audit = **FULL_HISTORY_PINNED**; do not move/delete historical rows yet
- next single task = read-only source vs candidate-v4 current parity/delta baseline
- then writer freeze -> final sync -> zero-delta parity -> writer retarget -> explicit cutover -> smoke -> oversized legacy resource resolution -> Hobby
- `Postgres` / `Postgres-AbWo` remain unverified; do not delete/resize
- target Pro -> Hobby completion = 2026-10-02; billing boundary = 2026-10-03

Fixed:
- GitHub `main` = code SoT
- `postgres-recovery` = current data SoT until cutover
- keep storage inside Railway where practical
- `purchase_action=false`
- never enumerate Railway plaintext Variables / never call `list_variables`
- one task at a time / short output

`READ_CURRENT_COMPACT / FULL_HISTORY_PINNED / RAILWAY_ONLY_ARCHIVE / 5GB_V4 / PARITY_NEXT / PROTECT_TOTO / PURCHASE_FALSE`
