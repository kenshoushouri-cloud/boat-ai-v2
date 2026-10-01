# Live Handoff — 2026-10-01 Hobby split (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Always re-fetch live state. SHA/run/size/count below are observations, not fixed values.

## 1. System purpose

Keep the boat-racing AI, V4/V5 prospective evidence, historical acquisition, and backtests intact while moving Railway from Pro to Hobby safely and keeping storage inside Railway where possible.

Fixed:
- GitHub `main` = code SoT
- Railway `postgres-recovery` = current Production data SoT until explicit cutover
- formal V4 2026-09-29 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`

## 2. Timeline

- **2026-10-01:** 5GB candidate repair + Railway-only history/archive split preparation
- **2026-10-02:** target for final parity/sync/cutover and Pro -> Hobby, only if all safety/storage gates pass
- **2026-10-03:** billing renewal boundary
- around **2026-10-15:** V5 operational-readiness review target; not automatic go-live

## 3. Current work/state

### Production / migration
- Source SoT: `postgres-recovery`; collection continues.
- 5GB cutover candidate: `postgres-hobby-fullhistory-candidate-v4`.
- Required unique index `ux_v2_odds_trifecta_race_ticket (race_id,ticket)` was rebuilt successfully.
- Post-build observation: index ~303 MB, VALID/READY; DB ~3.585 GB; WAL ~0.537 GB; actual candidate disk ~4.331 GB.
- GitHub Action showed failure only because PRE verification formatting missed a grep; **do not rebuild the index again**.
- Exact source-v4 parity/final sync/cutover have **not** been completed yet.

### Railway-only history split
- User preference: avoid external storage/site registration; keep archive/history in Railway when practical.
- New isolated service: `postgres-history-archive`.
- PostgreSQL 18 + one 5GB volume, deployment **SUCCESS**.
- It is currently empty; no data has been copied, deleted, or redirected.
- A read-only retention audit `/railway hobby-retention-finalize-readonly` was triggered to identify safe archive candidates; its latest result still needs to be read.
- Do not move/delete historical evidence before dependency/backtest review.

### Writers
Historical GitHub write workflows currently target `postgres-recovery`. At cutover, freeze -> final sync -> parity -> retarget writers to the new Production DB -> resume collection. Do not allow post-cutover writes to continue only on the old source.

## 4. Other protected projects/resources

- TOTO is separate Railway project `toto-ai-v1`; Postgres observed ~0.185 GB on a 5GB volume. **Do not modify it.**
- Keirin project was deleted by the user.
- In boat project, `Postgres` / `Postgres-AbWo` remain unverified and have large volumes; do not delete/resize until contents/dependencies are confirmed.
- Hobby downgrade requires all remaining storage/resource constraints to be compatible; resolve oversized legacy volumes only after verification.

## 5. Next single task

**Read only the latest result of the triggered Hobby retention audit and identify which historical/raw tables are safe candidates for `postgres-history-archive`.**

Do not move/delete data yet.

After that, one task at a time:
1. finalize archive split design without losing V4/V5/backtest evidence
2. exact parity source vs candidate-v4
3. freeze writers
4. safe final sync + zero-delta parity
5. retarget Production/historical writers
6. explicit cutover + smoke test
7. verify/remove only obsolete oversized legacy resources
8. Pro -> Hobby

## 6. Guardrails

- one task at a time; short output
- never enumerate Railway plaintext Variables / never call `list_variables`
- Railway Agent only when normal MCP cannot do the task
- no destructive data/resource action without dependency verification
- protect TOTO and all prospective V4/V5 evidence
- old handoffs are history; load only if a specific past decision is needed

Observed GitHub main before this handoff update: `0d5a0701d7e38d44a6ef6a07bff422973feaa0a8`; re-fetch live.

`CURRENT_COMPACT_HANDOFF / RAILWAY_ONLY_ARCHIVE / 5GB_V4 / PARITY_BEFORE_CUTOVER / PROTECT_TOTO / PURCHASE_FALSE`
