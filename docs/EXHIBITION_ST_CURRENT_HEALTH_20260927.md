# Exhibition ST frozen Forward health audit — 2026-09-27

Status: `RESEARCH_ONLY / PRE_RESULT / EXISTING_FROZEN_SHADOW / NO_COLLECTION / NO_PRODUCTION_CHANGE`

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
