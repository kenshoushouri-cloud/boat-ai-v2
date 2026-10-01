# Live Handoff 2026-10-02 — legacy cleanup plan ready

## 1. SoT / protection
- GitHub `main` = code SoT; always re-fetch live.
- **Production data SoT = `postgres-hobby-fullhistory-candidate-v4`**.
- `postgres-recovery` = verified rollback reference until safely archived/retired.
- `postgres-history-archive` = 5GB reserved; do not move FULL_HISTORY_PINNED data yet.
- Protect V4/V5 prospective evidence, historical/backtest, TOTO.
- Never call `list_variables`. `purchase_action=false`. One task at a time.

## 2. Production migration health
- cutover = DONE.
- cutover smoke = PASS.
- rollback verification = PASS.
- 13 scheduled writers resumed against candidate-v4.
- first resumed Production run = PASS.
- candidate-v4 disk after first run ~= `4.3526 GB / 5 GB`.
- no new FAILED / CRASHED / no-space / OOM issues at health gate.

## 3. Hobby compatibility plan
Railway current docs:
- Hobby Volume Storage limit = **5GB**.
- volume live resizing expands capacity only; existing oversized volumes are not shrinkable in place.
- plan downgrade takes effect at the beginning of the next billing cycle.

Hobby-compatible current volumes:
- `postgres-hobby-fullhistory-candidate-v4` = 5GB.
- `postgres-history-archive` = 5GB.
- `postgres-hobby-fullhistory-candidate-v3` = 5GB, actual disk ~= 4.552GB; redundant candidate but not a size blocker.

Oversized blockers:
- `postgres-recovery` = 20GB allocated, actual disk ~= 4.990GB. Verified rollback source.
- `Postgres` = 50GB allocated, actual disk ~= 0.843GB. Contents/dependencies unverified.
- `Postgres-AbWo` = 50GB allocated, actual disk ~= 0.844GB. Contents/dependencies unverified.

Keep:
- active Production writers/reports/backtest/historical services.
- `candidate-discovery-v4-fallback-dispatcher` (active daily fallback).
- `archive-restore-key-20261001` while encrypted restore path is needed.
- TOTO unchanged/protected.

Likely later cleanup candidates after verification:
- v3 candidate after rollback safety no longer needs it.
- old no-cron/no-volume audit/one-shot/legacy services.
These do not currently block Hobby by volume size.

## 4. Read-only orphan check attempt
Issue #42 plan comment: `5941649284`.

Existing `orphan-postgres-metadata-readonly` was attempted for `Postgres` / `Postgres-AbWo`.
It failed before metadata read with:
`Connection URL should point to the Railway TCP proxy`.

Reason: both services expose only private Railway networking and no public TCP proxy.
No DB row/schema/service/volume mutation occurred.

## 5. Safe cleanup sequence
1. Verify `Postgres` and `Postgres-AbWo` contents/dependencies through a Railway-private read-only path.
2. Create a fresh encrypted read-only archive of `postgres-recovery` and restore-verify it with the existing isolated restore drill. Retain escrow key.
3. With explicit destructive approval, remove/replace only oversized services proven obsolete or safely archived.
4. Verify every required remaining volume <=5GB and Production health remains clean.
5. Initiate Pro→Hobby.

## 6. Next single task
**Read-only verification of `Postgres` and `Postgres-AbWo` through a Railway-private path.**

Do not delete/resize/move data/change plan in that task.

`CLEANUP_PLAN_READY / THREE_OVERSIZED_BLOCKERS / VERIFY_ORPHANS_NEXT / NO_DELETE_YET / PURCHASE_FALSE`
