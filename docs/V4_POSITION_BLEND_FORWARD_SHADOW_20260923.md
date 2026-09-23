# V4 alpha=0.25 position-blend prospective shadow — preregistration 2026-09-23

Status: `PREREGISTERED_PROSPECTIVE_SHADOW / PURE_OFFLINE / NO_AUTOMATIC_PERSISTENCE / NO_PRODUCTION_CHANGE`

## Purpose

Historical work through 2026-09-22 found that a full learned position-conditional
tail replacement was too destructive for exact Top2 ranking, while a conservative
25% blend showed a small positive historical walk-forward signal.

That hypothesis was formed iteratively from historical results, so historical
performance is **not** sufficient for promotion. This document freezes the next
prospective test before any 2026-09-24-or-later result is used.

## Frozen challenger

The prospective shadow is fixed as:

`P_shadow(ticket) = 0.75 * P_current(ticket) + 0.25 * P_learned_tail(ticket)`

where:

- `P_current` is the unchanged current V4 120-ticket distribution;
- `P_learned_tail` preserves `P_current(first)` exactly;
- only `P(second | first)` and `P(third | first, second)` are supplied by the
  frozen pairwise-logit model;
- alpha is fixed at exactly `0.25`;
- model weights are frozen from the completed 2025-07-01..2026-09-22 historical
  training artifact and are not updated during this prospective shadow.

The embedded frozen weights come from:
- position-conditional tail run `35850876016`, artifact `10745542496`,
  JSON SHA-256 `7efaeff5b835494e0b8e4a76610b53a79734bf07a7e44a30541677969031078e`.

The alpha=0.25 hypothesis comes from:
- conservative blend run `35850876154`, artifact `10745995595`,
  JSON SHA-256 `817903cf704593171d4b93874d286fe0b110336c81775af642afa698d0720f5c`.

## Prospective start boundary

- historical training cutoff: **2026-09-22**
- preregistration date: **2026-09-23**
- first allowed Forward race date: **2026-09-24**

No race dated 2026-09-23 or earlier is admissible as prospective evidence.

## Two-phase evidence contract

### Phase A — pre-result freeze

The `freeze` command requires exactly six current formal races and accepts only:

- the current pre-result 120-ticket probability distribution;
- the six lane pre-result feature inputs used by the frozen tail model;
- race/date identifiers and a timezone-aware observation timestamp.

Any result/payout-like key causes fail-closed rejection. The output freezes:

- current Top2;
- alpha=0.25 shadow Top2;
- current and shadow first-place marginals;
- input SHA-256 and freeze SHA-256.

### Phase B — post-result settlement

The `settle` command accepts only a previously frozen artifact plus exactly six
matching official results. It verifies the freeze SHA before calculating metrics.
There is no post-result rerank, five-race shrink, replacement race, or later-date
substitution.

## Forward reporting

Report control and shadow on the same exact-six daily sets. Review cumulative evidence
at 30 / 50 / 100 settled races, without changing the challenger between checkpoints.

Primary research metric:
- exact formal Top2 hit rate.

Secondary diagnostics:
- ROI on the identical two-ticket stake;
- day/block consistency.

No automatic promotion threshold is defined by this PR. Any Production model or
coefficient change still requires explicit approval after prospective evidence review.

## Operational boundary

This PR intentionally contains **no**:

- database client;
- network client;
- Railway command;
- automatic cron/schedule;
- automatic Forward persistence;
- LINE action;
- purchase action.

It only freezes and evaluates user-supplied local JSON artifacts.

`ALPHA_025_FIXED / WEIGHTS_FROZEN_AT_2026_09_22 / EXACT_SIX / FORMAL_2_POINTS / PRE_RESULT_FREEZE / POST_RESULT_SETTLE / PURCHASE_FALSE`
