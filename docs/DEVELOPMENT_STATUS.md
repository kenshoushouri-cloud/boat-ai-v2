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
- The same 18:33 smoke had 2 early rows and 1 late row but `paired_races=0`; genuine same-race early+late pairs are still the next data requirement.

Next market-Shadow goal: capture genuine paired early+late rows on later races where the official market is fully populated, then evaluate Motor2/exhibition residual versus actionable late odds.

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

1. Continue Bao early/late forward capture on later-day races without relaxing the exact-120 gate; retain the post-fetch phase drift guard.
2. Once paired samples exist, evaluate early market + Motor2 (+ exhibition when available) against late actionable odds and realized results.
3. Continue one-feature-at-a-time residual OOS screening; reject features that do not add value beyond the stronger baseline.
4. Keep this file updated after material design/promote/reject decisions so a new ChatGPT conversation can resume from GitHub with minimal handoff text.
