# A_STABLE / B_PROFIT `final_ab` Timing-Safe Contract

Freeze date: 2026-09-12 JST

## Why this contract exists

The separately frozen deadline-minus-15-minute audit found only 21 complete 120-ticket races out of 2,880 races and produced no A_STABLE/B_PROFIT candidates. That result shows that a 15-minute lead is not representative of the current realtime odds collection architecture.

Production FINAL already uses `snapshot_label=final_ab` as its decision label on a 15-minute Cron. This contract therefore evaluates the unchanged historical Phase-4 A/B definitions against the actual `final_ab` source, while still rejecting any snapshot whose full 120-ticket set was not captured before the race deadline.

This is research only. It does not change FINAL logic, Cron, LINE, BUY, thresholds, model coefficients, or persistence.

## Frozen timing/source contract

- research period: 2026-08-25 through 2026-09-12
- odds table: `v2_realtime_odds_snapshots`
- snapshot label: exactly `final_ab`
- exactly 120 rows and 120 distinct tickets per race
- every odds value > 1.0
- timestamp spread across the label <= 60 seconds
- the last of the 120 ticket timestamps must be `<= deadline_at`
- no use of `learning_all` for candidate ranking

No minimum lead-time threshold is introduced in this contract. The observed minutes-to-deadline distribution is reported as a safety/operability diagnostic, not tuned against ROI.

## Frozen candidate contracts

The candidate definitions are unchanged from historical Phase-4 research and from the earlier 15-minute contract.

### A_STABLE

- probability rank: 11..25
- market rank: 2..5
- odds: 3.0 <= odds < 6.0
- race number: 7..12
- when multiple tickets match: maximum `raw_ev`, then maximum probability
- flat 100 yen accounting

### B_PROFIT

- probability rank: 11..20
- market rank: 2..5
- odds: 3.0 <= odds < 6.0
- race number: 7..10
- when multiple tickets match: maximum `raw_ev`, then maximum probability
- flat 100 yen accounting

The ranking helper is `v24_pre_candidate_notifier_pg._rank_candidates`, using stored race-entry fields and the timing-safe `final_ab` odds map. Settlement results are read only after the candidate is selected.

## Required reporting

For each rule report candidate count, 30-day-equivalent count, evaluated/pending, hits, ROI, profit, largest-hit share, maximum losing streak, maximum drawdown, monthly split, and overlap between A and B. Also report complete `final_ab` coverage and the minutes from the final ticket timestamp to deadline.

## Interpretation guard

A strong retrospective result does not authorize Production promotion. If this contract shows adequate volume and non-fragile evidence, the next step is a separately named prospective Forward freeze starting after 2026-09-12. Any new threshold/rank/odds/race-number/timing variant requires a new name and prospective start.

- database read-only
- no Production behavior change
- no Railway/Cron/service change
- no LINE send
- no BUY action
- no new Production persistence
- `purchase_action=false` unchanged
- `promotion_allowed=false`
