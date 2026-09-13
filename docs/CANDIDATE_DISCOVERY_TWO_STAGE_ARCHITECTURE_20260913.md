# Candidate Discovery two-stage architecture — 2026-09-13

## Goal

Keep the Boat AI feed interesting and useful by producing a stable amount of prediction candidates without making EV or absolute odds the primary eligibility gate, while still using later race information when it becomes available.

## Stage 1 — V4 structural main feed

The main feed is the source of candidates.

Frozen core:
- 6 races/day;
- 2 exact-order trifecta tickets/race;
- V2-style equal-weight structural race ranking;
- Course neutral-missing coefficient `0.50`;
- Opponent Pressure `adj_win-base_win`, coefficient `1.0`, first-place-only;
- Motor2 beta `0.06`, position weights `1.0 / 0.6 / 0.3`;
- no EV gate;
- no absolute minimum/maximum odds gate.

Existing S01-S05 observations remain legacy/reference carryover while the new feed accumulates prospective evidence.

## Stage 2 — late Bao corroboration

This layer is **not an eligibility filter** and never deletes a Stage-1 candidate.

When a timing-safe post-exhibition market snapshot exists:
- require a coherent complete 120-ticket market snapshot after the exhibition observation and before deadline;
- de-vig the 120-ticket market to probability mass;
- Motor2 beta `0.06`;
- exhibition-time-rank beta `0.06`;
- ticket position weights `1.0 / 0.6 / 0.3`;
- create a late Bao top-ticket ranking;
- compare the late Bao top tickets with the already-frozen V4 tickets.

Output is annotation only:
- `corroborated=true/false`;
- overlap ticket(s);
- late Bao top ticket(s).

A Bao disagreement does not remove or replace a V4 race/ticket. This avoids returning to a low-volume candidate system.

## Why Bao is separate from V4

The robust exhibition-time evidence was established as residual information on top of a timing-safe market + Motor2 baseline. It was not established as a standalone coefficient directly additive to the structural V4 lane-strength model.

Therefore V4 remains market-independent for eligibility, and Bao remains a late independent corroboration layer instead of being forced into the V4 formula.

## Timing / immutability

Each observation has its own timestamped identity:
- Stage 1 candidate freeze cannot be rewritten after later exhibition/market data arrives;
- Stage 2 can add a later annotation but cannot change what Stage 1 originally predicted;
- race results must never be read until the candidate/refinement observation being evaluated has already been frozen.

The 2026-09-13 official first Forward freeze remains run `34726186753`; it is not retroactively converted to V4 or Bao.

## Purchase boundary

This architecture is a prediction system, not an automatic purchase system.

- `purchase_action=false`
- candidate availability is intentionally broader than purchase eligibility.
- any future staking/purchase layer is separate and may use diagnostics, but cannot rewrite frozen prediction evidence.

## Implementation status

Pure contracts:
- `research/candidate_discovery_v4_contract.py`
- `research/candidate_discovery_late_bao_contract.py`

Pure CI:
- `Candidate Discovery V4 Pure Contract`
- `Candidate Discovery Late Bao Pure Contract`

No Production selector, DB schema/write path, Railway config/Cron, LINE send, or purchase behavior is changed by this architecture document.

`TWO_STAGE_RESEARCH_ONLY / V4_TOP6_X_TOP2_MAIN_FEED / LATE_BAO_CORROBORATION_ONLY / NO_CANDIDATE_REMOVAL_BY_BAO / PURCHASE_ACTION_FALSE / NO_PRODUCTION_CHANGE`
