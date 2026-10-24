# V4 course-entry error attribution preregistration — 2026-09-27

Status: `RESEARCH_ONLY / COMPLETED / ERROR_ATTRIBUTION_ONLY / NO_PREDICTOR_CHANGE`

## Question

Are current V4 daily-rank-1 first-place errors concentrated in races where the
official actual start course differs from the assigned boat/lane?

This is a causal-diagnostic step before proposing any new morning feature.
Actual start course is known only at/after the race start and is therefore
**forbidden as a predictor input** here.

## Frozen population

Replay the unchanged current V4 long-history contract for
`2025-07-01..2026-09-22`, 10 canonical blocks, source cutoff 08:15 JST.
Require the canonical 432 exact-six control days.

For each day's already-frozen control daily-rank-1 race, and only after the
selection is frozen:
- query the official result;
- query `v2_result_entries` with source `official_k_file`;
- require six lanes and a one-to-one actual start-course permutation 1..6.

## Frozen strata

Blocks 3–10 are the main diagnostic period.

Exactly these descriptive strata:
- no course change / any course change;
- predicted head boat did not move / moved from its assigned course;
- lane 1 not displaced / displaced;
- actual winner did not move / moved.

Metrics are count, head accuracy, multiclass LogLoss, and Brier.
No threshold search, coefficient fit, odds, EV, candidate filter, or Production
change is allowed.

## Interpretation

A large and directionally coherent error concentration would justify a separate
future hypothesis using **strictly prior** racer course-entry tendency as a
morning-safe predictor. It would not justify using actual course itself and would
not authorize Production.

If errors are not meaningfully concentrated in these strata, course-entry
uncertainty should not be promoted as the next missing-information direction.

`FREEZE_CURRENT_V4 / ACTUAL_COURSE_OUTCOME_DIAGNOSTIC_ONLY / RESULT_AFTER_SELECTION_FREEZE / NO_RETUNE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`


## Completed canonical diagnostic — 2026-09-27

Immutable evidence:

- trigger head: `239d312db7184dcc4a5b31c4435d9cb259f84262`
- workflow run: `36255242556` — SUCCESS
- artifact: `10910461830`
- artifact name: `v4-course-entry-error-36255242556`
- artifact ZIP SHA-256: `08a877607479a53a975b25ee25870c3e651e62af1defd56880ed30b617d5ca6c`
- result JSON SHA-256: `6e7058182e3ba458ae786bd9f91798bda030dabc1744ff0c47395cea839527a6`
- PostgreSQL transaction: READ ONLY
- actual start course used as predictor: **no**
- Production / LINE / purchase change: none / `purchase_action=false`

Coverage:

- calendar days: 449
- canonical exact-six control days: 432
- daily-rank-1 races with complete official six-course result card: 394
- blocks 3–10 complete-course daily-rank-1 races: 306
- complete-course unknown among otherwise evaluated control days: 38
- missing selected official result days: 17

### Blocks 3–10 diagnostic

| stratum | n | head accuracy | LogLoss | Brier |
| --- | ---: | ---: | ---: | ---: |
| all complete-course | 306 | 56.209% | 1.359214 | 0.664927 |
| no course change | 230 | 55.652% | 1.362583 | 0.665921 |
| any course change | 76 | 57.895% | 1.349021 | 0.661922 |
| predicted-head boat not moved | 287 | 57.143% | 1.354208 | 0.661912 |
| predicted-head boat moved | 19 | 42.105% | 1.434834 | 0.710478 |
| lane 1 not displaced | 304 | 55.921% | 1.361268 | 0.665890 |
| lane 1 displaced | 2 | 100.000% | 1.047048 | 0.518590 |
| winner not moved | 294 | 55.782% | 1.363889 | 0.666600 |
| winner moved | 12 | 66.667% | 1.244678 | 0.623939 |

### Interpretation

Broad actual course movement is **not** where current V4 head errors concentrate:
the `any_course_change` stratum is slightly better than `no_course_change` on
all three reported prediction metrics in this retrospective sample.

The only adverse-looking subgroup is when the boat that current V4 predicted to
win actually moved from its assigned course:
- 19 pure-evaluation races;
- head accuracy 42.105% vs 57.143% when that predicted-head boat did not move;
- LogLoss/Brier also worse.

That subgroup is too small and block-level behavior is not directionally stable:
some blocks worsen sharply, but others improve. It therefore does not justify a
broad course-change feature/filter, a venue/race-band exception, or a Production
change.

The lane-1-displaced and winner-moved strata are even smaller and are descriptive
only.

### Frozen conclusion

`GENERAL_COURSE_CHANGE_NOT_HEAD_ERROR_CONCENTRATION / PREDICTED_HEAD_MOVEMENT_SUBSET_WORSE_BUT_N19_UNSTABLE / DO_NOT_BUILD_BROAD_COURSE_CHANGE_FILTER / MORNING_COURSE_HEURISTIC_NOT_SUPPORTED_AS_NEXT_PRIMARY_PATH / PRIORITIZE_FROZEN_PRE_RACE_EXHIBITION_EVIDENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The next research direction should therefore prioritize already-frozen information
available close to the deadline (official beforeinfo / exhibition information)
rather than adding a broad morning course-entry heuristic.

Only this successful run is accepted as the diagnostic evidence.
