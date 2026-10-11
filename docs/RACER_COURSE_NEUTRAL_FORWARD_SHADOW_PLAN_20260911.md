# Racer Course neutral-missing forward-shadow integration plan

Status: `DESIGN_ONLY / RESEARCH_ONLY / NO_PRODUCTION_CHANGE / NO_DEPLOYMENT`

This plan converts the fixed, post-study-supported Course missing-row neutral rule into a prospective shadow experiment without changing v24/FINAL, BUY/WATCH/SKIP, LINE, thresholds, Railway Production configuration, or purchase behavior.

## 1. Frozen model contract

The shadow must import/use the pure contract in `research/racer_course_neutral_forward_contract.py` without adding a runtime coefficient setting.

Frozen rules:
- BASE is the current v24 PRE raw strength path.
- Course coefficient is exactly **0.50**.
- Course evidence key is exact `(racer_number, race_date, course=lane)`.
- Top3 must be finite and within `[0,100]`.
- source row must be from the target race date.
- `created_at <= 08:15 JST` and `created_at < race deadline`.
- only timing-safe observed lanes are z-scored against each other.
- unavailable/missing lanes receive Course z=0, leaving BASE raw strength exactly unchanged.
- fewer than two usable lanes, or effectively zero observed SD, means the entire Course adjustment is zero.
- no later snapshot repair or fallback to a different date/course/racer.

No environment variable or database column may override the coefficient or missing-lane rule.

## 2. Shadow isolation

The experiment must be unable to influence Production decisions.

Required isolation:
- separate shadow collector/script; do not edit the current v24/FINAL decision path;
- separate shadow table or immutable shadow artifact namespace;
- no write to Production prediction/candidate/decision tables;
- no import/call from BUY/WATCH/SKIP, LINE or purchase entrypoints;
- no LINE token required by the shadow service;
- no purchase variable/credential required;
- no automatic Production promotion;
- first-write-wins for a race/day snapshot; no outcome-time overwrite.

A CI isolation check must fail if the shadow module is imported by current Production notifier/decision modules.

## 3. Proposed immutable shadow record

If a database-backed Forward shadow is later approved, prefer one compact row per race. Proposed logical fields:

- `race_id` primary key
- `race_date`
- `venue_id`
- `race_no`
- `shadow_version` fixed text/code
- `base_version` fixed `v24`
- `course_coef` fixed `0.50` with a DB check if persisted
- `racer_numbers[6]`
- `usable_course_lanes[6]` or a six-slot boolean mask
- `course_top3[6]` with missing slots preserved
- `course_snapshot_created_at[6]` with missing slots preserved
- `course_unavailable_reason[6]` encoded compactly
- `base_raw[6]`
- `course_z[6]`
- `adjusted_raw[6]`
- immutable BASE trifecta probability vector in canonical 120-ticket order
- immutable Course-neutral trifecta probability vector in the same order
- `created_at`

All six-lane arrays must have cardinality six; probability arrays must have exactly 120 entries, be finite/nonnegative and sum to one within a fixed tolerance.

The shadow table must not contain payout, odds, purchase recommendation, stake, candidate class, or LINE state.

## 4. Forward timing sequence

The Course shadow must consume only naturally collected morning source rows.

Current observed sequencing on 2026-09-11:
- data preparation completed by about 06:53 JST;
- Racer Course natural collector starts at 07:15 JST and completed at 07:36:29 JST;
- fixed Course evidence cutoff is 08:15 JST.

Therefore a future approved shadow schedule should be after normal Racer Course completion but still leave a substantial cutoff margin. The exact Railway Cron time is a separate Production-infrastructure approval item and is **not selected or configured by this design note**.

Collector runtime itself must enforce the 08:15 cutoff and every target race deadline; scheduler timing alone is not evidence.

If the Course collector has not completed naturally, the shadow must fail closed. It must not manually rerun/backfill the source collector.

## 5. Coverage observability

Each natural shadow run must report before any result is available:
- target races and exact-six-entry races;
- counts by usable Course lanes 0..6;
- complete6 vs missing1plus race counts;
- unavailable reasons by lane/race: missing row, racer mismatch, course/lane mismatch, wrong date, invalid Top3, naive timestamp, after 08:15, at/after deadline;
- shadow rows written vs already-existing rows;
- minimum/maximum decision snapshot time;
- postcondition counts verifying immutable row cardinalities/version/timing.

The exact required-course read-only audit added in PR #329 remains the reference observability path. Racer-level collector success must never be substituted for exact `(racer, course)` coverage.

## 6. Prospective evaluation gate

Historical support is not sufficient. Before any Production promotion review, collect natural Forward shadow evidence under the frozen rule.

Minimum prospective gate proposed for a later approval review:
- at least **10 natural race dates**;
- at least **1,000 evaluated races** overall;
- at least **300 MISSING1PLUS** races;
- at least **10 distinct venues** represented in MISSING1PLUS;
- zero shadow rows created after 08:15 JST or at/after race deadline;
- zero later mutations (`updated_at > created_at`) if an updated timestamp exists;
- zero evidence-key substitutions or later-snapshot repairs.

After results become available, compare Course-neutral vs the BASE vector saved at the same decision snapshot:
- paired LogLoss and Brier primary;
- actual-ticket probability rank secondary;
- Top1/3/5/10 descriptive;
- complete6 and missing1plus separately;
- deterministic race-level bootstrap, 5,000 resamples, seed fixed before the first prospective outcome evaluation.

Do not tune 0.50, the z=0 missing rule, date/venue filters, or sample inclusion after prospective results are observed.

## 7. Interaction with Opponent Pressure

Course-neutral shadow should be validated independently first.

Opponent Pressure is currently undergoing a separate five-day natural timing gate on the dedicated 07:00 JST Railway collector. Do not combine Course-neutral and Opponent Pressure in a new Forward shadow until:
- Opponent completes the existing prospective timing gate;
- its source rows are timing-clean and immutable;
- a separate combined-shadow contract is frozen before combined outcomes are evaluated.

The fixed historical combined research (Course 0.50 + Opponent 1.0) remains evidence, not permission to combine live paths automatically.

## 8. Approval boundary

The following are **not authorized** by this plan and require explicit approval:
- merging any Forward-shadow collector into main if main auto-deploys Production services;
- creating a new DB table in Production;
- creating or changing Railway services/Cron/variables;
- any writes to Production PostgreSQL beyond a separately approved shadow table;
- connecting shadow outputs to v24/FINAL, candidate selection, LINE or purchase;
- Production promotion after the prospective gate.

Until approved, work remains limited to pure-function contracts, CI, documentation and read-only historical/Forward audits.
