# boat-ai-v2 Daily Handoff — 2026-09-10 JST

This snapshot supplements the older permanent handoff without rewriting prior history.

## Verified GitHub state
- main: `033db7ea2bcd06f49742aa7dbf21dfa375fa0fb6`
- PR #320 `Fix v21 official trifecta odds parsing and fail-closed fallback`: squash-merged to main.
- PR #319 `Research: audit 2026-09-08 odds evidence (read-only)`: closed without merge after remediation was delivered separately by #320.
- PR #169 `Draft: temporary 10-minute base-odds refresh`: closed without merge; do not reactivate from old assumptions.
- Production model/threshold promotion from the 2026-09-08 historical odds evidence remains BLOCKED because historical market values were not independently authenticated.

## #320 production remediation — live validation
Natural Railway Cron executions after the #320 deployment were inspected read-only.

`cron-learning-all`:
- 08:30 JST: safe collector active. Two races saved exact 120-ticket direct `official_odds3t` snapshots; one not-yet-complete race returned `odds=0` and failed closed instead of propagating partial fallback.
- 08:45 JST: the previously incomplete target and the other target both saved exact 120-ticket direct `official_odds3t` snapshots.
- 09:00 / 09:15 / 09:30 JST: all observed targets saved exact 120-ticket direct `official_odds3t` snapshots.

`cron-final-check`:
- 09:01 / 09:15 / 09:31 JST: safe `v21_realtime_collector_pg_safe.py` path active.
- Each observed run collected two targets at 120 tickets each (`saved_odds_rows=240`).
- The decision engine reported the observed targets odds-ready; no partial base-odds fallback propagation was observed.

Post-deploy log checks over the observed window found zero `v2_odds_trifecta_fallback` entries in both FINAL and learning services.

Operational status of this defect: **LIVE_VALIDATED**.
This does not retroactively authenticate 2026-09-08 market odds or approve historical ROI.

## Railway state
- Project: `boat-v2-postgres`
- `postgres-recovery`: unchanged, 1 replica, latest deployment SUCCESS.
- GitHub-linked application deployments from #320 completed successfully for the relevant services.
- Existing unrelated Railway environment patch remains **STAGED with 174 changes** and was not accepted/applied.
- No manual Railway config, Variable, Cron, DB-service, or deployment mutation was made during the live validation.

## Opponent Pressure Forward — current read-only evidence
Latest integrity health through 2026-09-10:
- storage rows: **2,724**
- first date: 2026-08-22
- latest date: 2026-09-10
- 2026-09-04..2026-09-10: **1,020 / 1,020 races**, 100% Shadow coverage, 7/7 full days

Latest realized Forward report through 2026-09-10:
- Shadow rows: **2,724**
- evaluated: **2,400**
- pending: **324**
- malformed: 0
- integrity skip: 0
- win Brier: `0.10301976 -> 0.10146546` / delta **-0.00155430**
- top3 Brier: `0.20731329 -> 0.20343500` / delta **-0.00387829**
- winner LogLoss: `1.27901054 -> 1.25830612` / delta **-0.02070442**
- winner rank: `1.9742 -> 1.9629` / delta **-0.0112**

All reported realized dates from 2026-08-22 through 2026-09-09 improved win Brier, top3 Brier, and winner LogLoss versus the stored baseline; rank improvement was not universal by day.

Interpretation remains **PROMISING_FORWARD_RESEARCH_ONLY** and **BLOCK_NO_PRODUCTION_CHANGE**. Do not tune the fixed coefficient or add post-hoc date/venue/race-band filters from these results.

## Current safe next work
1. Continue fixed Opponent Pressure Forward evidence and perform the already-designed read-only incremental comparison against current v24 before any manual promotion review.
2. Continue Racer Course Top3, Exhibition ST, and GUARD05 fixed Forward evidence without retuning coefficients/filters.
3. Keep Bao as auxiliary research with its formal gates; no automatic promotion.
4. Keep monitoring live odds acquisition only as a data-quality concern; the #320 realtime parser/fallback defect itself is live-validated.

## Safety / connection boundary
- Code source of truth: GitHub main.
- Production data source of truth: Railway PostgreSQL.
- Never record Railway tokens, DB URLs/passwords, LINE tokens, or personal identifiers in GitHub documents or reports.
- No Production BUY/WATCH/SKIP, LINE, model coefficient, threshold, Railway Variable/Cron, or DB schema mutation is authorized by this handoff.

This file records facts observed on 2026-09-10 JST and should not be treated as a replacement for future live verification.