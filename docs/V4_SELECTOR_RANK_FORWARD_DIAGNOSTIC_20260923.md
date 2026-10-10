# Candidate Discovery V4 selector-rank Forward diagnostic — 2026-09-23

Status: **RESEARCH ONLY / FORWARD DIAGNOSTIC ONLY / NO SELECTOR CHANGE / FORMAL 2 POINTS UNCHANGED**

## Why this exists

PR #376 narrowed the ticket-count question to formal 2 points versus a 3-point
shadow comparison. Increasing ticket count did not solve the historical
profitability problem.

The next research priority is therefore race selection / probability ranking
quality.

Current V4 Stage 1 selects the daily top six races by a relative structural
score. The score is the mean of same-day percentile ranks for:

- first-place probability (\`head_p1\`);
- first-place margin (\`head_margin\`);
- top-three ticket mass (\`top3_mass\`);
- distribution concentration (\`concentration\`).

There is no absolute Stage-1 confidence threshold. This document does **not**
add one.

## Immutable historical context

The hypothesis is generated only from immutable PR #376 evidence:

- workflow run: \`35806246724\`;
- artifact ID: \`10727519397\`;
- artifact ZIP SHA-256:
  \`426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771\`;
- formal comparison stake: two tickets per selected race, 100 JPY each;
- selection and ticket ranking were frozen before result/payout reads.

The frozen context is recorded in
\`research/evidence/v4_selector_rank_historical_context_20260923.json\`.

### Directional observation

Fixed OOS, 2026-07-01 through 2026-08-15:

- daily ranks 1-3: ROI 79.203%;
- daily ranks 4-6: ROI 65.797%;
- difference: +13.406 percentage points;
- 20,000-resample day-cluster bootstrap 95% interval:
  **[-20.072, +47.320] pp**.

Recent timing-safe, 2026-09-11 through 2026-09-22:

- daily ranks 1-3: ROI 54.333%;
- daily ranks 4-6: ROI 36.333%;
- difference: +18.000 percentage points;
- 20,000-resample day-cluster bootstrap 95% interval:
  **[-43.500, +77.167] pp**.

The direction repeats, but both uncertainty intervals cross zero. This is not
evidence to reduce the daily candidate count.

## Absolute race-score check

Using score quartiles fixed from the OOS score distribution, formal two-point
ROI is non-monotonic in both windows. Therefore the historical evidence does
not support a \`race_score\` cutoff.

No score threshold is preregistered here.

## Forward diagnostic contract

Future exact-settled formal V4 rows may be passed to
\`research/v4_selector_rank_forward_diagnostic.py\` only after the exact formal
six-race set is immutable and exact same-date outcomes are final.

Every accepted day must contain:

- exact source contract \`candidate_discovery_v4_main_feed_v1\`;
- \`source_prospective_evidence_eligible=true\`;
- exactly six formal races;
- unique daily ranks 1 through 6;
- the already-frozen \`race_score\`;
- the already-frozen formal top two tickets;
- exact same-date official trifecta outcome and payout;
- \`purchase_action=false\`.

The diagnostic reports:

- formal two-point economics by daily rank 1..6;
- rank 1-3 versus rank 4-6 economics;
- largest-hit concentration;
- deterministic day-cluster bootstrap uncertainty.

It does **not**:

- reconstruct a race or ticket after results;
- replace a missing/cancelled race;
- shrink six races to five;
- rerank candidates;
- define an absolute score gate;
- change candidate count;
- change point count;
- change a threshold, coefficient, stake, LINE behavior, or purchase behavior.

## Milestone separation

This diagnostic does not redefine any existing project 30/50/100 case
milestone. Formal settled-race counts, Stage-2 supported cases, and other
preregistered prospective case definitions remain separate evidence streams.

Any later selector hypothesis must be preregistered separately before the
outcomes used to validate it. Historical diagnostics may generate a hypothesis;
they may not both define and validate a Production selector change.

## Promotion boundary

No Production selector change is authorized by this Draft.

A future change to daily race count, absolute confidence threshold, selector
formula, ranking weights, or any other candidate logic remains a separate
Production-effect change requiring explicit user approval.

Frozen decision:

\`DIRECTIONAL_RANK_HALF_SIGNAL / UNCERTAINTY_CROSSES_ZERO / SCORE_GATE_NOT_SUPPORTED / FORMAL_2_POINTS_UNCHANGED / SIX_RACES_UNCHANGED / FORWARD_DIAGNOSTIC_ONLY / NO_RETUNE / PURCHASE_FALSE\`
