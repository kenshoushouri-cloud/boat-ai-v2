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

### Incremental value over current v24
Draft research PR #322 runs the already-designed fixed-coefficient incremental audit against the current v24 lane-strength baseline without writes or tuning.

Read-only result through 2026-09-10:
- Shadow: **2,724**
- evaluated: **2,579**
- pending: **145**
- integrity skip / missing entries: **0 / 0**
- winner Brier: `0.12915852 -> 0.12817352`, delta **-0.00098501**
- winner LogLoss: `1.62306091 -> 1.60802117`, delta **-0.01503974**
- winner rank: `2.3897 -> 2.3447`, delta **-0.0450**

Fixed pre-existing race bands:
- R01-04 n=860: Brier **-0.00077701**, LogLoss **-0.01221327**, rank **-0.0884**
- R05-08 n=860: Brier **-0.00019291**, LogLoss **-0.00299867**, rank **+0.0314**
- R09-12 n=859: Brier **-0.00198627**, LogLoss **-0.02992459**, rank **-0.0780**

Non-selective stability decomposition:
- 17 dates: Brier better **16/17**, LogLoss better **16/17**, all three metrics better **13/17**
- 24 venues: Brier better **19/24**, LogLoss better **20/24**, all three metrics better **12/24**
- 2026-08-24 was the only observed date with both Brier and LogLoss worsening
- venue heterogeneity remains; venues 03, 05, 10, and 22 worsened on both Brier and LogLoss, while venue 11 was effectively flat/slightly worse on Brier but better on LogLoss

These weak groups are **not** being removed after observing results. The decomposition is a stability diagnostic, not a post-hoc filter design.

Interpretation remains **PROMISING_INCREMENTAL_FORWARD_RESEARCH_ONLY / BLOCK_NO_PRODUCTION_CHANGE**. The evidence is substantially broader than the older checkpoint, but venue heterogeneity and the still-pending current-day results mean no Production coefficient/threshold change is authorized.

## Current safe next work
1. Continue fixed Opponent Pressure Forward collection and repeat the unchanged current-v24 incremental audit as additional dates realize; do not tune coefficient 1.0 or create post-hoc venue/race-band filters.
2. Continue Racer Course Top3, Exhibition ST, and GUARD05 fixed Forward evidence without retuning coefficients/filters.
3. Keep Bao as auxiliary research with its formal gates; no automatic promotion.
4. Keep monitoring live odds acquisition only as a data-quality concern; the #320 realtime parser/fallback defect itself is live-validated.

## Safety / connection boundary
- Code source of truth: GitHub main.
- Production data source of truth: Railway PostgreSQL.
- Never record Railway tokens, DB URLs/passwords, LINE tokens, or personal identifiers in GitHub documents or reports.
- No Production BUY/WATCH/SKIP, LINE, model coefficient, threshold, Railway Variable/Cron, or DB schema mutation is authorized by this handoff.

This file records facts observed on 2026-09-10 JST and should not be treated as a replacement for future live verification.