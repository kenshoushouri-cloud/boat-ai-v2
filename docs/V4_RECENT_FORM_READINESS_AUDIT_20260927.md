# V4 recent-form readiness audit — 2026-09-27

Status: `PREREGISTERED / RESULT_BLIND / READ_ONLY / NO_MODEL_VARIANT_YET`

## Question

Before defining another current-V4 predictive feature, determine whether
`v2_race_entries.recent_form` is actually usable as timing-safe stronger
current-form information.

This audit is evidence-only. It must not read race outcomes, payouts, odds, or
use performance to choose a transformation.

## Frozen period

- canonical historical period: 2025-07-01 through 2026-09-22;
- source tables allowed: `v2_races`, `v2_race_entries`, and
  `information_schema` only;
- PostgreSQL transaction must be READ ONLY;
- current 08:15 JST morning boundary is the timing reference.

## Readiness gates

A future predictive preregistration is allowed only if all of the following are
proved before any outcome-based feature design:

1. `recent_form` exists as JSONB and has non-empty rows in the canonical period;
2. each non-empty entry is bound to a non-null racer identity;
3. the payload structure is consistent enough to identify its component prior-race records;
4. every component record exposes a parseable event/race date;
5. every component event date is strictly earlier than the target race date;
6. a strong source-capture timestamp field exists and proves every non-empty
   payload was available no later than 08:15 JST on the target date.

`created_at` / `updated_at` are reported only as weak diagnostics; they are
not accepted as source-capture proof.

If any gate is not provable, classification is
`NOT_READY_FAIL_CLOSED`. No coefficient, transformation, or same-history
performance test may be designed from the audit result.

## Current-main provenance review before DB audit

Current-main code search found:

- schema compatibility adds `v2_race_entries.recent_form jsonb`;
- `diagnose_previous_st_sources_pg*.py` and
  `feature_lab_previous_st_detail_pg_v2.py` read the field;
- `repair_month_all_pg.py` writes `recent_form=[]` on its repair paths;
- no current-main writer that constructs a non-empty `recent_form` payload was
  found in the bounded repository search.

Therefore any non-empty Production rows require provenance/timing verification;
column existence alone is not sufficient evidence.

## Safety

- no result table read;
- no odds or payout read;
- no DB write/schema/VACUUM;
- no Railway variable enumeration;
- no collector execution;
- no LINE / Forward persistence / Production model change;
- no purchase action;
- `purchase_action=false`.

The one-shot workflow is not armed until contract validation is green.


## Canonical one-shot result

Canonical trigger:
- head: `1fec3d9c0ade35c48634ca1220ebcd2b188bd8d7`
- workflow run: `36300918133` — SUCCESS
- artifact: `10925970218`
- artifact ZIP digest: `sha256:3a2fcb827916be87facbb7b4ccb40200ce5c512b96136d9fe66ec6c7a52df107`
- result JSON SHA256: `11dd669a7af7da690e13fde312be4725cef3c9baee80ff221b2492915bc61a19`

Result-blind Production-data audit:
- canonical-period entry rows scanned: **413,820**
- non-empty `recent_form` rows: **0**
- full-six races with all six `recent_form` values non-empty: **0**
- parsed recent-form item dates: **0 / 0**
- strong source-capture timestamp column: **NONE**
- final classification: `NOT_READY_FAIL_CLOSED`

Safety markers from the canonical workflow:
- secret enumeration: 0
- outcome read: 0
- collector execution: 0
- PostgreSQL transaction: READ ONLY
- purchase action: false

## Frozen conclusion

`RECENT_FORM_EMPTY_IN_CANONICAL_PERIOD / NO_NONEMPTY_COVERAGE / NO_STRONG_CAPTURE_TIMESTAMP / NOT_READY_FAIL_CLOSED / DO_NOT_DEFINE_TRANSFORMATION_OR_COEFFICIENT / NO_OUTCOME_READ / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The audit does **not** support a predictive `recent_form` experiment. Because the
field is empty throughout the canonical period, there is no evidence-safe
transformation to preregister from this column. Do not backfill or reconstruct
historical recent-form values after outcomes merely to create a test set.

The one-shot workflow is hard-locked to the canonical trigger SHA and the
sentinel has been consumed. No rerun is authorized from this evidence.
