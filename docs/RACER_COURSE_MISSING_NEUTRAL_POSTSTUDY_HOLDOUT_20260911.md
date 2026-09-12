# Racer Course missing-row neutral fallback — post-study holdout check

Status: `PREREGISTERED_SENSITIVITY / RESEARCH_ONLY / NO_PRODUCTION_CHANGE`

This check is frozen after the broad 2026-07-15..2026-09-10 historical replay was observed, but **before inspecting the post-study subset metrics** defined below. It is a separate temporal sensitivity check and does not replace or retroactively alter the earlier preregistration or its status.

## Why this period

The previously established Course 0.50 research used data through **2026-08-24**. Therefore the fixed calendar period **2026-08-25 through 2026-09-10 inclusive** is selected solely because it starts after that prior study endpoint. No date inside this interval may be removed after outcomes are inspected.

## Fixed rule

Exactly reuse the already-frozen missing-row neutral rule without modification:

- BASE=current v24 PRE raw strength/probability logic.
- Course coefficient fixed at **0.50**; no coefficient search.
- Course feature is official racer-by-course Top3 only, lane=course.
- Course row must be exact race date, finite Top3 in `[0,100]`, created `<=08:15 JST` and strictly before race deadline.
- z-score timing-safe observed lanes only.
- missing/unusable lanes receive Course z=0; their BASE raw strength remains unchanged.
- fewer than two observed values or near-zero observed SD => all Course adjustment zero.
- no later snapshot repair, subgroup selection, venue/date exclusions, odds, payouts, ROI, or writes.

## Fixed sample and reporting

- Dates: **2026-08-25..2026-09-10**.
- exactly six entries.
- valid recorded trifecta result.
- report `ALL_ELIGIBLE`, `COMPLETE6`, and `MISSING1PLUS` separately.
- report observed Course-lane count distribution 0..6 and distinct dates/venues.

Metrics and uncertainty:
- LogLoss, Brier, actual-ticket rank; Top1/3/5/10 descriptive.
- deterministic race-level bootstrap, seed `20260911`, 5,000 resamples.
- negative deltas vs BASE are better.

## Predeclared sensitivity interpretation

`POSTSTUDY_HOLDOUT_SUPPORTS_FORWARD_SHADOW_REVIEW` requires:

- `MISSING1PLUS` >= 300 races and >= 10 distinct dates;
- MISSING1PLUS mean LogLoss, Brier and rank deltas <= 0;
- 95% bootstrap CI upper bound <= 0 for MISSING1PLUS LogLoss and Brier;
- ALL_ELIGIBLE mean LogLoss and Brier deltas <= 0.

Otherwise report `POSTSTUDY_HOLDOUT_DOES_NOT_SUPPORT` or `POSTSTUDY_HOLDOUT_INSUFFICIENT_SAMPLE`.

A pass still does not authorize Production. It permits only a separate forward-shadow implementation review. Opponent validation, Production promotion, LINE, BUY/WATCH/SKIP, and purchase behavior remain unchanged.
