# boat-ai-v2 Development Status

Last updated: 2026-08-23 JST

This file is the compact handoff/decision source for ongoing development. GitHub code/PR history remains the implementation source of truth; Railway PostgreSQL remains the production data source of truth.

## Current architecture direction

- PRE (`morning/day/night`): estimate race/ticket ability probability as independently from market odds as practical.
- FINAL (`cron-final-check`): combine the independent probability estimate with actionable late market odds to decide value/BUY-WATCH-SKIP.
- Market odds may be recorded during PRE for Shadow comparison, but should not dominate the independent ability probability layer.
- Production promotion requires OOS/walk-forward/forward evidence; high historical ROI alone is insufficient.

## Bao-style market/value research

Core idea retained: separate probability estimation from market price/value judgment rather than copying horse-racing formulas directly.

### Strong candidates

- Motor2 market residual: robust candidate. PR #108: positive beta across 4 splits (0.08/0.08/0.08/0.06), 7/8 months improved, aggregate OOS improvement on 34,193 races.
- Exhibition time residual: robust candidate. PR #113: additional beta 0.06 across 4 splits, 8/8 months improved, aggregate stability around z=-4.92.
- Market baseline: de-vigged market probability is substantially stronger than the current standalone v24 probability; use market as FINAL price baseline, not as PRE ability truth.

### Not promoted / rejected

- Naive `prob * odds` EV: not reliable; high model-vs-market edge historically worsened ROI.
- Individual racer × own course × opponent course/class affinity: unstable OOS; do not use yet.
- Wave residual after market+Motor2+exhibition: rejected; all 4 future splits worsened (PR #118).
- Wind-speed residual after market+Motor2+exhibition: rejected; 0/8 months improved, aggregate worsened (PR #119).
- Relative wind-direction residual: historical DB has no usable head/tail/crosswind coverage; do not infer venue geometry without verified official mapping (PR #120).
- Exhibition ST residual: PR #122 selected beta -0.02 in all splits, 6/8 months improved but aggregate z=-1.85; `NOT_YET_ROBUST`, no Production promotion.

## Bao early/late market Shadow

Isolated table: `v2_bao_market_shadow_snapshots`.

Safety:
- one compact row per race/phase with `real[120]` odds vector;
- exact 120-ticket gate; 119/120 is rejected;
- first early/late capture is frozen;
- re-check phase after the official odds fetch so a slow request cannot save a snapshot after its intended window;
- no Production decision/LINE changes.

Target windows:
- early: 20-30 minutes before deadline;
- late: 0-7 minutes before deadline.

Smoke observations on 2026-08-23:
- 08:08: Shimonoseki 1R was early-eligible, but no contemporaneous complete 120-ticket snapshot existed; safe skip.
- ~08:56: Shimonoseki 2R late had only 119/120 tickets in normal realtime snapshots; Shimonoseki 3R early had no snapshot yet; safe skips.
- Live diagnosis then confirmed the current official odds page is a side-by-side table; the legacy hyphen-ticket parser returned 0 while the new table-token parser can recover the canonical 120 tickets.
- 18:33 smoke after PR #127: 3/3 target races saved with exact 120-ticket vectors, `partial=0`, table size 49,152 bytes, and `BAO_SHADOW_RESULT=PASS`.
- 18:52 smoke: `20260823_07_09` late was captured at 2.83 minutes before deadline; `paired_races=1`, `partial=0`, `phase_drift=0`, PASS. This is the first genuine same-race early+late forward pair.

Forward audit direction:
- compare frozen early de-vigged market probability against actionable late market probability;
- apply the frozen current Motor2 beta 0.06 from PR #108 and exhibition-time beta 0.06 from PR #113 only when timestamp-safe realtime data exists;
- treat fewer than 30 paired races as insufficient for a formal forward conclusion;
- realized results are supplemental; no Production promotion from a tiny sample.

## Historical/data quality

- Production DB: Railway PostgreSQL; correct entries table is `v2_race_entries`.
- Historical temperature/water-temperature restoration from stored official raw text is validated on pilot dates; NULL-only/historical-only rules apply.
- Historical tilt restoration remains blocked by parser quality gate; do not write tilt until reliability improves.
- Motor maturity/source work: BOAT RACE official is primary; 艇国DB may be secondary corroboration only. Do not treat its aggregate start date as official truth without cross-check.
- DB capacity must be watched; prefer compact arrays/metadata rather than raw repeated payloads.

## Production safety rules

- Never change BUY/WATCH/SKIP or LINE from Shadow evidence alone.
- Shadow data must remain isolated from Production decision files except through explicitly reviewed promotion work.
- Historical/replay runs: `DRY_RUN=1`, `TEST_MODE=1`, no LINE.
- Main is not edited directly; use branch -> Draft PR -> CI -> review -> merge.

## Immediate next work

1. Continue Bao early/late forward capture without relaxing the exact-120 gate; accumulate paired races.
2. Run the paired forward read-only audit as samples accumulate; require at least 30 valid pairs before formal evaluation.
3. Evaluate Motor2 first and exhibition time only with timestamp-safe availability; do not promote from early tiny samples.
4. Continue one-feature-at-a-time residual OOS screening and keep this file updated after material decisions.
