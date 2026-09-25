# V4 input-information ablation preregistration — 2026-09-25

Status: `RESEARCH_ONLY / PRE_RESULT / NO_ODDS / NO_RETUNE / NO_PRODUCTION_CHANGE`

## Question

Does any current V4 enrichment reduce first-place prediction quality or daily-rank-1
economics, and is the present weakness better explained by harmful information or
by missing information?

This preregistration deliberately tests removal before adding new data.

## Frozen variants

Exactly five variants are allowed:

1. `control` — current V4.
2. `no_course` — identical current V4 except Course top3 adjustment is neutralized.
3. `no_opponent` — identical current V4 except Opponent first-place delta is neutralized.
4. `no_motor` — identical current V4 except Motor ticket adjustment is neutralized.
5. `base_only` — Course, Opponent and Motor are all neutralized.

No coefficient is retuned. No alternative value of 0.50, 1.0, 0.06 or 2.20 is searched.

## Why two evaluation tracks are required

### Track A — fixed control race

For each evaluable day, freeze the current V4 six races and its daily-rank-1 race
before reading the result.

Recompute all five variants on that exact same control rank1 race.

This isolates whether an enrichment helps or hurts the prediction itself without
confounding the answer with a changed race selector.

Primary Track A metrics:

- Top1 first-place head accuracy.
- First-place multiclass log loss.
- First-place multiclass Brier score.

Secondary:

- formal Top2 trifecta hit rate;
- 2-point ROI and profit.

### Track B — full variant reselection

Before reading results, independently build each variant distribution for every
eligible race and run the unchanged V4 `select_daily` contract.

Each variant then evaluates its own daily-rank-1 race.

This captures the combined effect on prediction and the structural daily selector.

Primary/secondary reports include:

- Top1 head accuracy;
- head log loss and Brier;
- formal Top2 hit rate;
- ROI/profit;
- profitable-day rate;
- maximum drawdown;
- selected-race overlap versus control.

## Time split

Use the existing long-history period `2025-07-01..2026-09-22` and the existing
10 chronological blocks.

Report all-period results, but blocks 1-2 remain development/warm-up context.
The main historical comparison is blocks 3-10.

This is still retrospective research because the same history has already been
inspected in prior studies. Even a positive result is not promotion evidence and
must be followed by fresh prospective shadow evidence.

## Source and leakage contract

Reuse the long-history replay rules:

- source cutoff 08:15 JST;
- Course exact-date official snapshots created before cutoff/deadline;
- Opponent model-v2 rows with train_end before race date and created/updated
  before cutoff/deadline;
- Motor from the race entry;
- freeze all distributions/selections before result query;
- exact-six evaluated-day rule;
- no result-based replacement or shrink;
- PostgreSQL read-only transaction;
- no odds/EV;
- no DB writes, LINE, or purchase action.

## Interpretation rules

A layer is not called harmful merely because ROI rises after removal.

Evidence of a harmful prediction layer requires improvement in Track A first-place
accuracy and/or proper scoring rule, with block-level stability reported.

If removal does not improve Track A, but Track B improves, interpret the effect as
selector interaction rather than proof that the input itself is bad.

If no removal improves Track A consistently, the next hypothesis is missing
first-place information rather than current-enrichment noise.

No new feature is added in this experiment.

`FIXED_FAMILY / FIXED_RACE_ABLATION + FULL_RESELECTION / RESULT_AFTER_FREEZE / NO_RETUNE / PURCHASE_FALSE`

## Completed one-shot execution — 2026-09-25

Execution was performed exactly once after the frozen preregistration and replay
implementation validation were green.

Immutable evidence:

