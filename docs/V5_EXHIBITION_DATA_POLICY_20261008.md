# V5 Exhibition Data Policy — 2026-10-08

## Decision

V5 may use **exhibition_time_rank** as a model-input candidate, under the rules below.

## Historical evaluation

- Historical rows whose source is `official_beforeinfo_historical` or
  `official_archived_beforeinfo_historical_reconstruction` may be used as
  retrospective pre-race truth for backtesting.
- The historical collectors fetch BOAT RACE official `beforeinfo` pages for
  the target date / venue / race number and parse exhibition information.
- Historical reconstruction timestamps are **not** prospective timing evidence.
- No target-race result, payout, or odds may be used to construct exhibition
  features.

## Operational deployment evidence

- Deployment must rely on genuinely captured pre-deadline snapshots.
- Frozen forward evidence currently confirms 278 safe observations across
  2026-08-23..2026-08-25, 16 venues, captured about 8.3–14.8 minutes before
  deadline, with zero timing/source/completeness/rank violations.
- Continue first-write-wins pre-deadline capture in production research/shadow
  so prospective evidence grows.

## Current V5 evidence

- `exhibition_time` raw exact-value incremental over lane+class: HOLD
  (essentially no gain in the fixed exact-value EB formulation).
- `exhibition_time_rank` incremental over lane+class: strong KEEP candidate.
  - delta LogLoss: -0.0147264358
  - delta Brier: -0.0055083422
  - Brier improved at 24/24 venues; LogLoss at 22/24.
- Frozen forward rank test on 278 safe snapshots:
  - delta LogLoss: -0.0175890434
  - delta Brier: -0.0060600421

## Guardrail

Historical backtest evidence and prospective timing evidence must remain
separate. Promotion to Production requires the live pre-deadline collection
path; synthetic historical timestamps must never be treated as proof of live
availability.
