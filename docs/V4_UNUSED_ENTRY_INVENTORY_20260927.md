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


## Canonical one-shot result

- trigger head: `d26ccaf5a936e6708db96d477dc02c7ad7972117`
- workflow run: `36301606766` — SUCCESS
- artifact: `10926285564`
- artifact ZIP digest: `sha256:2b9376f67b458fb1e0e5775d51ebe35896348d955fe300f59725f49cd9e0f3e7`
- result JSON SHA256: `435f343d0af25d1d0449142f5d6432c304408c55a17a9961869ff7d745eebf2c`
- canonical entry rows: **413,820**
- exact-six races: **68,970**
- strong row-level source-capture timestamp column: **NONE**
- outcome read: **0**
- secret enumeration: **0**

Coverage / full-six coverage among exact-six races:

| field | row coverage | full-six coverage | readiness |
|---|---:|---:|---|
| national_place3_rate | 99.8531% | 99.1272% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| local_win_rate | 99.8531% | 99.1272% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| local_place3_rate | 99.8528% | 99.1257% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| motor_place3_rate | 99.8231% | 98.9517% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| boat_place2_rate | 99.6552% | 98.0107% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| boat_place3_rate | 99.6153% | 97.7816% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| f_count | 100.0000% | 100.0000% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| l_count | 100.0000% | 100.0000% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| branch | 6.5942% | 6.5942% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| origin | 6.5942% | 6.5942% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| motor_no | 99.8526% | 99.1243% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |
| boat_no | 99.7422% | 98.5167% | DATA_PRESENT_0815_ROW_TIMING_UNPROVEN |

## Frozen interpretation

The audit establishes **data presence**, not predictive value or historical
timing safety. The high-coverage numeric fields are materially different from
`recent_form`: they are present in almost all canonical rows and are produced
by the current official `racelist` parser. However, no strong row-level
capture timestamp exists in `v2_race_entries`, so the canonical database alone
cannot prove that every historical row was fixed by 08:15 JST.

Therefore no historical coefficient search is authorized from this inventory.

Next safe work may use only result-blind redundancy/provenance analysis to
determine whether these fields add genuinely independent information relative
to current V4 inputs. Any predictive test requiring historical timing safety
must either prove an independent timing source or use a separately approved
prospective first-write-wins shadow.

Frozen gate:
`UNUSED_ENTRY_DATA_PRESENT / NUMERIC_COVERAGE_HIGH / HISTORICAL_0815_ROW_TIMING_UNPROVEN / NO_OUTCOME_READ / NO_COEFFICIENT_SELECTION / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The one-shot is hard-locked to the canonical trigger SHA and its sentinel has
been consumed.
