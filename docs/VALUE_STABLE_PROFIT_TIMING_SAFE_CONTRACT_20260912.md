# A_STABLE / B_PROFIT Timing-Safe Audit Contract

Freeze date: 2026-09-12 JST

## Purpose

Re-evaluate the historical Phase-4 A_STABLE / B_PROFIT candidate rules using only a coherent 120-ticket odds snapshot that was fully observable at least 15 minutes before the race deadline.

This is a research-only retrospective timing-integrity audit. It is **not** a reconstruction of the current PRE notifier timestamp, because N01/A_STABLE is not currently persisted in the actual PRE Shadow. It also does not authorize any Production rule, timing, threshold, LINE, BUY, persistence, or purchase change.

## Frozen timing contract

- research period: 2026-08-25 through 2026-09-12
- source odds: `v2_realtime_odds_snapshots`
- snapshot identity: `(race_id, snapshot_label)`
- exactly 120 rows
- exactly 120 distinct tickets
- all 120 odds must be > 1.0
- timestamp spread within one label <= 60 seconds
- every row in the chosen label must be observable by `deadline_at - 15 minutes`
- choose the latest coherent label satisfying those rules

The 15-minute cutoff is fixed **before** the realized A/B result is inspected. It is intended to preserve operational decision time rather than maximize historical ROI. Do not move the cutoff after seeing results.

## Frozen candidate contracts

Both variants use `v24_pre_candidate_notifier_pg._rank_candidates` with the six stored race-entry rows and the chosen timing-safe odds map. The v24 ranking helper derives ticket probabilities from static race-entry fields and the supplied odds; it does not use settlement results.

### A_STABLE

- `prob_rank`: 11 through 25
- `market_rank`: 2 through 5
- observed odds: 3.0 <= odds < 6.0
- race number: 7 through 12
- if multiple tickets match, select maximum `raw_ev`, then maximum probability
- flat stake: 100 yen per selected race

### B_PROFIT

- `prob_rank`: 11 through 20
- `market_rank`: 2 through 5
- observed odds: 3.0 <= odds < 6.0
- race number: 7 through 10
- if multiple tickets match, select maximum `raw_ev`, then maximum probability
- flat stake: 100 yen per selected race

These are the existing Phase-4 definitions. No rank, odds, race-number, timing, venue, or date subgroup may be changed in response to this audit.

## Required reporting

For each variant report:

- timing-safe candidate count
- candidates per 30 calendar days
- evaluated / pending count
- hits and hit rate
- flat-100-yen investment, return, profit, ROI
- largest-hit share
- maximum losing streak and maximum drawdown
- calendar-month breakdown

Also report the number of race rows, coherent timing-safe labels, entry-ready races, result-ready races, and the minutes-before-deadline distribution of selected labels.

## Interpretation

Historical stored-odds Phase-4 performance is only a reference because those odds were not guaranteed to be the odds observable at the decision time. This audit is the timing-integrity gate for the existing A/B hypotheses.

A positive result is not sufficient for Production promotion. A separate prospective Forward freeze and explicit Production approval would still be required. A weak result must not be repaired by post-hoc threshold tuning.

## Guardrails

- database transaction is read-only
- no Production behavior change
- no DB persistence
- no Railway setting/Cron/service change
- no LINE send
- no BUY action
- no threshold/model coefficient change
- `purchase_action=false` remains unchanged
- `promotion_allowed=false`
