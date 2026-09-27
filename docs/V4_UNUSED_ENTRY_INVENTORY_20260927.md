# V4 unused pre-race entry information inventory — 2026-09-27

Status: `PREREGISTERED / RESULT_BLIND / READ_ONLY / NO_MODEL_VARIANT`

## Purpose

After PR #394 showed `recent_form` is empty across the canonical period,
inventory other race-entry information already stored but not consumed by
current V4. This is a data-readiness audit only.

## Current V4 entry inputs

The current V4 base path already consumes:
- `racer_class`
- `national_win_rate`
- `national_place2_rate`
- `local_place2_rate`
- `avg_st`

Motor2 separately consumes `motor_place2_rate`.

## Frozen candidate inventory

- `national_place3_rate`
- `local_win_rate`
- `local_place3_rate`
- `motor_place3_rate`
- `boat_place2_rate`
- `boat_place3_rate`
- `f_count`
- `l_count`
- `branch`
- `origin`
- `motor_no`
- `boat_no`

No outcome-dependent ranking of these fields is allowed in this audit.

## Provenance from current main

`repair_month_all_pg.py` parses the numeric rates, F/L counts, branch/origin
and motor/boat numbers from BOAT RACE official race-specific `racelist` pages:

`https://www.boatrace.jp/owpc/pc/race/racelist?rno=N&jcd=XX&hd=YYYYMMDD`

The same parser validates the 13-value official stat block before accepting it.

This establishes current-main source semantics, but does not by itself prove
that every historical database row was captured by 08:15 JST. Row-level timing
proof is evaluated separately and must fail closed if absent.

## Audit

Canonical period: 2025-07-01..2026-09-22.

For every candidate field report:
- non-null row coverage;
- races with any value;
- exact-six race count;
- races with all six values;
- numeric range/distinct count where applicable;
- whether a strong row-level source-capture timestamp exists.

No result, payout, odds, or prediction-performance table may be read.

## Interpretation rule

This audit can establish **data presence**, not predictive value.

If historical 08:15 capture timing is unprovable, a field may be labeled
`DATA_PRESENT_0815_ROW_TIMING_UNPROVEN`; it must not automatically become a
historical V4 feature test. A later timing-safe prospective shadow may be needed.

No coefficients or transformations are defined here.

Safety:
`READ_ONLY / RESULT_BLIND / NO_DB_WRITE / NO_LINE / NO_FORWARD_PERSISTENCE / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`
