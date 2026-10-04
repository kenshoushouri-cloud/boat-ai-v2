# Value Candidate Shadow — Execution Plan

Date: 2026-09-12 JST

## Objective

Determine whether the Boat AI can produce materially more low-stake opportunities by widening the odds universe and selecting on calibrated value, while keeping the existing Production method untouched.

## Phase 1 — historical opportunity map

Use existing historical rows only. No Production writes.

For every timing-safe historical ticket for which a pre-result probability can be reproduced, evaluate:

- odds band;
- model probability;
- break-even probability;
- value ratio (`prob * odds`);
- edge (`prob - 1/odds`);
- actual hit/result.

Primary report dimensions:

- month;
- venue;
- race number group;
- odds band;
- value gate;
- current Production-eligible vs current Production-ineligible.

## Phase 2 — compare candidate frequency

The main comparison is not only ROI. Report:

- candidates/day;
- candidates/month;
- zero-candidate days/month;
- total turnover at 100 yen/ticket;
- total turnover under race caps of 300/500/1000/2000 yen;
- profit/loss;
- ROI;
- longest losing streak;
- worst month;
- best month.

The current Production selector is the control arm. The shadow method must demonstrate a material opportunity-frequency gain without sacrificing out-of-sample profitability.

## Phase 3 — low-odds focus

Because the current Production range excludes odds below 3.0, explicitly evaluate:

1. 1.5-2.0 odds;
2. 2.0-3.0 odds;
3. 3.0-5.5 odds (current reference band);
4. above 5.5 odds.

A 2.0x ticket is acceptable research material when its calibrated hit probability makes it positive value. It must not be rejected solely because its payout is small.

## Phase 4 — monthly-profit feasibility

Evaluate whether a small-stake portfolio can plausibly target monthly profit in the tens of thousands of yen.

Do not assume the target is feasible. Report the actual combination of:

- candidate count;
- average stake;
- turnover;
- observed out-of-sample ROI;
- observed monthly profit distribution.

Reject any strategy whose apparent target profit depends on high per-race stake, rare jackpot months, or in-sample threshold tuning.

## Storage / Railway constraints

Production DB currently has limited remaining capacity, so this research must not increase persistent Production storage in a meaningful way.

Rules:

- no new Production tables;
- no persistent ticket-level shadow rows in Production;
- no duplicate odds storage;
- no new Production Cron;
- no new Railway service/volume;
- bounded read-only extraction only;
- compact aggregated output outside Production DB.

If a future forward shadow is needed, prefer bounded ephemeral/CI artifacts first. Any persistent Production shadow design requires a separate storage review and explicit approval.

## Promotion gate

A Production proposal may be prepared only after the method is validated out-of-sample and shows both:

- materially higher useful candidate frequency;
- positive and sufficiently stable ROI under small-stake assumptions.

Until then, the current Production strategy remains unchanged.
