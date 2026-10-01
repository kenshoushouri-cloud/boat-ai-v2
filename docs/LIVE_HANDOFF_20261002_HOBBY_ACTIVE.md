# Live Handoff 2026-10-02 — Hobby active

## SoT / protection
- GitHub `main` = code SoT; always re-fetch live before work.
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`.
- Protect candidate-v4, `postgres-history-archive`, `archive-restore-key-20261001`, active writers/reports/backtest/historical services, and TOTO.
- Never call `list_variables`.
- `purchase_action=false`.
- One task at a time; keep chat output short.

## Completed migration / cleanup
- candidate-v4 cutover, smoke, rollback proof, resumed Production run: PASS.
- 13 scheduled writers resumed.
- encrypted pre-Hobby archive + isolated restore drill: PASS.
- GitHub restore run `36934788763`: SUCCESS.
- archive artifact: `boat-ai-pre-hobby-restorable-20261001-v2`.
- two former 50GB orphan DB services/volumes were deleted/queued for deletion.
- `postgres-recovery` service + 20GB volume were deleted after final live preflight and restore evidence confirmation.

## Hobby migration
- Railway Dashboard screenshot confirmed Active Plan = Hobby on 2026-10-02.
- Post-change boat-v2-postgres production smoke: PASS.
- Post-change TOTO production smoke: PASS.
- boat volumes remaining: candidate-v3 5GB, candidate-v4 5GB, history archive 5GB.
- TOTO Postgres volume: 5GB; observed usage about 0.186GB at verification.
- candidate-v4 observed usage at pre-change check: about 4.337GB current; 24h peak about 4.830GB. Hobby max volume size is 5GB, so storage headroom requires monitoring.
- boat production has an empty staged patch (`changes: []`).
- TOTO has a pre-existing staged service update; it was not touched.

## First post-Hobby scheduled run
- First unambiguous post-Hobby 08:30 JST slot was checked.
- `cron-final-check`: PASS; log reported `RESULT=PASS`.
- `cron-learning-all`: completed successfully and saved learning data.
- No Hobby-induced cron failure observed.

## Next single task
**Post-Hobby storage safety check for candidate-v4.**
- Read-only only.
- Re-fetch candidate-v4 disk usage/24h peak and recent DB/service health.
- Do not resize, delete, redeploy, or change plan.
- If storage is still close to 5GB, identify the safest no-purchase mitigation from existing project mechanisms before any mutation.
- Keep candidate-v4/history archive/escrow/TOTO protected.

`HOBBY_ACTIVE / FIRST_CRON_PASS / STORAGE_SAFETY_NEXT / PURCHASE_FALSE`
