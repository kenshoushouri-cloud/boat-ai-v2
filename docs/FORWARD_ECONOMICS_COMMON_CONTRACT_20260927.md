# Common prospective Forward economics contract — 2026-09-27

Status: `PURE / NO I/O / NO PRODUCTION CHANGE`

## Goal

Unify economic settlement semantics and reporting across prospective research tracks.

The common contract does **not** choose candidates or authorize promotion. It only evaluates already-frozen observations.

## Settlement semantics

### `evaluation_status = evaluated`
Counts economically:
- investment counts;
- hit/miss counts;
- return counts;
- included in ROI, drawdown, losing streak and bootstrap.

### `evaluation_status = invalid_result`
Void / cancelled / invalid:
- row remains in coverage;
- investment = 0 for economic reporting;
- return = 0;
- excluded from ROI denominator;
- excluded from losing streak and drawdown sequence.

### Other / missing status
Pending/unknown:
- row remains in coverage;
- investment = 0;
- excluded from economic metrics until officially evaluated.

This matches the existing Candidate Filter evaluator/report semantics and prevents the error of charging a 100 JPY loss to an invalid race.

## Input normalization

Candidate-shadow rows already carry `evaluation_status` and can enter the common evaluator directly.

Immutable V4 artifact settlement rows use `official` instead. The pure normalization adapter maps:
- `official=true` -> `evaluation_status=evaluated`;
- `official=false` -> `evaluation_status=invalid_result`;
- formal TOP1/TOP2 ticket count -> explicit investment per official race.

This allows V4 and S03/N02 research to share the same economic denominator and risk definitions without changing either evidence source.

## Unified outputs

- coverage: rows / evaluated / invalid_result / pending
- evaluated / hits / hit rate
- investment / return / profit / ROI
- largest hit / largest-hit share
- max drawdown / drawdown bets
- max losing streak
- chronological halves
- daily breakdown
- monthly breakdown
- deterministic whole-day bootstrap

Default bootstrap:
- 20,000 samples
- seed `20260927`

## Limits

This module must not:
- fetch DB data;
- fetch GitHub artifacts;
- read odds/results itself;
- write files/DB;
- tune thresholds;
- select subgroups;
- alter stake;
- authorize promotion;
- change Production;
- send LINE;
- buy.

`EVALUATED_ONLY_ECONOMICS / INVALID_RESULT_VOID / COMMON_RISK_METRICS / POLICY_NEUTRAL / PURCHASE_FALSE`
