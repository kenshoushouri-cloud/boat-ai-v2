# Exhibition ST frozen Forward health audit — 2026-09-27

Status: `RESEARCH_ONLY / COMPLETED / EXISTING_FROZEN_SHADOW / NO_COLLECTION / NO_PRODUCTION_CHANGE`

## Question

What is the realized health of the already-frozen Exhibition ST Forward Shadow
as of 2026-09-27, after additional prospective races accumulated beyond the
2026-09-10 one-shot health bundle?

This audit does not create or modify Shadow rows.

## Frozen model under audit

Existing `v2_exhibition_st_forward_shadow` only:

- official BOAT RACE beforeinfo;
- capture 8–15 minutes before deadline;
- first snapshot wins;
- current-v24-equivalent BASE;
- start-timing score `z(-start_timing_rank)`;
- trifecta position weights 1.0 / 0.6 / 0.3;
- beta = **-0.02 fixed** from the earlier PR #122 training cutoff.

No coefficient, race band, venue, threshold, or subgroup is selected here.

## Execution safety

- run existing `report_exhibition_st_forward_health_pg.py` unchanged;
- PostgreSQL default transaction mode forced READ ONLY with `PGOPTIONS`;
- connect via Railway `railway run` non-enumerating environment injection;
- do **not** call Railway variable-list APIs;
- do not invoke the collector;
- no INSERT / UPDATE / DELETE / DDL;
- no LINE, BUY/WATCH/SKIP, model, selector, Railway setting, or purchase change;
- `purchase_action=false`.

Primary readout is overall trifecta LogLoss / Brier / actual-ticket rank deltas,
with first-place proper scores as supporting diagnostics. Date, race-band and
venue sign counts are descriptive only; they cannot be used to invent a
post-result filter.

`EXISTING_FROZEN_FORWARD_ONLY / CURRENT_REALIZED_RESULTS / DB_READ_ONLY / NO_RETUNE / NO_COLLECTION / PURCHASE_FALSE`


## Completed canonical audit

The first one-shot run, `36255994155`, successfully executed the read-only report
and uploaded evidence but the workflow concluded FAILURE because the final safety
guard searched the workflow text for the literal collector filename that was also
present inside the assertion itself. That run is not accepted as canonical evidence.

The self-referential guard was fixed without changing beta, data scope, report code,
DB mode, subgroup definitions, or interpretation rules. A second one-shot was then
armed explicitly.

Canonical evidence:

- trigger head: `62571830b6d09a91fad9874e5a2c8c91555107d7`
- workflow run: `36288188460` — SUCCESS
- artifact: `10921021546`
- artifact name: `exhibition-st-current-health-36288188460`
- artifact ZIP SHA-256: `25d9a0236809ea198f58e0d012d295e40aede5550802d5422946f3e9ee19f5c3`
- sanitized evidence SHA-256: `8e84f8ced46b4abe190fa53242ec18bee16bf9cc9366d0489e290f980cfa84fc`
- rows evaluated: 1,879
- PostgreSQL transaction mode: READ ONLY
- collector execution: none
- Railway variable enumeration: none
- Production / LINE / purchase change: none / `purchase_action=false`

### Overall realized health

Frozen beta = -0.02 versus BASE:

- trifecta Brier delta: `+0.00001891`
- trifecta LogLoss delta: `+0.00053482`
- actual-ticket rank delta: `+0.0021`
- Top1: `3.78% -> 3.67%`
- Top3: `11.28% -> 10.80%`
- Top5: `16.82% -> 17.30%`
- Top10: `30.28% -> 30.44%`
- first-place Brier delta: `+0.00000874`
- first-place LogLoss delta: `+0.00019550`
- first-place rank delta: `+0.0059`

Positive delta is worse for Brier / LogLoss / rank. Therefore the frozen Exhibition
ST adjustment is approximately neutral but slightly adverse overall on the primary
proper-score diagnostics.

Venue sign counts are heterogeneous:

- venues: 24
- trifecta LogLoss better: 8
- trifecta Brier better: 8
- trifecta rank better: 11

Race-band signs are also mixed. In particular R05–08 looks better on proper scores,
but no race-band, venue, or date subgroup was preregistered for adoption, so none
may be promoted post-result.

### Frozen conclusion

`FROZEN_EXHIBITION_ST_NOT_SUPPORTED_FOR_PROMOTION / OVERALL_PROPER_SCORES_SLIGHTLY_WORSE / TOP5_TOP10_TINY_MIXED_GAIN_ONLY / VENUE_AND_DATE_SIGNS_HETEROGENEOUS / NO_POST_RESULT_SUBGROUP / KEEP_RESEARCH_ONLY / NO_PRODUCTION_CHANGE / PURCHASE_FALSE`

The canonical trigger SHA has been hard-locked and the one-shot sentinel consumed.
Further historical/current-health reruns require a new preregistered question rather
than reusing this evidence gate.
