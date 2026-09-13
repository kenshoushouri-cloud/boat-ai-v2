# Candidate Discovery daily Forward capture SOP

Status: **research-only / fail-closed / purchase_action=false**

This SOP defines how V4 Forward evidence is captured from 2026-09-14 onward without post-outcome reconstruction. It does not authorize a Production deployment, Railway schedule/configuration change, DB mutation, LINE send, or purchase action.

## 1. Stage-1 freeze must exist before outcome

For each evaluation date, create an immutable Candidate Discovery V4 main-feed artifact while the race card is ready and before outcome information is used.

The artifact must preserve the predeclared V4 contract:

- daily structural TOP6 races;
- TOP2 exact-order trifecta tickets per core race;
- Course coefficient `0.50`, missing lane neutral;
- Opponent Pressure coefficient `1.0`, first-place probability only;
- Motor2 beta `0.06`, position weights `1.0 / 0.6 / 0.3`;
- four structural metrics equal-weighted for daily ranking;
- no EV gate and no absolute odds gate;
- legacy/reference candidates retained separately as carryover;
- `purchase_action=false`.

Record at minimum the Actions run ID, artifact ID, artifact ZIP SHA-256, internal JSON SHA-256, freeze timestamp, scheduled/evaluable counts, core race/ticket count, and legacy carryover count.

If a valid pre-result Stage-1 artifact was not captured for a date, that date is **unavailable Forward evidence**. Do not regenerate it after results.

## 2. Stage-2 market annotation never changes Stage-1

`MKT_LATE07_TOP2_SUPPORT_V1` starts on **2026-09-14 JST**.

The generic read-only runner is:

- `research/candidate_discovery_market_forward_annotate_pg.py`

It requires all of the following external provenance inputs:

- exact frozen Stage-1 JSON;
- expected frozen JSON SHA-256;
- freeze Actions run ID;
- freeze artifact ID.

The runner verifies the SHA-256 before querying market snapshots and refuses pre-2026-09-14 freezes. It extracts only the immutable V4 `DISCOVERY_CORE` `core_order=1` ticket from each of the six core races.

Eligible market evidence remains fixed:

- complete coherent 120-ticket trifecta snapshot;
- 120 distinct tickets with positive odds greater than 1.0;
- snapshot spread <= 60 seconds;
- snapshot timestamp at or before deadline;
- lead time `0.0..7.0` minutes before deadline;
- support = frozen V4 TOP1 trifecta ticket is in market trifecta TOP2.

The market layer may annotate a candidate but may never create, replace, reorder, or delete the Stage-1 feed.

The runner reads only `v2_races` and `v2_realtime_odds_snapshots` inside an explicit read-only PostgreSQL transaction. It does not read official outcomes.

## 3. Outcome evaluation uses the exact freeze

After official results are available, evaluate only the exact frozen Stage-1 artifact for that date. Do not add later candidates or regenerate candidates from the final state of the database.

For `MKT_LATE07_TOP2_SUPPORT_V1`, join outcome returns to the previously frozen market annotation and summarize with:

- `research/candidate_discovery_market_forward_metrics.py`

Report the same-universe late-available baseline and the market-TOP2-supported subset. Required metrics include evaluated cases/days, hits, hit rate, flat-100-JPY investment/return/profit/ROI, maximum losing-race streak, maximum drawdown, positive-day rate, and maximum single-hit share of returns.

Milestones remain fixed at **30 / 50 / 100 supported evaluated cases**. Crossing a milestone does not automatically authorize promotion.

## 4. Daily automation boundary

The current Candidate Discovery work remains on Draft PR #351 rather than `main`. GitHub scheduled workflows execute from the default branch, and a Railway Cron/service change would modify Production configuration. Therefore this Draft research package does **not** silently add an autonomous daily scheduler.

Until a daily capture mechanism is explicitly approved and safely promoted, each date must have a deliberate pre-result freeze. If that capture is missed, record the date as unavailable rather than reconstructing it after outcome.

A future automation proposal must preserve all of these boundaries:

- pre-result Stage-1 freeze;
- immutable artifact and digests;
- outcome-free Stage-2 annotation;
- fail-closed behavior when inputs are late or incomplete;
- no candidate deletion from market disagreement;
- no retuning of the 0-7 minute / TOP2 definition;
- `purchase_action=false`;
- Production promotion only by separate explicit approval.

## 5. 2026-09-13 remains wiring-only for this hypothesis

The official 2026-09-13 V4 artifact is an independent Forward freeze, but it predates the prospective start of `MKT_LATE07_TOP2_SUPPORT_V1` and must never be counted toward its 30 / 50 / 100 milestones.

The dedicated 2026-09-13 wiring dry run may remain as a technical check only. Its observed market annotations do not become prospective study observations.
