# V4 storage ownership migration plan

Status: `RESEARCH_ONLY / NO_PRODUCTION_MUTATION / ARCHIVE_FIRST / DELETE_BLOCKED`

Updated: 2026-09-15 JST

## Goal

Prepare the database ownership split needed to move the completed system back toward Railway Hobby without reducing prediction quality, timing evidence, reproducibility, or recovery options.

Cost target from the project handoff:

- October target: ChatGPT Go + Railway Hobby where safe
- combined target: approximately USD 20/month or less
- cost reduction must never be achieved by dropping required model inputs, Forward evidence, source provenance, or safety guards

This document is a preregistration/design artifact only. It does not authorize a Production schema change, data copy, DELETE/DROP/VACUUM, service/Cron change, or Railway plan change.

## Fresh read-only storage snapshot

Existing guarded Railway DB-size workflow reported PostgreSQL database size: **3681 MB**.

Largest relations observed in the latest audit were approximately:

| Relation | Approx. total size | Initial classification |
|---|---:|---|
| `v2_odds_trifecta` | 1754 MB | valuable historical/raw; archive-first |
| `v2_realtime_odds_snapshots` | 498 MB | Stage2-required now; compact-migration candidate |
| `v2_result_entries` | 223 MB | shared/core result evidence |
| `v2_v24_motor2_forward_shadow` | 208 MB | legacy/research candidate; V4 core does not directly read it |
| `v2_realtime_racer_condition_snapshots` | 193 MB | historical raw; archive/retention audit |
| `v2_realtime_weather_snapshots` | 186 MB | historical raw; archive/retention audit |
| `v2_realtime_race_condition_snapshots` | 169 MB | historical raw; archive/retention audit |
| `v2_race_entries` | 133 MB | V4 runtime/core |
| `v2_realtime_exhibition_snapshots` | 133 MB | historical raw; archive/retention audit |

Exact sizes change over time. Re-run the read-only inventory immediately before any migration decision.

## Current V4 runtime ownership

Current `main` V4 Stage1 generator directly reads:

- `v2_races`
- `v2_race_entries`
- `v2_racer_course_stats_snapshots`
- `v2_opponent_pressure_shadow_v2`
- `v2_candidate_filter_shadow` only for legacy S01-S05 carryover

Important boundaries:

- V4 Stage1 does not read odds/EV for candidate inclusion or ordering.
- Motor2 in current V4 is derived from `v2_race_entries.motor_place2_rate`.
- Current V4 core therefore does not directly require `v2_v24_motor2_forward_shadow`.
- Stage2 `MKT_LATE07_TOP2_SUPPORT_V1` currently requires timing-safe `v2_realtime_odds_snapshots` and must not lose its evidence source.

## Target ownership split

### A. Keep online in Railway

Keep the minimum complete set required for live operation and audit:

- current/future race cards and entries
- official results and result entries needed for settlement/evaluation
- timing-clean Course data
- timing-clean Opponent Pressure data
- new-system-owned market snapshot evidence required by Stage2/trio research
- immutable Forward/evaluation provenance required to prove prospective performance

No retention limit should be imposed until dependency and research requirements are explicitly demonstrated.

### B. Remove the old-selector carryover dependency prospectively

Current V4 artifact still appends S01-S05 rows from `v2_candidate_filter_shadow` even though the core 6-race/12-ticket selection is built independently.

Future cutover revision must:

1. be preregistered before use;
2. remove the legacy S01-S05 runtime read from the new-system artifact contract;
3. prove the V4 core race ordering and core tickets are unchanged for identical source inputs;
4. never rewrite or relabel already-frozen V4 evidence;
5. remain `purchase_action=false` until a separate Production approval.

Only after that and active-runtime zero-consumer proof can `v2_candidate_filter_shadow` become a deletion candidate.

### C. Compact Stage2 market storage

Do not delete `v2_realtime_odds_snapshots` while Stage2 depends on it.

Preferred future design is a versioned new-system-owned compact market record that stores only the timing-safe evidence actually required for reproducibility. A candidate logical record contains:

