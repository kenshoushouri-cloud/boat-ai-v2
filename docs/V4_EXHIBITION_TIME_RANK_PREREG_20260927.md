# Current V4 exhibition-time-rank missing-information preregistration — 2026-09-27

Status: `RESEARCH_ONLY / PREREGISTERED / RETROSPECTIVE_OOS / NO_ODDS / NO_PRODUCTION_CHANGE`

## Why this is the next bounded hypothesis

The current V4 evidence chain has now ruled out several broader directions:

- input ablation did not support removing Course, Motor2, Opponent Pressure, or all enrichments;
- strict-prior official ST produced only a tiny fixed-race calibration movement and changed head correctness on 0/344 primary races;
- broad actual course movement was not where current V4 first-place errors concentrated;
- the already-frozen close-to-deadline Exhibition ST Forward adjustment was slightly adverse overall on proper scores and is not supported for promotion.

The remaining beforeinfo family with direct first-place plausibility and existing historical coverage is **exhibition time rank**. This experiment tests that family in the **current V4 model context**, not the old v22 or Bao model context.

## Frozen feature

Source:

- `v2_realtime_exhibition_snapshots`
- `snapshot_label='historical'`
- field: `exhibition_time_rank`

A race receives an exhibition adjustment only when all six lanes have a complete rank permutation 1..6. Otherwise the variant is exactly neutral and equals current V4 for that race.

For a complete race:

1. orient rank so a better exhibition rank is a higher score: `-rank`;
2. z-score across the six lanes;
3. add `coefficient * z` to the current V4 BASE raw lane strength;
4. then run the existing V4 Course, first-place Opponent Pressure, Motor2 and selector unchanged.

No exhibition course, start timing, tilt, weather, odds, payout, venue or race-number interaction is added.

## Frozen coefficient family

Exactly:

`0.00 / 0.05 / 0.10 / 0.20`

These values are preregistered here before the current-V4 replay result is read. Old v22 weight 0.20 and Bao exhibition coefficients are **not** treated as evidence for current V4 and are not copied as a chosen coefficient.

For each pure evaluation block 3–10:

- training data = control-fixed daily-rank-1 rows from strictly earlier canonical blocks only;
- only rows with complete six-lane exhibition ranks enter coefficient selection;
- objective = minimum mean first-place multiclass LogLoss;
- ties choose the smaller coefficient;
- the selected coefficient is frozen for the entire future block;
- no coefficient outside the four-point family may be tested after OOS results are seen.

Coefficient 0 is an explicit null. If training prefers 0, the experiment does not force an exhibition effect.

## Frozen population and chronology

Use the same current-V4 canonical long-history contract:

- period: `2025-07-01..2026-09-22`;
- 10 chronological blocks;
- require the canonical 432 exact-six control days;
- pure evaluation = blocks 3–10;
- current V4 Course=0.50, Opponent=1.0, Motor2=0.06, temperature=2.20;
- daily selector remains Top6 races / Top2 formal tickets.

For every target day, all four exhibition candidate distributions and selectors are built **before** target-day results are queried. Outcomes from an evaluation block are never available when that block's coefficient is chosen.

## Primary and secondary evaluation

### Track A — primary

Hold the current-control daily-rank-1 race fixed.

Compare current V4 versus the coefficient selected only from earlier blocks on:

- first-place Top1 accuracy;
- first-place multiclass LogLoss;
- first-place multiclass Brier.

Report both:

- `all`: intended neutral-missing behavior;
- `full6`: rows where the control rank1 race has complete exhibition ranks.

Formal Top2 trifecta hit/ROI is secondary only and cannot override worse proper scores.

### Track B — secondary

Allow the selected exhibition variant to rerun the current structural Top6 selector.

Report:

- first-place accuracy / LogLoss / Brier;
- rank1 overlap;
- Top6 overlap;
- formal Top2 only as a secondary descriptive measure.

No result-derived venue, race-band, date, availability or coefficient subgroup may be adopted.

## Frozen support gate

A historical result may advance only to a **new prospective first-write-wins Forward research shadow**, never directly to Production, and only if all are true on blocks 3–10:

1. Track A aggregate LogLoss improves;
2. Track A aggregate Brier improves;
3. Track A head accuracy improves;
4. Track A LogLoss improves in at least 6 of 8 pure evaluation blocks;
5. a positive coefficient is selected in at least 6 of 8 blocks;
6. Track B aggregate LogLoss does not worsen;
7. Track B aggregate Brier does not worsen;
8. Track B head accuracy does not worsen.

Failure of any gate means no current-V4 exhibition-time Forward promotion experiment from this replay.

## Historical-source limitation

The `historical` beforeinfo rows are retrospective copies of information that exists before race start. They are suitable for this bounded historical OOS question, but their database `snapshot_at` is not treated as proof that they were captured 8–15 minutes before deadline.

Therefore even a fully positive replay is **not** prospective evidence. It must be followed by a newly frozen first-write-wins capture using official beforeinfo before any Production review.

## Leakage / safety

- PostgreSQL transaction READ ONLY.
- No odds / EV.
- No DB writes.
- No candidate persistence.
- No LINE.
- No Railway Production setting changes.
- No purchase.
- `purchase_action=false`.
- Result/payout access occurs only after that day's control and all four candidate selectors are frozen.

`CURRENT_V4_BASE_FROZEN / EXHIBITION_TIME_RANK_ONLY / TRAIN_PRIOR_BLOCKS_ONLY / FOUR_POINT_GRID_FROZEN / ZERO_NULL_INCLUDED / RESULT_AFTER_ALL_VARIANT_FREEZE / NO_POST_RESULT_SUBGROUP / FRESH_FORWARD_REQUIRED_IF_POSITIVE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
