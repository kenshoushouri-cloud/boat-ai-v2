# V4 position-conditional conservative blend walk-forward — 2026-09-23

Status: `ITERATIVE_RESEARCH / READ_ONLY_DB / CURRENT_SIX_FIXED / FIRST_PLACE_MARGINAL_FIXED / PAST_ONLY_ALPHA / NO_PRODUCTION_CHANGE`

## Why this study exists

The corrected position-conditional model improved conditional second-choice accuracy
on unseen blocks but reduced exact Top2 accuracy when it fully replaced the current
tail distribution.

That suggests the learned signal may be useful but too destructive as a full
replacement. This follow-up tests only a conservative convex blend.

Because this hypothesis was formed after observing earlier historical results, this
study is explicitly **iterative historical hypothesis refinement**. Even a positive
result is not pristine promotion evidence and can only nominate a prospective shadow.

## Fixed alpha family

Five blend levels are fixed in source:

- alpha 0.00 = exact current control;
- alpha 0.25;
- alpha 0.50;
- alpha 0.75;
- alpha 1.00 = full learned conditional tail.

For every ticket:

`P_blend = (1-alpha) * P_current + alpha * P_learned`

Both endpoints preserve the same current first-place marginal, therefore every blend
also preserves current P(first) exactly.

## Strict past-only alpha policy

The calendar is split into the same 10 chronological blocks.

- block 1 is model warm-up only;
- block 2 is forced to alpha=0 because there is no prior unseen blend evidence;
- before block 3 and later, choose alpha using only cumulative candidate results from
  earlier unseen blocks;
- primary choice metric is exact Top2 hit rate;
- tie-break is lower mean log loss, then smaller alpha;
- all five candidate Top2 sets for the current day are frozen before result access;
- the current block is added to alpha-selection history only after it is evaluated;
- model training likewise happens only after block completion.

Thus neither the current block nor any future block chooses its own alpha.

## Interpretation boundary

ROI is secondary only. Historical success cannot authorize Production changes.

No result from this study can directly change:

- Production model or coefficients;
- six-race selector or candidate count;
- two-ticket formal count;
- stake, LINE, or purchase behavior.

A positive result would require a separately preregistered prospective shadow.

`CONSERVATIVE_BLEND / PAST_ONLY_ALPHA / FIRST_PLACE_MARGINAL_PRESERVED / CURRENT_SIX_FIXED / FORMAL_2_POINTS / NO_RETUNE / PURCHASE_FALSE`
