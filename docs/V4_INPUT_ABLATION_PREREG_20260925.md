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
