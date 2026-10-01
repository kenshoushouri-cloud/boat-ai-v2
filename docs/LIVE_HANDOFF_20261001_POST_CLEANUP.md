# Live Handoff — 2026-10-01 post-cleanup (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Always re-fetch live state. SHA/run/size/count values below are observations, not fixed assumptions.

## 1. Purpose

Keep the boat-racing AI, V4/V5 prospective evidence, historical collection, and backtests running while safely moving Railway PostgreSQL from Pro to a 5 GB Hobby target.

Fixed:
- GitHub `main` = code SoT
- Railway `postgres-recovery` = current data SoT
- formal V4 on 2026-09-29 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives no prospective gate credit
- `purchase_action=false`

## 2. Timeline

- **2026-10-01:** obsolete-resource cleanup, candidate-v4 recovery, 5 GB headroom work
- **2026-10-02:** target for final sync/parity/cutover and Pro -> Hobby completion, only if safety/headroom gates pass
- **2026-10-03:** billing renewal boundary
- around **2026-10-15:** V5 operational-readiness review target; not automatic go-live

Daily prospective schedule remains:
`08:15 cutoff -> 08:16 GitHub -> 08:20 Railway fallback -> formal freeze -> 23:30 settlement`.

## 3. Protected live path

Do not modify/delete unless a later verified cutover explicitly replaces it:
- `postgres-recovery` + 20 GB volume
- `historical-backfill`, `backtest-analysis`
- active cron collection/settlement services
- candidate-v3 as fallback
- candidate-v4 as current 5 GB migration candidate

Needed historical/backtest data stays until backtests + an operating test period determine the external-archive policy.

## 4. Completed work

Obsolete resources removed successfully:
- `postgres-hobby-candidate` + 5 GB volume
- old `postgres-hobby-fullhistory-candidate` + 5 GB volume
- `postgres-hobby-fullhistory-candidate-v2` + 50 GB volume
- `hobby-migration-worker`, `-v2`, `-v3`

Post-cleanup read-back:
- protected services remain present/SUCCESS
- pending staged changes = empty
- `Postgres` / `Postgres-AbWo` were **not deleted** because contents remain unverified

## 5. Candidate-v4

Service: `postgres-hobby-fullhistory-candidate-v4`.

Safety:
- unsafe non-atomic `current-refresh` is disabled (`if: false`)
- fixed-artifact restore now preflights in ephemeral PostgreSQL before touching v4
- restore run `36839120335`: preflight SUCCESS, v4 restore SUCCESS, post-restore verify SUCCESS; run-level failure was only the final result-post cleanup bug

Latest read-only observation:
- DB: **3,282,384,575 bytes**
- WAL: **536,870,912 bytes**
- public indexes: **613,498,880 bytes**
- `ux_v2_odds_trifecta_race_ticket` is absent
- that unique index was previously ~303 MB and is required for `(race_id,ticket)` uniqueness and exact schema parity; do not permanently omit it just to fit 5 GB

Source observation:
- `postgres-recovery`: **4249 MB**
- same-day observed growth: **4219 -> 4249 MB** over ~9h14m; short-window estimate only

## 6. Next single task

**Run/read candidate-v4 read-only index-layout diagnostics and identify only truly redundant/duplicate indexes.**

Do not rebuild/delete indexes yet.

After headroom is acceptable:
1. rebuild required odds unique index
2. exact parity
3. identify/freeze writers
4. final sync + zero-delta parity
5. explicit cutover approval
6. smoke test
7. Pro -> Hobby completion before billing boundary

## 7. Guardrails

- unnecessary resources/data may be deleted only after dependency review
- never enumerate Railway plaintext Variables / never call `list_variables`
- Railway Agent only when normal MCP cannot perform the task
- one task at a time; avoid bulk Actions/comments/logs
- no cutover before required index + exact parity + final writer freeze/sync + explicit approval

Observed GitHub main at this update: `782374870b4c0d0260878bf674c02c7eea2e7a13`; re-fetch live.

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / PROTECT_HISTORY / 5GB_V4 / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`
