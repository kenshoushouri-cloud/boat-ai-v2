# Candidate Discovery market Forward evaluation contract — 2026-09-13

Status: **research-only / prospective from 2026-09-14 JST / purchase_action=false / promotion blocked**

This addendum fixes how `MKT_LATE07_TOP2_SUPPORT_V1` will be evaluated against exact immutable V4 Forward artifacts.

## Exact Forward scope

The current Candidate Discovery V4 main-feed artifact freezes **trifecta tickets** before results. It does not freeze an independent exacta or trio structural TOP1 distribution.

Therefore the exact V4 prospective track for `MKT_LATE07_TOP2_SUPPORT_V1` is:

- bet type: **trifecta only**;
- structural ticket: the immutable V4 `DISCOVERY_CORE` ticket with `core_order=1`;
- market window: complete coherent 120-ticket snapshot at 0.0..7.0 minutes before deadline;
- support rule: immutable V4 trifecta TOP1 is in the de-vigged market trifecta TOP2;
- stake for evaluation: flat 100 JPY per evaluated ticket;
- prospective start: **2026-09-14 JST**.

The historical exacta/trio proxy audits remain diagnostics. They must not be reclassified as exact V4 Forward evidence.

Do **not** regenerate an exacta/trio structural distribution after results from the V4 model and backfill it into this study. If a future pre-result feed explicitly freezes exacta/trio structural candidates, that requires a new prospective version and a new start date.

## Same-universe baseline

Every exact V4 Forward report must show two trifecta views over the same immutable candidate stream:

1. `late_available_baseline`: every V4 core TOP1 with an eligible timing-safe 0..7 minute market snapshot;
2. `market_top2_supported`: the subset whose frozen V4 TOP1 ticket is in market TOP2.

This prevents the support view from being compared against a different race universe.

## Evidence milestones

Milestones are based on **evaluated `market_top2_supported` V4 trifecta cases**:

- 30 cases — first formal checkpoint;
- 50 cases — intermediate checkpoint;
- 100 cases — robustness checkpoint.

A milestone does not authorize Production promotion. At each checkpoint report:

- supported evaluated cases and days;
- hits / hit rate;
- flat-100-JPY investment, return, profit, ROI;
- maximum losing-race streak;
- maximum drawdown;
- positive-day rate;
- maximum single-hit share of total returns;
- same-universe late-available baseline metrics;
- source V4 feed artifact SHA-256 and annotation artifact identity for each day.

## Daily provenance required before evaluation

For each prospective day retain, before results are scored:

- V4 feed date;
- immutable feed artifact/run identity;
- feed JSON SHA-256;
- race_id / venue / race_no / tier / daily rank;
- frozen core TOP1 ticket;
- whether a valid late snapshot existed;
- snapshot label and timing metadata;
- market TOP2 tickets;
- `market_top2_support` boolean;
- `counts_as_prospective=true` only for dates >= 2026-09-14.

If the pre-result artifact or the timing-safe late snapshot is unavailable, record unavailable and do not reconstruct it after the outcome.

## Separation of responsibilities

Candidate generation, market annotation, and outcome evaluation remain separate:

- V4 main feed creates/fixes candidates before results;
- market annotation may only add tags to those fixed candidates;
- outcome evaluation runs later and must not alter either the candidate set or annotation;
- market disagreement never deletes the Stage-1 prediction feed;
- `purchase_action=false` remains mandatory.

## 2026-09-13 wiring-only observation

Run `34747378454` verified the wiring against the immutable 2026-09-13 V4 freeze without reading outcomes or payouts:

- core TOP1 tickets: 6;
- eligible late snapshots available: 3;
- market TOP2 supported: 2;
- counts as prospective evidence: **0**.

This observation validates plumbing only and is excluded from the 30/50/100 milestones.

## Safety boundary

- DB write: 0
- schema change: 0
- LINE send: 0
- purchase action: false
- Production selector/model/threshold change: 0
- Production persistence change: 0
- Railway Production config/Cron/service change: 0
