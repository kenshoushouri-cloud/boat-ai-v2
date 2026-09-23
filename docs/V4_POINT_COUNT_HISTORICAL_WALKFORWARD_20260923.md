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
