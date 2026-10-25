# V4 entry input novelty audit — 2026-09-27

Status: `PREREGISTERED / RESULT_BLIND / INPUT_ONLY`

PR #395 established that unused official racelist fields are broadly present,
but historical row-level 08:15 capture timestamps are not retained.

This audit does **not** test predictive performance. It only asks whether the
unused fields are non-degenerate and independent enough to justify any future
preregistration.

## Frozen metrics

Canonical period: 2025-07-01..2026-09-22.

Input-only Pearson pairs:
- national place3 vs national place2;
- local win vs local place2;
- local place3 vs local place2;
- motor place3 vs motor place2;
- boat place3 vs boat place2;
- boat place2 vs motor place2.

A pair with |Pearson| >= 0.95 is labeled structurally redundant for triage.

For each numeric field report:
- full-six coverage;
- fraction of full-six races with any lane-to-lane variation;
- positive-value row fraction;
- distinct values.

A field is only shape-ready when full-six coverage >=95% and within-race
variation >=5%. This does not authorize a predictive test.

## Priority rule fixed before audit

1. F/L is considered first because it is a distinct pre-race operational-state
   family rather than another place-rate/motor-rate transform.
2. place3/motor3 may not become next merely from high coverage; redundancy with
   current inputs is checked first.
3. boat rate remains low priority due prior #186/#187/#188 evidence.
4. historical predictive testing remains blocked by PR #395's missing strong
   row-level 08:15 timestamp unless a separate timing-safe design is established.

No outcomes, odds, payouts, or prediction metrics are read.

Safety:
`READ_ONLY / RESULT_BLIND / NO_DB_WRITE / NO_FORWARD_PERSISTENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`.


## Canonical one-shot result

- trigger head: `05cbc5e2ff5f4af71fdeb66510964711317de3fd`
- workflow run: `36302265912` — SUCCESS
- artifact: `10926306186`
- artifact ZIP digest: `sha256:14b3218bee76b8df00dac650afc57a81f92d21a08cc510aade6eb68b750324d8`
- result JSON SHA256: `bf7ef418a2d0568cec17fd2af6c52eca329e68b7adbf72dd1c88730218f33b48`
- entry rows: **413,820**
- exact-six races: **68,970**
- outcome read: **0**
- secret enumeration: **0**

Input-only findings:
- `f_count`: full-six 100.0%; within-race variation 57.0741%; positive rows 15.0826%; **shape gate PASS**
- `l_count`: full-six 100.0%; within-race variation 0.8221%; positive rows 0.1382%; **shape gate FAIL**
- national place3 vs place2 Pearson: 0.94477355
- local win vs local place2: 0.68002845
- local place3 vs local place2: 0.89692188
- motor place3 vs motor place2: 0.85751604
- boat place3 vs boat place2: 0.88884350
- boat place2 vs motor place2: 0.18915992

No fixed pair crossed the preregistered |Pearson| >= 0.95 redundancy label.

## Frozen interpretation

`F_COUNT_INPUT_SHAPE_READY / L_COUNT_TOO_DEGENERATE / PLACE3_AND_MOTOR3_NOT_REDUNDANT_BY_FIXED_095_RULE_BUT_NOT_PRIORITIZED / BOAT_RATE_REMAINS_LOW_PRIORITY_FROM_PRIOR_EVIDENCE / HISTORICAL_0815_TIMING_STILL_UNPROVEN / NO_OUTCOME_READ / NO_HISTORICAL_COEFFICIENT_SEARCH / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The result supports **F count as the next information family for a separate
prospective diagnostic design**, not a model coefficient. Because historical
row-level 08:15 capture timing is unproven, no retrospective F-count
performance test is authorized from this audit.

A clean next design should freeze F counts before outcomes and first ask whether
the current V4 predicted-head error rate differs when the predicted head has an
F count above zero. Only if that prospective diagnostic accumulates enough
evidence should a separate coefficient/model experiment be preregistered.

The one-shot is hard-locked to the canonical trigger SHA and its sentinel has
been consumed.