- `race_id`, `race_date`, venue/race number
- race deadline
- chosen `snapshot_at`
- minutes-to-deadline / timing window identity
- source/provenance identifier
- complete 120-ticket trifecta odds snapshot in a deterministic representation
- completeness flag
- content checksum / deterministic hash
- schema/contract version

The frozen Stage2 contract must still be reproducible exactly from the compact record. No market TOP2 or derived trio support result may be stored without enough raw snapshot information to recompute it.

Before replacing the shared table, run a prospective equivalence period in which old and compact sources independently produce identical Stage2 support decisions.

### D. Archive large historical stores before deleting online rows

#### `v2_odds_trifecta`

At ~1.75 GB it is the largest single relation and therefore the largest potential capacity lever, but it is useful historical/research data. It is **not** a delete-first table.

Before reducing its online retention:

1. determine every current default-branch + Railway runtime consumer;
2. determine the minimum online date window required by any still-active consumer;
3. export older rows by bounded date partition/month to an external archive;
4. record row count, date range, uncompressed/compressed size and SHA-256 manifest;
5. perform at least one restore/readback test from the archive;
6. keep only the proven online-required slice if and only if the dependency audit permits it.

Archive format/storage provider is a later implementation decision. The archive must be independently recoverable and must not depend on the same Railway volume being reclaimed.

#### Large realtime condition/exhibition histories

The following are also candidates for archive/retention reduction after old-system consumers are retired:

- `v2_realtime_racer_condition_snapshots`
- `v2_realtime_weather_snapshots`
- `v2_realtime_race_condition_snapshots`
- `v2_realtime_exhibition_snapshots`

Do not discard them merely because V4 Stage1 does not directly read them today. They may remain valuable research/training inputs. Preserve all necessary raw history externally before any online reduction.

#### `v2_v24_motor2_forward_shadow`

Current V4 core does not directly read this ~208 MB relation. It becomes a strong archive/delete candidate once a fresh dependency scan proves no active Production/research contract still requires it and its evidence has been archived where required.

## Legacy-only retirement sequence

The safe order is:

1. accumulate clean V4/Stage2 prospective evidence;
2. remove V4 S01-S05 carryover prospectively;
3. establish new-system ownership of required market data;
4. retire/replace the old PRE candidate-shadow producer;
5. retire/replace old FINAL decision/LINE chain;
6. retire old nightly shadow evaluation/report consumers;
7. run fresh code + Railway start-command zero-consumer scan;
8. freeze exact Production row/date/size inventory;
9. create and verify an independent recovery point/archive;
10. request explicit user approval for the bounded destructive Production step;
11. execute only the approved scope;
12. post-verify DB integrity, runtime health, disk use and Forward behavior;
13. only then decide Pro -> Hobby migration mechanics.

## Acceptance gates for Railway Hobby target

Do not downgrade just because the logical database is below 5 GB at one instant.

A safe Hobby readiness decision requires:

- post-cleanup actual data fits with meaningful headroom below the Hobby volume limit;
- expected daily growth has been measured;
- required live/raw evidence is still captured;
- no new-system model/read path depends on archived-only data during normal operation;
- restore instructions are proven;
- Production services are healthy after migration;
- no pending destructive operation remains necessary just to stay under the cap.

Target operating headroom should be chosen from measured growth, not from a fixed arbitrary number.

## Evidence separation

Never mix:

- historical/backtest data
- BASELINE Forward
- formal V4 prospective Forward
- Stage2 market support
- trio secondary research
- Production purchase evidence

Storage migration must preserve the provenance that keeps these evidence classes separate.

## Current decision

`COMPACT_NEW_SYSTEM_OWNERSHIP_DESIGN_APPROVED_FOR_RESEARCH / ARCHIVE_FIRST / NO_PRODUCTION_DATA_MOVE_YET / NO_DELETE_YET / NO_VACUUM_YET / NO_PLAN_DOWNGRADE_YET`
