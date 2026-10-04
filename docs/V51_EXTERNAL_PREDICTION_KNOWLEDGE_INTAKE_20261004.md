# V5.1 external prediction-knowledge intake — 2026-10-04

## Purpose

Use public/official boat-racing prediction knowledge only to discover **testable pre-race features**.
Do not copy public picks or tip-site tickets into the model.

Current Production=V4 and the frozen V5 core remain unchanged.
This document defines a **post-V5 / V5.1 research lane** and must not delay the current matched-backtest critical path.

## Intake principles

A candidate feature is admissible for research only when:
- available before the target race deadline;
- provenance/timestamp can be audited;
- target-race result/payout/odds are not used to construct the feature;
- a fixed transformation can be preregistered before outcome review;
- it can be evaluated on the existing TRAIN_REFERENCE / VALIDATION / OOS chronology and then Forward evidence;
- it does not require a new paid service or material Railway cost without approval.

No feature is promoted because an article or tipster says it works.

## Priority

### P1 — Exhibition ST

Why:
- official BOAT RACE guidance identifies start exhibition, entry-course movement, and start timing as important pre-race information;
- repo already has an isolated fixed Forward Shadow;
- frozen existing research: beta=-0.02, official beforeinfo only, 8–15 minutes before deadline, first-write-wins;
- existing research history already labels it PROMISING_FIXED_OOS_REQUIRE_FORWARD.

Action:
- reuse the existing collector/shadow; do not build a duplicate service/table;
- next research task is a live/frozen evidence checkpoint, not coefficient search.

### P1 — Exhibition time / rank / diff

Why:
- official BOAT RACE guidance says exhibition time measures straight-line speed/伸び足 and can connect to race performance;
- repo already stores exhibition_time, rank and diff from official beforeinfo;
- historical beforeinfo pipeline already supports these fields.

Initial research form:
- within-race standardized/rank-based signal only;
- no venue-specific threshold discovered after seeing outcomes;
- compare incremental probability calibration first, economics second.

### P2 — Start-exhibition course movement

Why:
- official BOAT RACE guidance notes frame number and actual course can differ and calls start exhibition indispensable pre-race information;
- repo already stores exhibition_course / original_course / is_course_changed.

Caution:
- start exhibition course can differ again in the actual race;
- treat it as probabilistic evidence, never as confirmed final course.

Initial research form:
- course_changed flag;
- signed course movement = exhibition_course - frame;
- no hand-tuned venue filters.

### P2 — Weather / water × venue/season interaction

Candidate fields:
- wind speed/direction;
- wave height;
- air/water temperature;
- venue water type / tidal characteristics;
- seasonal venue course-strength priors.

Why:
- official venue guidance publishes seasonal course-performance data and documents venue-specific wind/water effects;
- repo already has realtime/historical weather fields.

Caution:
- high interaction dimensionality creates overfit risk;
- preregister only a small fixed interaction set and require stronger OOS/Forward evidence.

### P3 — Tilt / propeller / parts change

Repo already has tilt, original_tilt, tilt_change and race-condition/parts fields.

Use only as isolated research candidates after P1/P2 because:
- coverage and semantics vary;
- the relationship can be highly venue/racer dependent;
- manual feature mining after outcomes is prohibited.

### P1 — Recent form / L-count

Already known deferred candidates.
Keep behind exhibition and environment features because the current repository already has a separate historical reconstruction/evidence path and the V5 core scope lock explicitly deferred them.

## Explicitly excluded from this intake

- paid/free tip-site ticket copying;
- consensus of public predictions as a direct model input;
- post-result commentary;
- current aggregate values backcast into old races without as-of proof;
- odds/EV as a formal selector change;
- post-hoc venue/race-band thresholds;
- automatic Production promotion.

## Admission gate for any V5.1 feature

1. Freeze one feature definition before seeing its evaluation outcomes.
2. Demonstrate timestamp-safe coverage.
3. TRAIN_REFERENCE is descriptive only; no repeated threshold search.
4. VALIDATION and OOS must show consistent incremental value versus frozen V4/V5 baseline.
5. Prefer probability-quality improvement (LogLoss/Brier/calibration) plus economics; ROI alone is insufficient.
6. Require prospective Forward reproduction.
7. Production change requires a separate explicit human approval.

## Research order — updated 2026-10-04

1. **Recent Form last-5** — first new V5.1 candidate; preregistered separately.
2. Exhibition time fixed incremental test.
3. Start-exhibition course movement fixed incremental test.
4. Small preregistered weather/water interaction test.
5. Tilt/parts only after the above.

Exhibition ST remains research-only but is no longer first priority: candidate-v4 read-only run `37185447967` evaluated 2,050/2,050 timing-clean rows and the frozen beta=-0.02 slightly worsened overall tri Brier, LogLoss and actual-ticket rank versus BASE. Do not retune beta after seeing this result.

`V51_EXTERNAL_INTAKE / OFFICIAL_FIRST / EXHIBITION_P1 / NO_TIP_COPY / NO_POST_HOC / NO_PROD_CHANGE`

## Collection vs adoption policy

- **Collection and model adoption are separate decisions.**
- Continue collecting potentially useful pre-race information even when it is not currently used by V4/V5, provided collection is timestamp-safe, low-cost, and does not require a new paid service/material Railway expansion without approval.
- A collected feature enters the prediction model only when frozen TRAIN/VALIDATION/OOS and prospective Forward evidence show incremental improvement versus the frozen baseline.
- If a feature worsens probability quality or fails to reproduce Forward, keep collecting it for future research but do not use it in Production prediction.
- Do not stop a useful collector merely because the current coefficient/model use is rejected; first assess storage/cost and future research value.
- Periodically re-evaluate stored unused features when the baseline model, sample size, or interaction set materially changes.

`COLLECT_BROADLY_LOW_COST / ADOPT_ONLY_IF_INCREMENTAL / KEEP_UNUSED_EVIDENCE / NO_AUTO_PROMOTION`
