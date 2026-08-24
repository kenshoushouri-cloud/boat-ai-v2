# Research Update: 2026-08-25 morning milestone

更新日時: 2026-08-25 08:35 JST

この文書は `PROJECT_HANDOFF.md` / `PROJECT_HISTORY.md` の次回統合更新で取り込むための確定マイルストーン記録。GitHub main / Railway PostgreSQL を Source of Truth とし、ここに書かれた状態も再開時には再確認する。

## Current code / safety state

- PR #220 `Audit: independent holdout for maturity-gated motor rates` を CI 5/5、COMMENT review 後に squash merge。
- merge SHA: `84b3b0af6fa0a6c91760c3d26931eaadec3fff15`。
- Production v24、LINE、Railway Variables/settings/schedules、N02、Bao coefficient/promotionは変更していない。
- PR #169 `Draft: temporary 10-minute base-odds refresh` は引き続き Open Draft。明確なprediction/learning valueなしにmergeしない。

## Opponent Pressure Shadow — 2026-08-25 health

Issue #42 `/railway opponent-pressure-forward-health` read-only確認:

- 2026-08-22: 156 / 156R complete
- 2026-08-23: 168 / 168R complete
- 2026-08-24: 144 / 144R complete
- 2026-08-25: 156 / 156R complete
- since-rollout total: 624R
- model version / train_end / fixed arrays / matched-opponents integrity all complete
- `PASS_READ_ONLY`

7-day headline coverage 58.10%は8/19–8/21がrollout前のため。8/22開始後は 624/624R = 100% complete。

Historical OOSではPR #217で meet-day × broad race-band の12 strataすべてが3/3 splitでBrier/LogLoss改善、PR #218で24/24 venuesすべてが3/3 splitでBrier/LogLoss改善。Forward Shadowは継続し、Productionへはまだpromoteしない。

## Venue × meet-day × race-band upset context

PR #212 fixed chronological OOS:

- test total: 45,183R
- M2 = venue × meet-day bucket × broad race band, fixed shrinkage
- M2 vs global: Brier `-0.00014743`, LogLoss `-0.00054213`
- M2 vs venue-only: Brier `-0.00005916`, LogLoss `-0.00020613`

PR #216 exact R01..R12 increment:

- exact-R model was worse than broad-band M2 in all 3 OOS splits
- Combined M3 vs M2: Brier `+0.00008401`, LogLoss `+0.00029520`

Decision: meet-day/race context is useful, but current evidence supports broad bands (`R01-04 / R05-08 / R09-12`) rather than exact R-number coefficients. Venue interaction and shrinkage remain necessary.

## Motor actual 2-place rate — independent holdout

PR #220 uses a genuinely later holdout not used in preceding motor maturity audits:

- Holdout: 2026-08-16..2026-08-24
- five venues with externally verified official current-generation start dates only
- evaluated: 240R
- BASE: fixed `motor2=33`
- ALL_ACTUAL: race-card `motor_place2_rate` for all eligible races
- MATURE_GATE: actual motor2 only when race-level minimum strictly-prior current-generation appearances across all six motors >=21, otherwise BASE
- `21` was frozen before this holdout; no retuning/search.

### Overall

ALL_ACTUAL vs BASE:
- LogLoss: `-0.00354788`
- Brier: `-0.00009918`
- actual-ticket rank: `-0.2583`

MATURE_GATE vs BASE:
- LogLoss: `-0.00322104`
- Brier: `-0.00009354`
- rank: `-0.2542`

MATURE_GATE vs ALL_ACTUAL:
- LogLoss: `+0.00032684`
- Brier: `+0.00000564`
- rank: `+0.0042`

Therefore the independent holdout confirms that **actual motor2 itself remains useful**, but it does **not** validate a hard >=21 appearance cutoff as better than universal actual motor2.

### Maturity interpretation

- P21+: n=236, LogLoss delta `-0.00327563`, Brier `-0.00009513`, rank `-0.2585`.
- P00-20: only n=4. ALL_ACTUAL improved strongly in these four races, but sample is far too small to reverse the prior caution or establish a young-motor rule.

Decision:
- Do not promote the >=21 hard gate.
- Do not conclude young motors are always safe from n=4.
- Treat motor maturity/use-start as **reliability metadata**, not a proven binary cutoff.
- DB first-seen remains forbidden as official generation start.

### Venue heterogeneity in holdout

ALL_ACTUAL LogLoss delta vs BASE:
- V03: `-0.01436944`
- V05: `-0.00087679`
- V12: `+0.00453061` (worse)
- V14: `-0.00380946`
- V23: `-0.00186245`

Four of five verified venues improved, while V12 reversed. This reinforces that the next step is **venue/reliability-aware validation**, not a universal Production substitution based on one aggregate metric.

## Bao formal Forward — sample gates reached, no auto promotion

2026-08-25 Issue #42 `/railway bao-formal-forward-eval`:

Motor:
- ready 133
- improved 75/133
- avg delta `-0.008344`
- median delta `-0.011052`

Exhibition:
- ready 124
- improved 82/124
- avg delta `-0.016289`
- median delta `-0.018346`

Both >=30 formal sample gates are now `READY_FOR_MANUAL_REVIEW`.

However:
- `BAO_FORMAL_AUTO_PROMOTION=DISABLED`
- 馬王型は通常予想のプラスアルファという方針を維持。
- coefficient変更・Production promotionはこの到達だけでは行わない。

## Next normal-prediction priorities

1. Inspect the existing motor Forward/Shadow implementation before creating anything new; avoid duplicate collectors/tables.
2. Continue actual motor2 validation with venue/reliability awareness. Prefer fixed predeclared shrinkage/reliability comparisons over a post-hoc hard cutoff.
3. Investigate V12 reversal without venue cherry-picking; use chronological OOS/Forward and fixed design.
4. Continue Opponent Pressure daily Forward accumulation and evaluate realized incremental lift as days/venues grow.
5. Treat venue × meet-day × broad race-band as a contextual candidate; exact R1–12 granularity is currently rejected.
6. Bao remains manual-review-only supplemental research.
7. PR #169 remains Draft.

No Production model change is authorized by this note alone.
