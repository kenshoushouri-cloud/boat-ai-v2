# Opponent Pressure v2 — timing-safe Railway Cron migration plan

Date: 2026-09-11
Status: **PLAN ONLY / NO PRODUCTION CHANGE**

## Objective

Make the existing fixed Opponent Pressure v2 research feature available as trustworthy Forward input before the fixed 08:15 JST source boundary, without changing its coefficient (`1.0`) or Production prediction routing.

## Why migration is required

The current GitHub Actions workflow nominally schedules at 07:15 JST but its actual scheduled starts have often been delayed. In the audited 2026-08-25..2026-09-10 shadow rows:

- 15 dates / 2,256 rows
- only 2 dates were created by 08:15 JST
- 1,932 rows were created after 08:15 JST
- 183 rows were created at/after their race deadline

The schedule mechanism is therefore not suitable evidence for a strict pre-08:15 Forward contract.

## Upstream readiness observed on 2026-09-11

Production Railway `cron-data-prepare` currently runs at 06:30 JST (`30 21 * * *` UTC).

The 2026-09-11 natural run:

- started at about 06:30:42 JST
- saved 144 races / 864 race-entry rows
- completed the relevant daily preparation by about 06:53:19 JST
- had 0 race-preparation failures

The Opponent Pressure calculation uses today's `v2_races` / `v2_race_entries` plus historical `v2_result_entries` strictly before `TARGET_DATE`. It does not depend on the 07:15 Racer Course collector.

## Proposed scheduler

Preferred candidate after explicit approval:

- platform: Railway Cron
- proposed service name: `cron-opponent-pressure-v2`
- proposed cron: `0 22 * * *` UTC = **07:00 JST**
- source: `kenshoushouri-cloud/boat-ai-v2` main
- restart policy: NEVER
- target date: current JST date

Rationale: 07:00 is after today's observed 06:53 daily-preparation completion and leaves 75 minutes before the fixed 08:15 cutoff. The service must still fail closed if preparation is late on a future day.

## Mandatory execution contract

The Railway job must not simply call the existing writer. A guarded entrypoint is required with this order:

1. Resolve `TARGET_DATE` in JST.
2. Read-only preflight: require target races > 0 and exactly six valid class/lane entries for every race.
3. Require all race deadlines to be present.
4. Before scoring, require current JST date = `TARGET_DATE` and current time <= 08:15.
5. Run the existing fixed v2 scoring logic with no coefficient or feature tuning.
6. Immediately before any commit, re-check current JST time <= 08:15 and require write time < each race deadline.
7. Write an immutable observation/run identity where practical. If the existing mutable table is retained temporarily, both `created_at` and `updated_at` must be validated by every Forward consumer.
8. Verify postconditions: expected row count, model_version=2, train_end=target-1 day, six-array shapes, matched_opponents >=4 for all six lanes.
9. Any failed precondition/postcondition => no Forward eligibility; no stale previous-day fallback.

## Coexistence / cutover

The GitHub Actions schedule must not remain as an uncontrolled second writer after Railway is proven. A safe cutover should be staged:

1. Add Railway collector in research/shadow-only mode; Production prediction routing remains unchanged.
2. Observe at least 5 consecutive natural days with all intended Opponent rows created by 08:15 and before race deadlines.
3. During observation, keep the fixed coefficient 1.0 and do not tune based on outcomes.
4. After natural-run gate passes, separately review disabling the GitHub scheduled writer and enabling any combined Production consumer.
5. Production combined routing is a separate approval from scheduler migration.

## Existing staged Railway patch warning

The Production environment currently reports staged patch `babf0d2c-fba1-4157-b55b-1ca668e9a03e` with a large environment-level staged change count. **Do not accept/apply that staged patch as part of this migration.** Any future Railway change must first verify that the requested operation does not unintentionally commit unrelated staged changes.

## Approval boundaries

Explicit approval is required before any of the following:

- creating the Railway service
- changing/adding a Railway Cron schedule
- changing Production variables/configuration
- disabling the GitHub scheduled writer
- merging Production-affecting collector changes
- enabling Course + Opponent in Production prediction routing

This document and PR are research/preparation only.