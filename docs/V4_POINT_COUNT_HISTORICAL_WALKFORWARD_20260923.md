# V4 1–5 point historical walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / PRE_RESULT_RANKING / RESULT_AFTER_FREEZE_ONLY / NO_PRODUCTION_CHANGE`

## Objective

Use historical data to narrow the economically useful number of trifecta
tickets per selected V4 race before enough Forward cases accumulate.

The first fixed OOS window is:

`2026-07-01 .. 2026-08-15`

with 100 JPY per ticket and cumulative Top1..Top5 strategies.

## Historical replay order

For each calendar day:

1. load all same-day race cards and six-lane entries;
2. load Course snapshots only when:
   - `snapshot_date == race_date`;
   - official Course source;
   - `created_at < 08:15 JST`;
   - `created_at < race deadline`;
3. load Opponent Pressure only when:
   - exact race date;
   - model version 2;
   - `train_end < race_date`;
   - matched opponents satisfy current minimum;
   - `created_at/updated_at < 08:15 JST`;
   - `created_at/updated_at < race deadline`;
4. use race-entry Motor2 exactly as current V4;
5. build the current frozen V4 distribution;
6. select the same daily six races with current `select_daily`;
7. freeze Top5 ticket ranks from that distribution;
8. **only after the full ranking is frozen**, query official result/payout rows;
9. if any selected race lacks an official result, mark the whole day unevaluable.

No result availability is used to pre-filter the race universe.

## Missing feature behavior

Current V4 is intentionally neutral on missing Course/Opponent/Motor2 support.
Historical replay uses the same contract.

Coverage is reported so a good economic result cannot hide poor feature
availability.

## Compared strategies

For the exact same frozen six races:

- Top1: 100 JPY/race;
- Top1–2: 200 JPY/race;
- Top1–3: 300 JPY/race;
- Top1–4: 400 JPY/race;
- Top1–5: 500 JPY/race.

For every strategy report:

- investment;
- gross return;
- net profit;
- ROI;
- exact hit rate;
- chronological max drawdown;
- Nth-ticket-only marginal investment/return/profit/ROI/hits.

## Stability checks

The report includes:

- overall fixed-window result;
- month-by-month result;
- four chronological walk-forward blocks;
- profitable blocks;
- marginal-profitable blocks;
- minimum block ROI;
- median block ROI.

The purpose is to avoid choosing a point count because of one high-payout race.

## Evidence limitations

This is historical reconstruction, not immutable Forward evidence.

It is acceptable for narrowing a shortlist only because selection inputs are
restricted to timing-safe race-date data and result/payout tables are isolated
until after ranking freeze.

It does **not** override the Forward 30/50/100-case milestones.

The final Production point-count decision still requires Forward confirmation.

## Day exclusions

A day is not shrunk to five races.

Possible whole-day unevaluable states include:

- fewer than six V4-selectable races;
- a selected deadline at/before the 08:15 cutoff;
- missing/cancelled/non-official selected result;
- malformed official payout/result.

No replacement race, synthetic zero, later-date result or rerank is allowed.

## Safety

`READ_ONLY_TRANSACTION / NO_ODDS_SELECTION / NO_RESULT_BEFORE_RANKING / NO_5R_SHRINK / NO_REPLACEMENT / NO_RETUNE / NO_LINE / PURCHASE_FALSE`


## 2026-09-23 dual-window result

The first immutable sanitized report artifact is:

- workflow run: `35806246724`
- artifact ID: `10727519397`
- ZIP SHA-256:
  `426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`

### Fixed OOS window — 2026-07-01..2026-08-15

Coverage:

- 46/46 days evaluated;
- 276 exact selected races;
- no day shrink;
- Course any: 66.304%;
- Course full6: 28.623%;
- Opponent timing-safe: 0%;
- Motor: 99.275%.

Marginal Nth-ticket ROI:

- rank1: 71.848%;
- rank2: 73.152%;
- rank3: **88.478%**;
- rank4: 79.674%;
- rank5: **32.935%**.

### Recent timing-safe window — 2026-09-11..2026-09-22

Coverage:

- 10/12 days evaluable;
- 60 exact selected races;
- 2 whole days unevaluable because an exact selected result was unavailable;
- no 5R shrink;
- Course any: 100%;
- Course full6: 78.333%;
- Opponent timing-safe: 90%;
- Motor: 98.333%.

Marginal Nth-ticket ROI:

- rank1: 27.667%;
- rank2: 63.000%;
- rank3: **89.500%**;
- rank4: 172.833%;
- rank5: **29.167%**.

### High-payout sensitivity

The recent rank4 result is not robust:

- only 2 exact rank4 hits;
- one 9,560 JPY hit contributes **92.189%** of rank4 gross return;
- removing that one hit reduces rank4 marginal ROI to **13.500%**;
- among the 40 recent races with Course full6 + Opponent + Motor all present,
  rank4 had **0 exact hits / 0% marginal ROI**.

Rank3 is much more stable across the two windows:

- OOS marginal ROI: **88.478%**;
- recent marginal ROI: **89.500%**;
- OOS marginal profit per race: **-11.522 JPY**;
- recent marginal profit per race: **-10.500 JPY**.

Rank5 is consistently weak:

- OOS marginal ROI: **32.935%**;
- recent marginal ROI: **29.167%**.

A deterministic 20,000-resample day-cluster bootstrap is recorded in:

`research/evidence/v4_point_count_historical_sensitivity_20260923.json`

The intervals are wide because payouts are heavy-tailed, so the bootstrap is
used as an uncertainty diagnostic rather than as a significance claim.

## Current shortlist

Historical replay does **not** support simply increasing the fixed ticket count.

The point-count shortlist is:

- formal comparison: **2 points**;
- shadow comparison: **3 points**;
- rank4: diagnostic only until its large-payout effect replicates;
- rank5: deprioritize.

This is not a Production point-count change.

The current formal two-point policy remains unchanged while Forward evidence
continues. The third point should be observed as a shadow marginal rank so its
Forward incremental economics can be compared directly.

## CI secret boundary

The initial report run used an inherited Railway CLI variable-list pattern that
exists elsewhere in the repository. That pattern is **not retained** in this
PR.

The workflow now:

- never runs `railway variable list`;
- never consumes `RAILWAY_TOKEN`;
- never writes a variable-list JSON file;
- optionally replays the database report only when a dedicated
  `V4_BACKTEST_DATABASE_URL` GitHub secret is explicitly configured;
- otherwise skips the live DB replay while still running all pure contract and
  evidence tests.

The already-produced report artifact above remains the immutable source for the
recorded dual-window result.
