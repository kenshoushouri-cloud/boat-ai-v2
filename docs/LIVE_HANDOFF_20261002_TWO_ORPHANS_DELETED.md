# Live Handoff 2026-10-02 — two 50GB orphan DBs deleted

## 1. SoT / protection
- GitHub `main` = code SoT; re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` 20GB remains protected until its final cleanup step.
- `postgres-history-archive` = 5GB reserved; FULL_HISTORY_PINNED history not moved.
- Protect V4/V5, historical/backtest, TOTO.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Migration / restore safety
- cutover / smoke / rollback / first resumed Production run = PASS.
- 13 scheduled writers resumed against candidate-v4.
- fresh encrypted `postgres-recovery` archive + isolated restore = PASS.
- restore run `36934788763` = SUCCESS.
- archive artifact = `boat-ai-pre-hobby-restorable-20261001-v2`.
- escrow key service remains `archive-restore-key-20261001`.

## 3. Oversized cleanup progress
Issue #42 progress comment: `5942322298`.

Completed:
- `Postgres` service = deleted.
- `postgres-volume-0I4P` 50GB = detached, pending deletion=true.
- `Postgres-AbWo` service = deleted.
- `postgres-volume-TmfB` 50GB = detached, pending deletion=true.

Railway deletion grace behavior:
- deleted volumes remain queued/pending and restorable for up to ~48h before permanent deletion.

Protected and still present:
- `postgres-recovery` 20GB.
- candidate-v4 Production 5GB.
- history archive 5GB.
- escrow key.
- active writers/reports/backtest/historical services.
- TOTO.

No plan change yet.

## 4. Next single task
**Final live preflight for `postgres-recovery`, then delete its service + 20GB volume under the user's existing explicit cleanup approval.**

Before deletion:
- re-fetch `postgres-recovery` live status/volume.
- confirm archive restore PASS evidence remains recorded.
- do not touch candidate-v4/archive/escrow/TOTO.
- delete service + volume via Railway dashboard/2FA if required.
- verify volume enters pending deletion.

After that:
**Hobby compatibility check -> Pro→Hobby plan change.**

`TWO_50GB_ORPHANS_DELETED / RECOVERY_20GB_NEXT / PURCHASE_FALSE`
