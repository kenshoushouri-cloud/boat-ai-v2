# Current V4 exhibition-time-rank missing-information preregistration — 2026-09-27

Status: `RESEARCH_ONLY / COMPLETED / RETROSPECTIVE_OOS / NO_ODDS / NO_PRODUCTION_CHANGE`

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


## Completed canonical replay

Canonical execution:

- trigger head: `6d5986f7889a8bb89cc0d32a95b2b1f50492bc0c`
- workflow run: `36288864737` — SUCCESS
- artifact: `10921393420`
- artifact name: `v4-exhibition-time-rank-oos-36288864737`
- artifact ZIP SHA-256: `8ddca8ff36a89452620a3a3e780ec959e8edfcc01f697f474145fbb98a92d33e`
- result JSON SHA-256: `99f4d32e2bbbddaa698767d434ed37e57b43d290752d72d92b3897bd4d915498`
- PostgreSQL: READ ONLY
- variable enumeration: 0
- collector execution: 0
- Production / LINE / purchase changes: none / `purchase_action=false`

Historical exhibition coverage was sourced entirely from
`official_beforeinfo_historical` rows; 373,230 lane rows were observed by the
read-only replay. This remains retrospective evidence, not prospective
capture-time proof.

### Frozen coefficient selection

The preregistered training-only selector chose coefficient **0.20** in every pure
evaluation block 3–10.

- positive coefficient blocks: 8 / 8
- Track A LogLoss-better blocks: 8 / 8
- the selected value was the upper edge of the frozen four-point grid in all
  blocks

The grid must **not** be expanded after seeing this result. A larger coefficient
is not an authorized follow-up on the same history.

### Track A — fixed current-V4 rank1 race, blocks 3–10

| model | days | head acc | LogLoss | Brier | formal Top2 | ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344 | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| exhibition time | 344 | 57.558% | 1.314880 | 0.643763 | 22.093% | 77.689% | -15,350 |

Primary proper-score deltas:

- LogLoss: **-0.025823**
- Brier: **-0.011450**
- head accuracy: **unchanged**
- predicted head changed: **0 / 344**
- control-wrong -> exhibition-right: **0**
- control-right -> exhibition-wrong: **0**

Complete-six exhibition subset:

- paired days: 308
- control LogLoss 1.352353 -> exhibition 1.323512
- control Brier 0.661857 -> exhibition 0.649069
- head accuracy 56.818% -> 56.818%

Thus the feature changes confidence/calibration materially, but on the fixed
current-V4 rank1 race it does **not** alter first-place classification at all.

### Track B — full variant reselection, blocks 3–10

| model | days | head acc | LogLoss | Brier | formal Top2 | ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344 | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| exhibition time | 349 | 62.464% | 1.278669 | 0.624626 | 21.490% | 73.109% | -18,770 |

Selector movement was substantial:

- common evaluable days: 343
- rank1 overlap: 52.770%
- mean Top6 overlap: 63.994%

Track B proper scores and head accuracy are descriptively better, while formal
Top2 economics are slightly worse. Because Track B changes the selected race
population and the preregistered primary Track A head-accuracy gate failed, this
secondary result cannot be used to rewrite the hypothesis or authorize a Forward
experiment.

### Frozen support gate

Passed:

- Track A aggregate LogLoss better
- Track A aggregate Brier better
- Track A LogLoss better in at least 6/8 blocks (actual 8/8)
- positive coefficient selected in at least 6/8 blocks (actual 8/8)
- Track B aggregate LogLoss not worse
- Track B aggregate Brier not worse
- Track B aggregate head accuracy not worse

Failed:

- **Track A head accuracy better**

Therefore the preregistered decision is:

`CURRENT_V4_EXHIBITION_TIME_CALIBRATION_SIGNAL_SUPPORTED / FIXED_RACE_HEAD_CLASSIFICATION_CHANGED_0_OF_344 / PRIMARY_HEAD_ACCURACY_GATE_FAILED / TRACK_B_RESELECTION_DESCRIPTIVELY_BETTER_BUT_NOT_PROMOTION_AUTHORITY / DO_NOT_EXPAND_COEFFICIENT_GRID / NO_NEW_FORWARD_FROM_THIS_REPLAY / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The canonical trigger SHA is hard-locked and the sentinel consumed. Do not rerun
or retune this experiment on the same history. A future exhibition-time study
would need a genuinely new preregistered question and, for promotion evidence,
fresh first-write-wins prospective data.
