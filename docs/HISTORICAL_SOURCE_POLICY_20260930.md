# Historical data source policy — 2026-09-30

Status: `APPROVED / ACTIVE / HISTORICAL_BACKFILL_ALLOWED / PROSPECTIVE_EVIDENCE_SEPARATE`

## User-approved direction

Historical data acquisition should proceed aggressively.

For historical backtests, the project adopts the practical convention that **the value that would have been available before the target race deadline is the correct value**.

This does not mean every value retrieved today may be pasted backward. Historical inputs must come from one of the accepted provenance classes below.

## Source precedence

### Tier A — BOAT RACE official target-day pre-race sources

Preferred primary source.

Examples:
- official archived racelist / race card;
- official program / syusso PDF;
- official program download data;
- racer period data when the applied period is fixed before the target race.

A target-day program/racelist archive is treated as `PREDEADLINE_BY_NATURE` for historical backtest use because it is the pre-race program for that target day.

Retrieval time may be later than the target day. The content contract, not the later HTTP retrieval timestamp, defines its historical role.

### Tier B — BOAT RACE official prior-only reconstruction

Prior race results may be used to reconstruct a target-day feature only when:
- every source event occurred before the target race deadline;
- the target race result is not read;
- the transformation is frozen before economic evaluation.

Examples:
- historical Opponent Pressure replay;
- applied-term Course proxy;
- rolling recent-form statistics built strictly from prior races;
- motor history aggregates calculated from prior uses only.

### Tier C — 艇国データバンク supplemental historical source

艇国データバンク is allowed as a secondary source within its published usage rules.

Mandatory request rules:
- >=3 seconds between accesses;
- known existing URLs only;
- one IP;
- do not repeatedly fetch css/js/images/favicon;
- do not use it to acquire program tables, race results, or racer-term data when BOAT RACE official download service provides those categories.

Allowed project roles:
- gap-filling for data categories not adequately available from official downloads;
- explicit historical ledgers with event dates;
- cross-checking official reconstruction;
- venue / motor / boat / course aggregate research when a valid historical cutoff can be proven or reconstructed.

A current aggregate page retrieved today is **not** a valid historical target-day feature. It is cross-check only unless an explicit historical as-of cutoff exists.

## Deadline convention

For each target race, accepted historical feature values must satisfy one of:

1. target-day pre-race program snapshot;
2. explicit source as-of timestamp/date before the target deadline;
3. deterministic reconstruction using only events strictly prior to the target deadline.

Rejected:
- target-race result-dependent values;
- current aggregates backcast into old races without an as-of proof;
- post-outcome recent-form reconstruction that includes the target event;
- threshold/feature searches that use target outcomes during feature construction.

## Evidence labels

Historical replay remains separate from prospective evidence.

Recommended labels:
- `HIST_PREDEADLINE_PROGRAM`
- `HIST_PRIOR_ONLY_RECONSTRUCTED`
- `HIST_TEIKOKU_SUPPLEMENT`
- `HIST_CROSSCHECK_ONLY`
- `PROSPECTIVE_CAPTURE`

A historical backtest can inform model design and data sufficiency, but it does not replace the V4 20-day / S03 100-observation prospective gates.

## Work already completed before this policy update

Official historical acquisition / reconstruction has already begun:
- official racelist missing-field backfill through 2025-07-21;
- historical Opponent replay for 2025-07 and 2025-08;
- historical applied-term Course proxy for 2025H2.

On 2026-09-30 the next batches were queued:
- entry backfill 2025-07-22..2025-07-28;
- entry backfill 2025-07-29..2025-08-04;
- entry backfill 2025-08-05..2025-08-11;
- Opponent replay 2025-09;
- Course proxy 2026H1.

## Safety boundary

Historical DB writes are for data acquisition / isolated historical shadow tables only.

Unchanged unless separately proposed:
- Production V4 accepted source/model contract;
- Production selector;
- coefficients;
- thresholds;
- LINE behavior;
- stake;
- purchase action.

`HISTORICAL_BACKFILL_ACTIVE / PREDEADLINE_BY_NATURE_ACCEPTED / PRIOR_ONLY_RECONSTRUCTION_ALLOWED / TEIKOKU_SUPPLEMENT_WITH_3S_RULE / TARGET_OUTCOME_LEAKAGE_FORBIDDEN / PROSPECTIVE_EVIDENCE_SEPARATE`
