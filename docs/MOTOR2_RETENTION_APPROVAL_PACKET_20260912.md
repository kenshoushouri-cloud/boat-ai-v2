# Motor2 retention — future approval packet

Research-only design. This document does **not** authorize DELETE, VACUUM, backup creation, Railway/Cron changes, schema changes, model changes, LINE changes, or merge to Production behavior.

## Purpose

`v2_v24_motor2_forward_shadow` is currently the largest measured source of recent logical growth among the tracked Boat tables. The existing read-only retention contract has a zero-diff protected-output audit, so it is the first place where a bounded retention action can be studied without changing Production prediction inputs.

The objective of any future retention action is primarily **internal PostgreSQL page reuse / slower future file expansion**. Plain DELETE plus ordinary VACUUM must not be represented as guaranteed Railway-volume shrink.

## Measured recent effect

Read-only audit for completed dates 2026-09-05..2026-09-11, conservative `final/final` scope only:

- source rows: 29,711
- source logical tuple bytes: 28,039,984
- removable candidates: 14,578 rows
- candidate logical tuple bytes: 13,759,792
- removable share: 49.0660% of rows / 49.0720% of logical tuple bytes
- average candidate growth: 2,082.57 rows/day / 1,965,684.57 logical bytes/day
- unevaluated-protected rows in scope: 220

This is about 32.4% of the measured total Motor2 logical growth rate and about 12.8% of the measured logical growth across the ten tracked active tables. These percentages are prioritization evidence only, not a physical-volume reclaim forecast.

## Frozen keep contract

A row is preserved when any of the following is true:

1. its logical key `(race_id,ticket,run_class,window_name)` contains any unevaluated row;
2. it is the latest row for that logical key by `(snapshot_at,id)`;
3. it belongs to the latest valid PRE health snapshot group for its race.

Equal-latest ambiguity must remain zero. If ambiguity is non-zero, stop.

## Conservative first phase

Even if the broader contract identifies removable rows, a first approved action should be limited to:

- `run_class='final'`
- `window_name='final'`
- completed dates only (`race_date < current_date`)
- rows marked removable by the frozen keep contract

Manual, test, live-window and current-day rows remain untouched.

## Mandatory pre-action gates

Immediately before any future DELETE approval/execution:

1. Confirm Production is healthy and no incident/recovery is active.
2. Create a **fresh restorable backup** and verify its metadata. Backup creation itself requires explicit Production approval.
3. Re-run exact read-only Motor2 inventory.
4. Re-run protected-output invariance and require zero differences for Performance, Robustness PRE, Robustness FINAL and latest PRE health.
5. Re-run candidate preview and candidate SHA-256 digest. Never reuse an old digest as current truth.
6. Require protected-candidate intersection = 0 and ambiguous equal-latest keys = 0.
7. Record exact candidate row count/date range/digest in the approval message.
8. Require separate explicit approval for the DELETE itself.

Any failed or unavailable gate means **no mutation**.

## First execution boundary if later approved

The first execution should be one manually supervised bounded batch, not a new automatic Cron. The mutation should affect only the exact approved conservative candidate set and should fail closed if the live candidate count/digest no longer matches the approved preflight evidence.

After the mutation, verify:

- deleted row count equals the approved count;
- protected-output audits still show zero differences;
- current unevaluated rows remain present;
- latest-per-key rows remain present;
- latest valid PRE health groups remain intact;
- FINAL/PRE/LINE health is unchanged;
- PostgreSQL relation/dead-tuple stats are recorded.

Do not proceed to a second batch if any check fails.

## VACUUM / physical reclaim boundary

- DELETE alone creates dead tuples and does not guarantee physical volume reduction.
- Ordinary VACUUM can make space reusable internally but should be separately approved as a Production DB maintenance action under the project policy.
- `VACUUM FULL`, table rewrite, filesystem compaction or equivalent physical rewrite is a distinct high-impact action and is **not** part of this packet.

## Automation boundary

Do not create or modify Railway Cron for retention as part of the first execution. Only after at least one manually supervised action demonstrates the expected invariants should recurring retention be proposed separately with:

- explicit cadence and execution window;
- backup policy;
- maximum rows/bytes per run;
- digest/invariance fail-closed gates;
- alerting/reporting behavior;
- rollback/recovery procedure.

## Current decision

`RESEARCH_READY / MEASURED_RECENT_CANDIDATE_1.97MB_LOGICAL_PER_DAY / ZERO_DIFF_CONTRACT_REQUIRED / CONSERVATIVE_FINAL_FINAL_ONLY / FRESH_BACKUP_REQUIRED / LIVE_DIGEST_REQUIRED / FIRST_RUN_MANUAL_ONLY / NO_DELETE_AUTHORIZED / NO_VACUUM_AUTHORIZED / NO_CRON_AUTHORIZED / NO_PHYSICAL_REWRITE_AUTHORIZED`
