# Live Handoff — 2026-10-01 post-cleanup (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Always re-fetch live state. SHA/run/size/count values below are observations only.

## 1. Purpose / fixed rules

Goal: keep the boat-racing AI, V4/V5 prospective evidence, historical collection, and backtests running while completing a safe Railway Pro -> Hobby migration to a 5 GB PostgreSQL target.

- GitHub `main` = code SoT
- Railway `postgres-recovery` = current Production/data SoT
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`
- needed historical/backtest data must be preserved until backtests + an operating test period determine the final external-archive policy
- obsolete/duplicate migration resources may be deleted after dependency review
- never enumerate plaintext Railway Variables / never call `list_variables`
- Railway Agent only when normal MCP cannot perform the required operation
- one task at a time; avoid bulk logs/comments/actions

## 2. Timeline

- **2026-10-01:** cleanup + 5 GB candidate recovery/capacity work
- **2026-10-02:** target day for final sync/parity/cutover and Pro -> Hobby completion, only if safety/headroom gates pass
- **2026-10-03:** billing renewal boundary
- around **2026-10-15:** V5 operational-readiness review target; not automatic go-live

Daily prospective schedule remains:
`08:15 cutoff -> 08:16 GitHub -> 08:20 Railway fallback -> formal freeze -> 23:30 settlement`.

## 3. Protected live path

Keep untouched unless a later verified cutover explicitly replaces it:
- `postgres-recovery` + 20 GB volume
- `historical-backfill`, `backtest-analysis`
- active cron collection/settlement services
- candidate-v3 as fallback for now
- candidate-v4 as current 5 GB migration candidate

Latest Railway read-back after cleanup: protected services above are present/SUCCESS and pending staged changes are empty.

## 4. Cleanup completed

Dashboard Apply completed successfully. Removed only confirmed-obsolete migration resources:
- `postgres-hobby-candidate` + 5 GB volume
- old `postgres-hobby-fullhistory-candidate` + 5 GB volume
- `postgres-hobby-fullhistory-candidate-v2` + 50 GB volume
- `hobby-migration-worker`, `-v2`, `-v3`

`Postgres` and `Postgres-AbWo` were **not deleted** because their contents were not verified.

## 5. Candidate-v4 current state

Service: `postgres-hobby-fullhistory-candidate-v4`.

Safety:
- unsafe non-atomic `current-refresh` is disabled (`if: false`)
- fixed-artifact restore workflow now preflights into ephemeral PostgreSQL before touching v4
- fixed restore run `36839120335`: preflight SUCCESS, v4 restore SUCCESS, post-restore verify SUCCESS; run-level failure was only the final result-post step cleanup bug

Latest read-only v4 observation:
- DB: **3,282,384,575 bytes**
- WAL: **536,870,912 bytes**
- public indexes: **613,498,880 bytes**
- `ux_v2_odds_trifecta_race_ticket` is currently absent
- that unique index was previously about **303 MB** and is required for `(race_id,ticket)` uniqueness / exact schema parity, so it should not be permanently omitted merely to fit 5 GB

Current source observation:
- `postgres-recovery` DB: **4249 MB**
- same-day observed growth: **4219 -> 4249 MB** over about 9h14m; short-window estimate only

## 6. Current decision / next task

Do **not** cut over yet. Full-history preservation remains required for useful data; unnecessary resources/data may be removed only after confirming they are not needed.

Current next single task:
**run/read the candidate-v4 read-only index-layout diagnostic and identify truly redundant/duplicate indexes that can be removed without breaking V4/V5/backtests, uniqueness, or exact required schema.**

After capacity headroom is acceptable:
1. rebuild required odds unique index
2. re-run exact parity
3. identify/freeze writers for final sync
4. final zero-delta sync/parity
5. explicit cutover approval
6. smoke test
7. Pro -> Hobby completion before billing boundary

Observed GitHub main at this handoff update: `27eb0066e7d18b9f727fbd6e430fe65e86c1fabf`; re-fetch live.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / PROTECT_HISTORY / 5GB_V4 / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`
