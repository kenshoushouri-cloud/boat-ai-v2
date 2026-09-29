# Historical pre-deadline data acquisition — 2026-09-30

Status: `APPROVED / ACTIVE / HISTORICAL_RECONSTRUCTION / PROSPECTIVE_SEPARATE`

## User direction

Historical missing data should be acquired aggressively.

For historical research, the working truth is:
- use the value published for the race before its deadline when an archived pre-race source exists;
- do not use post-result outcome information to construct a pre-race feature;
- record source and reconstruction status;
- keep historical reconstruction distinct from genuine prospective evidence.

## Source priority

1. **BOAT RACE official**
   - official download service for race cards, race results and racer term data;
   - archived official race pages for race-time entry features and beforeinfo;
   - first choice whenever available.

2. **Derived from official raw data**
   - course statistics;
   - opponent-pressure inputs;
   - recent-form windows;
   - other features that can be recomputed using only information dated before the race.

3. **艇国データバンク**
   - supplementary / cross-check source where useful;
   - follow its published automation rules;
   - at least 3 seconds between requests;
   - do not use it as the bulk source for race cards, race results or racer term results where its rules direct users to the BOAT RACE official download service.

## First active backfill

Priority range begins at:
- 2025-07-01

First batch:
- 2025-07-01 through 2025-07-07

Official archived racelist fields to fill:
- F count;
- L count;
- average ST;
- national win rate;
- national place2/place3 rate;
- local win rate;
- local place2/place3 rate;
- motor number and place2/place3 rate;
- boat number and place2/place3 rate.

Safety:
- existing `v2_race_entries` rows only;
- fill NULL/blank values only;
- never overwrite a non-null historical value;
- no result/odds/payout read;
- no LINE;
- no purchase;
- no model/selector/stake change.

## Evidence semantics

Historical reconstructed rows may be used for:
- matched-contract backtests;
- feature coverage analysis;
- robustness research;
- model-development diagnostics.

They are **not** counted as:
- formal prospective V4 days;
- S03 prospective observations;
- future-only F-count companion evidence.

This distinction prevents historical reconstruction from inflating prospective gates.

## Next acquisitions

After raw entry backfill:
1. official historical beforeinfo (exhibition / weather / condition);
2. derive course statistics from official past race outcomes using only prior races;
3. derive opponent pressure from contemporaneous entry fields;
4. build recent-form features from races strictly earlier than the target race;
5. use 艇国DB selectively for cross-checks / supplementary data under its rules.

`OFFICIAL_FIRST / PREDEADLINE_ARCHIVE_AS_HISTORICAL_TRUTH / NULL_ONLY_FILL / NO_OUTCOME_LEAKAGE / TEIKOKU_SUPPLEMENT_WITH_3S_RULE / PROSPECTIVE_GATES_UNCHANGED`
