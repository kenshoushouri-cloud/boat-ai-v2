# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261001_HOBBY_SPLIT.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current focus:
- protect `postgres-recovery`, V4/V5 evidence, historical collection, backtests, and separate TOTO project
- 5GB cutover candidate = `postgres-hobby-fullhistory-candidate-v4`
- required odds unique index rebuilt and VALID/READY; do not rebuild again
- new Railway-only history DB `postgres-history-archive` = PostgreSQL 18 + 5GB volume, SUCCESS, empty
- read-only retention audit was triggered; **next single task = read its latest result and identify archive candidates**
- no data move/delete yet
- exact parity -> writer freeze -> final sync -> zero-delta parity -> retarget writers -> explicit cutover -> smoke -> Hobby
- `Postgres` / `Postgres-AbWo` remain unverified; do not delete/resize
- target Pro -> Hobby completion = 2026-10-02; billing boundary = 2026-10-03

Fixed:
- GitHub `main` = code SoT
- `postgres-recovery` = current data SoT until cutover
- keep storage inside Railway where practical
- `purchase_action=false`
- never enumerate Railway plaintext Variables / never call `list_variables`
- one task at a time / short output

`READ_CURRENT_COMPACT / RAILWAY_ONLY_ARCHIVE / 5GB_V4 / PARITY_BEFORE_CUTOVER / PROTECT_TOTO / PURCHASE_FALSE`
