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
