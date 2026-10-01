# Live Handoff — 2026-10-01 14:44 JST (compact)

Status: **CURRENT COMPACT HANDOFF**  
Repository: `kenshoushouri-cloud/boat-ai-v2`

Always re-fetch live state. Snapshot SHA/run/count values below are not fixed.

## 1. Purpose / fixed contract

Build a reproducible positive-expectation boat-race selection system using only pre-deadline information. No leakage, hindsight reconstruction, or gate relaxation for economic targets.

Fixed:
- GitHub `main` = code Source of Truth; Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 = permanently **UNAVAILABLE**
- V5 gate = V4 >=20 resolved `FORMAL_AVAILABLE` days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstruction gives zero prospective gate credit
- `purchase_action=false`
- Production behavior / cutover / delete / resize / plan changes require explicit approval
- never enumerate Railway plaintext Variables / never call `list_variables`
- Railway Agent only if normal MCP cannot answer

## 2. Schedule

Daily: `08:15 cutoff -> 08:16 GitHub -> 08:20 Railway fallback -> formal freeze -> 23:30 settlement`

Milestones:
- **2026-10-03:** Pro -> Hobby billing boundary target; parity/resource safety first
- **around 2026-10-15:** V5 operational-readiness review target; not automatic go-live

Last settled snapshot:
- V4 = **8/20** through 2026-09-28
- S03_M2 = **63/100**
- 2026-10-01 fallback freeze `36790563118` = SUCCESS; settlement must confirm resolved status
- historical writer `36703692641`: do not duplicate-trigger; re-fetch live state

## 3. Pro -> Hobby migration state

Completed:
- Railway backup secured
- encrypted recovery archive secured
- restore/parity run `36812386066` = SUCCESS
- recovery artifact `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066`, id `11139857666`
- exact restore parity previously PASS for 39 public tables + schema metadata
- retention finalization `36813600010` = SUCCESS
- retention policy = **FULL_HISTORY_PINNED**
- no historical DELETE before migration

Current isolated candidate:
- service = `postgres-hobby-fullhistory-candidate-v3`
- 5 GB volume candidate; Production not targeted
- ENOSPC diagnostic: candidate DB **3,284,670,143 bytes**, WAL **1,073,741,824 bytes**
- source DB snapshot around **4.44 GB**
- missing candidate indexes identified:
  - `ux_v2_odds_trifecta_race_ticket` — source about **571 MB**
  - `ux_v2_venues_venue_id` — source **16 KB**
- small venues index repair completed successfully:
  - `INDEX_PRESENT=true`
  - candidate DB after repair **3,284,686,527 bytes**
  - WAL remains **1,073,741,824 bytes**
- Production was not mutated by the repair
- old 60d filtered candidate is not a cutover reference

**Next single task:** resolve the remaining candidate-only `ux_v2_odds_trifecta_race_ticket` index under the 5 GB constraint, then rerun read-only exact parity. Do not cut over until parity is accepted.

Safe order:
`restore DONE -> retention DONE -> 5GB full-history candidate -> remaining index repair -> exact parity -> explicit cutover approval -> stable cutover -> cleanup -> Pro->Hobby downgrade`

## 4. Operating discipline

- one task at a time
- concise results only; avoid broad Actions/log/list endpoints
- for GitHub Actions/Issue #42, fetch only the specific run/comment/page needed
- replace stale handoff text instead of appending
- read only `HANDOFF_LATEST.md -> this file -> NEXT_CHAT_START_HERE.md`
- old handoffs are history unless a specific past decision is needed

`CURRENT_COMPACT_HANDOFF / ONE_TASK_AT_A_TIME / AVOID_BULK_ACTIONS_OUTPUT / FULL_HISTORY_PINNED / 5GB_CANDIDATE / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`
