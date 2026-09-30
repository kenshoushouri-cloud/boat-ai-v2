# Historical pre-deadline acquisition contract — 2026-09-30

Status: `APPROVED / PILOT / HISTORICAL_REPLAY / NOT_PROSPECTIVE`

## User-approved historical assumption

For historical backtesting, race-card fields associated with the target race are
treated as the pre-deadline historical values when no original capture timestamp
exists.

This assumption is explicitly recorded and must never be confused with genuine
prospective evidence.

Labels:
- historical replay: allowed under this assumption;
- prospective evidence: false;
- Production promotion evidence: must still be confirmed by Forward data.

## Source priority

1. **BOAT RACE official download service**
   - daily programme (B) archive;
   - official race/performance archives where needed;
   - preferred for bulk acquisition.

2. **艇国データバンク**
   - supplemental historical race-card fields and source cross-check;
   - automated access must obey its published rules;
   - minimum 3 seconds between requests;
   - deterministic existing URLs only;
   - no parallel/multi-IP acquisition.

3. BOAT RACE historical web pages
   - use only when the official download files do not contain the required field;
   - keep request volume minimal.

## Leakage boundary

A 艇国 historical race-detail page contains both post-race results and the
historical race card.

The feature backfill path must:
- locate the race-card `場外締切` block;
- discard all page text before that marker;
- whitelist only pre-race fields;
- never parse payout/result/finish information into model features.

Raw pages may be retained solely for provenance and reproducibility.

## Pilot

First bounded batch:
- date: 2025-07-17;
- venue: 大村 / code 24;
- races: 1R..12R;
- 12 sequential 艇国 detail requests at >=3 seconds;
- one BOAT RACE official B archive request;
- raw files + predeadline-only text + SHA256 manifest;
- no DB writes.

After pilot verification, the next bounded step is:
1. parse fields into a normalized schema;
2. compare against current PostgreSQL coverage;
3. identify only missing/backfillable columns;
4. perform a small, explicitly logged DB insert/upsert batch;
5. re-audit coverage before expanding the date range.

## Candidate fields

Expected from historical race cards/programmes:
- class;
- F/L counts;
- current-term stats;
- national win / 1st / place2 / place3 rates;
- average ST;
- local win / place2 rates;
- motor number / place2 rate;
- boat number / place2 rate;
- deadline;
- meeting/race context.

Beforeinfo fields (exhibition/weather) remain a separate historical source path.

Course/Opponent features should be recomputed only from information dated before
the target race, not copied from a current racer profile.

## Safety

`HISTORICAL_ASSUMPTION_EXPLICIT / OFFICIAL_BULK_FIRST / TEIKOKU_3SEC_MIN / OUTCOME_PREFIX_STRIPPED / RAW_HASHED / NO_DB_IN_PILOT / NO_PROD_MODEL_CHANGE / PURCHASE_FALSE`
