# V5.1 Exhibition Time minimal-cost OOS backfill plan — 2026-10-04

Status: PLAN ONLY / NO BACKFILL EXECUTED

## Objective
Fill only the 4,703 OOS races missing six-lane Exhibition Time. Do not broaden this operation to weather or other beforeinfo fields.

## Read-only planning evidence
Run `37190834004` / artifact `11299500355`.

- OOS races: 14,514
- Exhibition-Time missing: **4,703**
- current generic beforeinfo HTTP target: **12,424**
- extra HTTP caused by other missing fields: **7,721**
- Exhibition-Time-only saves **~62.15%** of HTTP requests.
- 0.50s/request sleep floor: generic **103.53 min** vs targeted **39.19 min**.

Monthly targeted counts:
- 2026-07: **53**
- 2026-08: **2,086**
- 2026-09: **2,564**

## Storage / Railway
candidate-v4 volume: 5,000 MB.
Observed disk: current ~4.670 GB, 24h max ~4.769 GB.

Historical exhibition table:
- 385,782 historical rows
- avg row payload ~217.5 bytes
- relation size ~140.05 MB

Worst case:
- 28,218 new rows
- payload ~6.14 MB
- relation-size extrapolation ~10.2 MB before transient WAL/maintenance overhead

The volume margin is not large enough for an uncontrolled broad campaign. Check disk/WAL after every batch.

## Minimum-cost implementation
Before any write:
1. add explicit `exhibition-time-only` mode;
2. target only historical races with six-lane exhibition_time incomplete;
3. write only `v2_realtime_exhibition_snapshots`;
4. do not fetch/write weather for this task;
5. target `postgres-hobby-fullhistory-candidate-v4`, not stale `postgres-recovery`;
6. preserve existing non-null values and fill missing only;
7. keep 0.50 sec/request;
8. no result/odds/payout reads, no LINE/purchase/Production-model changes.

## Execution order after safety tests
1. July pilot 2026-07-01..31 — expected HTTP target **53**.
2. Recheck coverage, disk and WAL.
3. August 2026-08-01..31 — expected **2,086**.
4. Recheck disk/WAL.
5. September 2026-09-01..30 — expected **2,564**.
6. Final readiness audit.

If the actual target count materially differs, stop before writes.

## Implementation status
Completed in PR `#544`, merged as `0e9dc77127eb38ccfa47a009e70f492879cb95f4`.

Safety run `37192162162`:
- validate: SUCCESS
- candidate-v4 July plan-only: SUCCESS
- July target: **53**
- HTTP requests: **0**
- DB writes: **0**
- actual backfill job: SKIPPED

The dedicated mode writes only Exhibition Time / rank / diff and does not parse/write weather or fill ST/tilt/course.

## Next ONE task
Run the **July 53-race pilot only**, then recheck coverage, disk and WAL before any August work.

`EX_TIME_ONLY_IMPLEMENTED / JULY_53_PILOT_NEXT / CHECK_DISK_WAL_AFTER_PILOT / NO_AUG_UNTIL_PASS`
