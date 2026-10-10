# S02 Prospective Forward Freeze

Freeze date: 2026-09-12 JST  
Prospective start: 2026-09-13 JST

## Purpose

Freeze the existing Candidate Filter Shadow rule `S02` before additional outcomes accumulate. This is a read-only prospective evaluation contract only. It does not change the existing shadow collector, Production selection, model coefficients, thresholds, Railway scheduling, LINE, BUY behavior, or persistence.

## Frozen rule: `S02_FORWARD_V1`

The rule is copied without modification from `collect_candidate_filter_shadow_pg.py`:

- source: actual `v2_candidate_filter_shadow` rows with `rule_id='S02'`
- probability rank: 16 through 30
- market rank: 6 through 10
- observed odds: 20.0 <= odds < 30.0
- race number: 7, 8, or 9
- venue style: `in_strong`
- event category: all
- selection mode: maximum probability among eligible tickets
- one current shadow row per `(race_id, rule_id)`
- flat 100 yen accounting for research evaluation

The rule definition, start date, and stake accounting are frozen. A material change requires a new version/name and a new prospective start date.

## Pre-freeze evidence

Actual PRE Candidate Filter Shadow evidence through 2026-09-12 showed approximately 59 evaluated S02 observations over the preceding 30 days, with 5 hits, flat-stake ROI about 140.68%, and about +2,400 yen profit at 100 yen per observation. Both the August and September slices were positive in the frozen pre-start audit (August about 159.71% ROI; September about 112.92% ROI).

This evidence is encouraging but remains too small for Production promotion. It is used only to justify prospective collection of the unchanged rule, not to authorize a threshold/model change.

## Forward checkpoints

Review the frozen rule without retuning at 30, 50, and 100 evaluated post-start observations. Report at least:

- eligible/evaluated/pending observations
- hits and hit rate
- flat 100 yen investment, return, profit, and ROI
- largest-hit share of total returns
- maximum losing streak and maximum drawdown
- calendar-month breakdown

No checkpoint automatically authorizes Production promotion. Stability must persist across time and must not depend on a single large payout.

## Guardrails

- read-only database access only
- existing Shadow rows are observed; this audit adds no Production persistence
- no Production behavior change
- no model/threshold change
- no Railway/Cron/service change
- no LINE send
- no BUY action
- `purchase_action=false` remains unchanged
- `promotion_allowed=false` until separately reviewed and explicitly approved
