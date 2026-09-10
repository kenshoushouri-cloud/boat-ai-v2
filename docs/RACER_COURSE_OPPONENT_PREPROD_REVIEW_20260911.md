# Racer Course + Opponent Pressure pre-production review — 2026-09-11

## Scope

This is a research-only review of the fixed combination:

- Racer Course Top3 coefficient: `0.50`
- Opponent Pressure coefficient: `1.0`

No Production prediction logic, BUY/WATCH/SKIP rule, LINE behavior, Railway configuration/variables/Cron, coefficient, threshold, or purchase behavior is changed by this review.

## 2026-09-11 Racer Course natural Cron

The natural Railway Cron completed successfully.

- target racers: 530
- success racers: 518
- partial racers: 22
- failed racers: 12
- saved rows: 3,045
- racer coverage: 97.7%
- failed samples: all `no_usable_metrics`
- target races: 144
- races with six entries: 144
- six-lane Course Top3 timing-safe: 117/144 = 81.25%
- fail-closed races: 27
- partial-slot additional race rescue on this date: 0

This establishes useful live source readiness for Racer Course on this date, while retaining fail-closed behavior for the 27 incomplete races.

## 2026-09-11 Opponent Pressure readiness

A Production-PostgreSQL read-only audit run at approximately 07:57 JST found:

- target races: 144
- race deadlines available: 144
- Opponent Pressure v2 rows present: 0
- missing: 144
- timing-clean combined-input races: 0/144

Verdict at that observation point:

`BLOCK_OPPONENT_ROWS_INCOMPLETE`

Therefore the fixed Course 0.50 + Opponent 1.0 combination is **not live-source-ready** for 2026-09-11 at the pre-production decision boundary, even though the Racer Course source itself is ready for 117 races.

## Historical Opponent Pressure timing audit

Read-only audit window: 2026-08-25 through 2026-09-10.

- dates with rows: 15
- rows: 2,256
- rows created after fixed 08:15 JST cutoff: 1,932
- rows created at/after race deadline: 183
- rows later mutated (`updated_at > created_at`): 0
- cases where `created_at` was safe but a later `updated_at` crossed the cutoff: 0
- cases where `created_at` was safe but a later `updated_at` crossed the race deadline: 0

Observed batch creation times:

| race date | rows | after 08:15 | at/after deadline | created JST |
|---|---:|---:|---:|---|
| 2026-08-25 | 156 | 0 | 0 | 07:44:06 |
| 2026-08-26 | 168 | 0 | 0 | 07:44:41 |
| 2026-08-27 | 156 | 156 | 46 | 12:17:57 |
| 2026-08-28 | 144 | 144 | 89 | 15:06:44 |
| 2026-08-31 | 144 | 144 | 8 | 09:36:35 |
| 2026-09-01 | 144 | 144 | 9 | 10:17:55 |
| 2026-09-02 | 156 | 156 | 4 | 09:13:12 |
| 2026-09-03 | 168 | 168 | 4 | 09:15:13 |
| 2026-09-04 | 156 | 156 | 3 | 09:05:42 |
| 2026-09-05 | 168 | 168 | 3 | 09:04:57 |
| 2026-09-06 | 144 | 144 | 2 | 08:53:55 |
| 2026-09-07 | 144 | 144 | 2 | 08:53:35 |
| 2026-09-08 | 132 | 132 | 5 | 09:24:55 |
| 2026-09-09 | 144 | 144 | 4 | 09:14:08 |
| 2026-09-10 | 132 | 132 | 4 | 09:14:15 |

Only 2 of the 15 observed dates met the fixed 08:15 cutoff. The remaining 13 dates missed it. The principal operational blocker is therefore **late initial creation**, not an observed late overwrite.

## Mutable-upsert contract

The current Opponent Pressure v2 collector writes with an `ON CONFLICT (race_id) DO UPDATE` contract and stores both `created_at` and `updated_at`.

No empirical row mutation was observed in the audited 2,256 rows, but the table remains structurally mutable. A future rerun could change a row while preserving an earlier `created_at`. A Production-eligible loader must therefore never treat `created_at` alone as sufficient timing evidence.

Before Production use, one of the following is required:

1. Prefer an immutable/append-only snapshot contract keyed by race plus observation/run identity; or
2. at minimum require both `created_at` and `updated_at` to be at or before the source cutoff and strictly before the race deadline, with any later update failing closed.

## Interpretation of prior combined Forward evidence

The previous fixed Course 0.50 + Opponent 1.0 research evaluation remains useful model evidence:

- timing-clean common sample: 1,144 races
- combined vs Course LogLoss delta: -0.02814106
- Brier delta: -0.00082388
- winner-rank delta: -0.4685
- paired-bootstrap 95% CIs excluded zero for all three metrics

That evidence does **not** establish that the current live Opponent collection schedule can reliably produce inputs before the required 08:15 decision boundary. Model quality evidence and operational source-readiness evidence must remain separate.

## Required remediation before promotion review

Recommended pre-production contract:

1. Run Opponent collection from a scheduler that can be relied upon to complete materially before 08:15 JST. The current GitHub Actions scheduled job has repeatedly produced rows after 08:15 and sometimes after race deadlines.
2. Add an in-process hard guard: if the observation/write time is after 08:15 JST, do not create a Forward-eligible snapshot.
3. Preserve immutable timing evidence, preferably append-only. If mutability is retained, require both `created_at` and `updated_at` to pass cutoff/deadline checks.
4. A combined loader must require timing-clean Racer Course and timing-clean Opponent inputs for the same race. Missing/late Opponent data must fail closed and must not silently use a stale day.
5. Do not alter current Production v24 fallback behavior as part of this research PR. Any Course-only fallback or combined Production routing requires a separate explicit approval.
6. After remediation, require at least **5 consecutive natural operating days** with Opponent rows available by 08:15 JST and before race deadlines before reopening Production promotion review.

No scheduler change is made by this PR. Moving the job to Railway Cron or another deterministic scheduler is a Production/operations change and requires explicit approval.

## Decision

`BLOCK_OPPONENT_SOURCE_TIMING / NO_PRODUCTION_CHANGE`

The fixed combined model remains promising research, but Production promotion is blocked until Opponent Pressure collection timing is made operationally reliable and then validated on natural runs.