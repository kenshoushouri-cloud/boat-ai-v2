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
- Exhibition time residual: robust historical/OOS candidate. PR #113: additional beta 0.06 across 4 splits, 8/8 months improved, aggregate stability around z=-4.92. Forward evidence must use the dedicated frozen Bao mid-window exhibition capture described below.
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
- re-check phase after the official odds fetch so a slow request cannot save a market snapshot after its intended window;
- market collector is market-only after PR #134; it no longer fetches official `beforeinfo`;
- legacy nullable exhibition columns remain only for schema compatibility and are ignored by forward audit;
- no Production decision/LINE changes.

Target windows:
- early market: 20-30 minutes before deadline;
- late market: 0-7 minutes before deadline.

Important observations on 2026-08-23:
- Current official trifecta odds page is a side-by-side table; the legacy hyphen-ticket parser returned 0 while the table-token parser can recover the canonical 120 tickets (PR #127).
- 18:33 smoke after PR #127: 3/3 target races saved with exact 120-ticket vectors, `partial=0`, table size 49,152 bytes, PASS.
- 18:52: `20260823_07_09` became the first genuine same-race early+late market pair.
- 18:59: paired market races increased to 2.
- 19:04: paired market races increased to 3 with `partial=0`, `phase_drift=0`.
- Later captures increased the sample to 5 market pairs; Motor2 improved distance to late market on 4/5, average cross-entropy delta `-0.007092`.
- 19:41: `20260823_19_10` late was captured at 6.70 minutes before deadline, increasing market pairs to 6.
- 20:09 combined smoke increased paired market races to 8.
- 20:14-20:16 captures added `20260823_19_11` late and `20260823_19_12` early, increasing paired market races to 9.
- 20:18 combined smoke captured `20260823_24_07` late at 6.42 minutes before deadline, increasing paired market races to 10; exact-120 remained intact.
- 20:24 combined smoke captured `20260823_07_12` late at 6.05 minutes before deadline, increasing paired market races to 11.
- 20:31 combined smoke captured `20260823_20_12` late at 6.14 minutes before deadline, increasing paired market races to 12.
- `20260823_24_08` early was attempted inside its 20-30 minute window, but the official page returned zero usable odds; exact-120 gate correctly rejected it and no partial row was saved.
- 20:42 combined smoke captured `20260823_19_12` late at 2.69 minutes before deadline, increasing paired market races to 13.

## Bao dedicated exhibition mid Shadow

Isolated table: `v2_bao_exhibition_shadow_snapshots` (PR #133).

Reason for separation:
- `v2_realtime_exhibition_snapshots` is upserted by `(race_id,snapshot_label,lane)`, so later collection can move `snapshot_at`; it cannot prove first historical availability.
- Live official-page probes showed exhibition data can be absent at 20-30 minutes before deadline and complete closer to the deadline.
- Example live observations: `20260823_19_10` had no complete exhibition data around the earlier window, while official `beforeinfo` was complete in the 10-15 minute region.

Safety/design:
- target window: 8-15 minutes before deadline;
- one frozen row per race;
- require exactly six lanes, six positive exhibition times, and a complete rank permutation `{1,2,3,4,5,6}`;
- re-check window after the official HTTP fetch; window drift is rejected;
- first valid capture is frozen with `on conflict do nothing`;
- paired audit accepts a row only when `market_early_at < exhibition_mid_at < market_late_at`;
- mutable realtime exhibition timestamps and deprecated market-row exhibition fields are ignored;
- no Production decision/LINE changes.

Verified captures by 20:42 JST include:
- `20260823_19_10`: exhibition mid at 9.74 minutes before deadline.
- `20260823_07_11`: exhibition mid at 14.63 minutes before deadline.
- `20260823_20_11`: exhibition mid at 14.74 minutes before deadline.
- `20260823_24_07`: exhibition mid at 10.29 minutes before deadline.
- `20260823_07_12`: exhibition mid at 13.62 minutes before deadline.
- `20260823_20_12`: exhibition mid at 14.31 minutes before deadline.
- `20260823_19_12`: exhibition mid at 13.34 minutes before deadline.
- every stored dedicated row requires six times and a complete six-rank permutation.

## Combined Bao forward smoke

To reduce manual capture overhead without adding any recurring schedule:
- PR #136 added the explicit owner-only Issue #42 command `/railway bao-forward-shadow-smoke CONFIRM`.
- The command loads the Railway DB connection once, runs dedicated exhibition-mid Shadow first, then market early/late Shadow.
- PR #137 extended the same explicit command to run `bao_paired_forward_audit.py` immediately afterward and return sanitized audit diagnostics.
- PR #139 added a read-only next-capture planner. After every combined smoke it reports the next missing market-early, exhibition-mid, and paired-late window plus `BAO_PLAN_NEXT_COMBINED`, reducing no-target manual executions without adding a scheduler.
- The planner was tightened so exhibition-mid recommendations prioritize races with an already frozen early market row.
- PR #142 added supplemental realized-result log-loss summaries to the read-only forward audit. It compares early vs Motor2 and Motor2 vs Motor2+dedicated-exhibition on the same result-ready subsets while leaving the 30-pair gates unchanged.
- There is still no recurring Bao scheduler; captures occur only through an explicit smoke command.
- Only the two isolated Bao Shadow tables are writable; paired audit and capture planner are read-only.
- No Production decision/BUY/WATCH/SKIP/LINE or Railway configuration change is performed.

## Forward audit status

Read-only paired audit compares frozen early de-vigged market probability against actionable late market probability.

Coefficients under forward observation:
- Motor2 beta: 0.06 from PR #108.
- Exhibition-time beta: 0.06 from PR #113, evaluated only with the dedicated 8-15 minute frozen exhibition row.
- Feature definitions were rechecked against PR #108/#113: both forward Motor2 and exhibition score construction match the historical robustness definitions.

Current forward sample after the 20:42 combined smoke:
- market pairs: 13;
- Motor2-ready: 13;
- Motor2 improved distance to late market on 9/13, average cross-entropy delta `-0.004529`;
- safe dedicated exhibition-ready pairs: 7;
- dedicated exhibition improved over Motor2 on 6/7, average additional cross-entropy delta `-0.005281`;
- `20260823_20_12` is the first dedicated exhibition non-improvement example in this Forward sample: exhibition additional delta `+0.003090`; keep it unchanged as genuine Forward evidence.
- realized-result coverage at this observation point: 0; PR #142 will summarize realized outcome log loss automatically once `v2_results` rows are available.

Forward evidence rules:
- earlier tiny-sample exhibition outputs derived from mutable realtime snapshots are invalidated and do not count;
- require at least 30 Motor2-ready paired races for formal Motor2 forward evaluation;
- separately require at least 30 dedicated exhibition-ready paired races for formal exhibition evaluation;
- realized results are required as supplemental evidence before any Production promotion decision;
- 13 market pairs / 7 exhibition pairs are only early observations and are not promotion evidence.

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

1. Continue market early/late and dedicated exhibition-mid forward capture without relaxing exact/completeness gates; next planner target after the 20:42 smoke is `20260823_24_09` market-early at 20:55 JST.
2. Run the paired read-only audit as samples accumulate; require 30 Motor2 pairs and separately 30 dedicated exhibition pairs before formal evaluation.
3. After nightly result ingestion, use the PR #142 realized-result summaries as supplemental Forward evidence; do not promote from late-market proxy alone.
4. Continue one-feature-at-a-time residual OOS screening and keep this file updated after material decisions.