- trigger head: \`a40ea1d4858a87fd6fb230cb3ef4347331e69f19\`
- workflow run: \`36098761397\` — SUCCESS, attempt 1
- artifact: \`10847994618\`
- artifact name: \`v4-input-ablation-replay-36098761397\`
- artifact ZIP SHA-256: \`2a775d97c8ed4c1495f33772699bae6aa50234c83a51ff09c115ba7a7edd6368\`
- result JSON SHA-256: \`277927e9a9a66f12797168cf4c7af4bb91684ae84f5f4a6853e6f54e4447e779\`
- connection route: Railway \`railway run\` non-enumerating environment injection
- PostgreSQL transaction: READ ONLY
- result access: after all five variant distributions and selectors were frozen
- secret enumeration: 0
- replay attempts: 1
- Production/LINE/purchase change: none / \`purchase_action=false\`

Coverage:

- calendar days: 449
- control exact-six evaluated days: 432
- Track A: 432 days for every variant
- Track B: control 432 / no_course 433 / no_opponent 432 / no_motor 431 / base_only 431
- control blocks 3-10: 344 days
- Track A blocks 3-10 feature coverage: Course any 64 / Course full6 33 / Opponent 13 / Motor 334

### Track A — fixed control daily-rank-1, blocks 3-10

| variant | head acc | log loss | Brier | formal Top2 | 2pt ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| no_course | 57.558% | 1.361287 | 0.666295 | 21.512% | 75.901% | -16,580 |
| no_opponent | 57.558% | 1.340987 | 0.655305 | 21.512% | 75.131% | -17,110 |
| no_motor | 57.558% | 1.346750 | 0.657931 | 22.093% | 76.977% | -15,840 |
| base_only | 57.558% | 1.368635 | 0.669570 | 21.802% | 77.674% | -15,360 |

Primary interpretation:

- no ablation improves Top1 head accuracy;
- no ablation improves aggregate first-place LogLoss or Brier;
- removing Course worsens LogLoss by +0.020584 and Brier by +0.011083;
- removing Opponent worsens LogLoss by +0.000284 and Brier by +0.000093;
- removing Motor worsens LogLoss by +0.006047 and Brier by +0.002719;
- base_only is worse by +0.027932 LogLoss and +0.014358 Brier.

Course support appears only in control blocks 9-10; Course removal worsens both proper
scores in both covered blocks. Opponent support appears only in block 10; Opponent
removal worsens both proper scores there. Motor removal improves LogLoss in only one
of eight pure-evaluation blocks and improves Brier in none.

The modest secondary Top2/ROI gains for no_motor/base_only do **not** establish a
harmful head layer because the preregistered primary fixed-race proper scores worsen.
They are treated as ticket-order/payout behavior, not a reason to remove information.

### Track B — full variant reselection, blocks 3-10

| variant | days | head acc | log loss | Brier | formal Top2 | 2pt ROI | profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 344 | 57.558% | 1.340703 | 0.655212 | 21.512% | 75.131% | -17,110 |
| no_course | 345 | 55.072% | 1.381045 | 0.675081 | 19.710% | 71.710% | -19,520 |
| no_opponent | 344 | 57.849% | 1.341217 | 0.654580 | 21.221% | 74.288% | -17,690 |
| no_motor | 343 | 55.977% | 1.367021 | 0.667312 | 20.991% | 71.370% | -19,640 |
| base_only | 343 | 54.227% | 1.390198 | 0.680224 | 20.408% | 75.233% | -16,990 |

Selector overlap versus control across common evaluable days:

- no_course: rank1 91.204%, mean Top6 91.667%
- no_opponent: rank1 98.611%, mean Top6 99.498%
- no_motor: rank1 67.209%, mean Top6 77.791%
- base_only: rank1 61.538%, mean Top6 72.145%

Removing Course or Motor materially worsens the combined prediction+selector path.
The tiny no_opponent Track B head/Brier movement is not stable evidence for removal:
it is confined to the sparse Opponent-covered tail, LogLoss/Top2/ROI worsen, and
Track A does not show a prediction-layer benefit from removal. It is therefore
interpreted as selector interaction, not proof that Opponent information is harmful.

### Frozen conclusion

\`NO_HARMFUL_INPUT_REMOVAL_SUPPORTED / CURRENT_HEAD_CLASSIFICATION_UNCHANGED_BY_ABLATION / COURSE_AND_MOTOR_IMPROVE_FIXED_RACE_PROPER_SCORES / OPPONENT_EFFECT_TOO_SPARSE_BUT_REMOVAL_NOT_SUPPORTED / MISSING_FIRST_PLACE_INFORMATION_IS_NEXT_HYPOTHESIS / NO_PRODUCTION_CHANGE / PURCHASE_FALSE\`

This remains retrospective development evidence on repeatedly inspected history.
It does not authorize removal/addition of a Production feature, coefficient changes,
selector changes, or promotion. Any new missing-information hypothesis must be
preregistered and ultimately requires fresh prospective shadow evidence.

