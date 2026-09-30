# Boat AI — System Purpose, Operating Timeline, and Handoff

> **SUPERSEDED FOR CURRENT OPERATIONS**
>
> この2026-09-29版は履歴として保持する。
> 最新の完全版は **`docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`**。
> 次チャットは必ず9/30版を優先して読む。


## Handoff baseline — 2026-09-29 17:10 JST

This document is the high-level handoff for the current boat-racing AI project.

For exact current operational/evidence values, always read these files first:
1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. this document

GitHub `main` is the code Source of Truth.
Railway PostgreSQL is the Production-data Source of Truth.

Do not assume a SHA, count, deployment, Cron, or evidence state from an older section is still current. Re-read GitHub main / open PRs / CI / Railway Production before acting.

---

## 1. System purpose

The project is building a boat-racing prediction and selection system whose objective is:

> **to identify a repeatable, timing-safe, prospectively validated betting policy that can sustain positive economics over time, while avoiding result leakage, retrospective reconstruction, and post-outcome overfitting.**

The goal is not:
- to maximize one-day ROI;
- to force a bet every day;
- to increase race count for appearance of activity;
- to claim guaranteed profitability from a backtest;
- to optimize historical outcomes after seeing results.

A day with 1–3 strong races is acceptable if that is economically superior.
A day with no valid formal prospective artifact is also acceptable and must remain unavailable.

The current target is to build a **V5 research candidate**, while Production itself remains V4.

---

## 2. Current generations

### Production: V4

Production remains the frozen V4 baseline.

Current probability / selection contract:
- racer class;
- national win rate;
- national place2 rate;
- local place2 rate;
- average ST;
- venue/course bias;
- Racer Course coefficient **0.50**;
- Opponent Pressure coefficient **1.0**, first-place-only;
- Motor2 beta **0.06**;
- probability temperature **2.20**;
- selector signals:
  - `head_p1`
  - `head_margin`
  - `top3_mass`
  - `concentration`
- formal TOP6 races;
- formal TOP2 tickets;
- formal selector does not read odds/EV;
- missing Course/Opponent/Motor remains neutral;
- `purchase_action=false`.

Do not change this Production contract without explicit approval.

### Research target: V5 core

The project now treats the next-generation work as a V5 research candidate rather than another informal V4 coefficient tweak.

Target:
- **2026-10-15 V5 core freeze review**

This means:
- mandatory prospective evidence gates are mature enough to review;
- a V5 core research specification can be deliberately frozen;
- that frozen specification can enter another Forward phase.

It does **not** mean:
- long-run ROI >100% is proven;
- V5 is automatically promoted to Production;
- purchase is enabled.

---

## 3. V5 scope lock through 2026-10-15

The V5 core scope is intentionally locked to prevent feature creep.

Mandatory evidence:
1. formal V4: **>=20 resolved FORMAL_AVAILABLE days**;
2. S03_M2: **>=100 officially evaluated observations**;
3. evidence contract remains clean.

Current settled state through 2026-09-28:
- V4: **8 / 20**, remaining 12;
- S03_M2: **63 / 100**, remaining 37;
- status: `COLLECTING_CORE_EVIDENCE`.

If all future formal days are valid, the V4 20-day point is roughly around 2026-10-11. Missing/unavailable days shift this later.

Optional layers do not block the V5 core milestone.

### Optional: day-strength shadow

Frozen admission gate:
- >=10 future resolved days from 2026-09-28 onward;
- >=3 KEEP_SHADOW;
- >=3 SKIP_SHADOW.

Current:
- 2026-09-28 = `SKIP_SHADOW`;
- future classified/resolved days: 1;
- KEEP: 0;
- SKIP: 1;
- 2026-09-29 = unavailable, no label.

If the natural KEEP/SKIP mix is not ready by 10/15:
- do not lower the gate;
- do not manufacture volume;
- keep day-strength shadow-only;
- freeze V5 core without it.

### Optional: F-count

F-count is not required for the 10/15 core milestone.

Still forbidden without explicit approval:
- live capture activation;
- persistence/schedule;
- historical backfill;
- historical coefficient search.

Existing F-count PR chain is research infrastructure/provenance only.

### Deferred to later V5.1 research

Do not add to the 10/15 core merely because time remains:
- recent_form;
- L-count;
- exhibition ST;
- exhibition time;
- weather/water;
- odds/EV selector;
- new unpreregistered features.

---

## 4. Current economic evidence

### Formal V4 TOP2 — settled through 2026-09-28

Canonical settled state:
- resolved formal days: **8**;
- settled races: 44;
- head accuracy: **63.6364%**;
- bets: 88;
- hits: 12;
- investment: 8,800 JPY;
- return: 13,000 JPY;
- profit: **+4,200 JPY**;
- ROI: **147.7273%**;
- second chronological half ROI: **135.2083%**;
- leave-one-day worst ROI: **112.3684%**;
- leave-one-hit minimum ROI: **109.4186%**;
- bootstrap P(ROI>100%): **85.63%**;
- remaining to 10-day review: **2 valid resolved formal days**.

2026-09-28 single-day formal:
- 12 bets;
- 1 hit;
- investment 1,200 JPY;
- return 660 JPY;
- profit **-540 JPY**;
- ROI **55.0%**.

The preregistered 9/28 day-strength classification was `SKIP_SHADOW`, so that shadow would have avoided this one-day loss. This is one-day descriptive evidence only and is not a promotion rule.

### S03_M2 — settled through 2026-09-28

Current:
- evaluated: **63**;
- invalid: 1;
- pending: 0;
- hits: 4;
- investment: 6,300 JPY;
- return: 10,120 JPY;
- profit: **+3,820 JPY**;
- ROI: **160.6349%**;
- max DD: 2,000 JPY;
- max losing streak: 20;
- first-half ROI: 268.0645%;
- second-half ROI: **56.5625%**;
- bootstrap P(ROI>100%): **77.61%**;
- remaining to 100 review: **37**.

Interpretation:
- overall economics remain positive so far;
- recent-half weakness is material;
- do not retune;
- continue frozen to 100 evaluated observations.

---

## 5. Daily operating timeline

All times are JST unless stated otherwise.

### Morning prospective phase

**08:15**
- source cutoff reference.

**08:16 nominal**
- GitHub scheduled prospective-freeze primary is expected around this time.
- This path is operationally unreliable because GitHub scheduled delivery has repeatedly been delayed by hours.

**08:25 current Production fallback**
- Railway service:
  `candidate-discovery-v4-fallback-dispatcher`
- current Cron:
  `25 23 * * *` UTC = **08:25 JST**.

**08:32**
- availability hard-stop used by the prospective contract.

Formal freeze must complete before all applicable feed/core deadlines.

No outcome/result/payout information may enter before the formal artifact is frozen.

### During the day

- formal V4 evidence remains immutable;
- day-strength, if available, is classified from immutable pre-result artifacts only;
- no result-based retuning;
- no unavailable-day reconstruction.

### Nightly settlement

**23:30**
- Production `cron-nightly-results`.

Historical recent completion has commonly been around 23:38–23:42, but actual readiness must be checked from data rather than time alone.

After results are terminal:
- run/read the combined checkpoint;
- settle frozen V4 evidence;
- update S03_M2;
- update V5 milestone progress;
- keep invalid/cancelled races void at zero investment.

---

## 6. 2026-09-29 fallback incident and current safe Production state

An explicitly approved attempt moved the Railway fallback Cron from 08:25 to 08:20.

The first live cycle exposed a code/config mismatch.

Observed:
- Railway Cron was 08:20;
- dispatcher decision occurred at **08:23:33**;
- code returned:
  `action=NOT_DUE reason=before_0825_checkpoint`;
- no fallback workflow_dispatch was created.

Root cause:
- `research/candidate_discovery_v4_fallback_dispatcher.py` still had an internal checkpoint at 08:25.

The natural GitHub schedule was also unusable:
- run `36513182505`;
- started around **11:33 JST**;
- after the 08:32 hard-stop and feed deadline;
- correctly failed closed.

Therefore:
- **2026-09-29 has no valid formal prospective V4 artifact**;
- do not reconstruct;
- do not backfill;
- do not create a 9/29 day-strength label;
- do not count 9/29 toward formal V4/day-strength gates.

Production was immediately rolled back.

### Current safe fallback state

Current Railway read-back:
- Cron: **08:25 JST** / `25 23 * * *`;
- latest dispatcher deployment: SUCCESS;
- source repo/branch unchanged;
- start command unchanged;
- runtime/region/replica unchanged;
- pending work: none;
- staged/unmerged config: none.

This is the current safe Production state.

---

## 7. Draft PR #452 — 08:20 code alignment

Open Draft:
- PR #452 `Fix: align fallback dispatcher checkpoint to 08:20 JST`;
- head: `73dd7f593be1199edf32bb0710458548a6d2d32d`;
- mergeable: true;
- all CI SUCCESS.

#452 changes:
- internal dispatcher checkpoint 08:25 -> 08:20;
- activation manifest aligned to 08:20;
- tests verify:
  - 08:19:59 => NOT_DUE / no GitHub call;
  - exactly 08:20 => fallback dispatch permitted.

**#452 is not merged.**

A fresh explicit approval is required before:
- merging #452 if it changes Production fallback behavior;
- reactivating Production fallback Cron from 08:25 to 08:20.

Do not reuse the earlier approval as authorization for this new code+Cron activation cycle.

---

## 8. Handoff work priorities

### Priority A — preserve evidence integrity

Always:
- freeze candidate/artifact before result access;
- fail closed on missing/late evidence;
- never reconstruct unavailable formal days;
- keep cancelled/invalid zero-investment;
- separate historical evidence from prospective evidence.

### Priority B — restore fallback safety correctly

Safe work without approval:
- read-only analysis;
- additional #452 tests;
- activation/rollback manifest validation;
- Draft PR work;
- CI;
- docs.

Requires approval:
- #452 merge if Production behavior changes;
- Railway Cron 08:25 -> 08:20 reactivation.

The next attempted 08:20 activation must align both:
1. Railway Cron;
2. dispatcher internal checkpoint.

### Priority C — continue V5 evidence collection

Continue:
- formal V4 resolved-day accumulation;
- S03_M2 frozen observation accumulation;
- combined review packet;
- V5 progress tracking.

Do not retune from one day or one loss/win.

### Priority D — optional day-strength

Continue only on days with valid formal prospective artifacts.

Never create a label for an unavailable formal day.

### Priority E — deferred work

Do not let optional features derail the 10/15 core milestone.

---

## 9. Source-of-truth / approval rules

### Safe without extra approval

- read-only audits;
- historical research without leakage;
- prospective Forward evaluation;
- Draft PR creation/update;
- CI;
- docs/handoff;
- pure/offline helpers;
- evidence collection that does not mutate Production.

### Explicit approval required

- merge/activation of a Production-effect PR;
- Railway Production Variables / Cron / service / volume / migration changes;
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM;
- Production model/coefficient/threshold/candidate/stake changes;
- live F-count capture/persistence/schedule;
- LINE real-send;
- purchase activation;
- paid/external actions.

### Forbidden

- historical F-count snapshot backfill after outcomes;
- historical F-count coefficient search;
- recent_form post-outcome reconstruction;
- loosening gates/thresholds merely to create volume/profit;
- reconstructing unavailable formal days;
- Railway plaintext variable enumeration/display;
- `railway variable list`;
- automatic purchase activation.

---

## 10. Files / PRs to read first in the next chat

First:
- `docs/PROJECT_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260929.md`

Then:
- Draft PR #452 — fallback 08:20 code alignment;
- PR #409 — formal V4 evidence provenance;
- PR #405 — S03_M2 evidence provenance;
- PR #412 — fallback timing/activation/rollback provenance;
- PR #413 — F-count compatibility, still not live-approved.

Also re-fetch:
- current main;
- open PRs;
- relevant CI;
- Railway Production status/config/deployments.

---

## 11. Immediate next-chat checklist

1. Re-read the three handoff files.
2. Re-fetch current main/open PRs/CI/Railway Production.
3. Confirm fallback is still **08:25 JST**.
4. Confirm #452 remains unmerged unless new explicit approval was given.
5. Preserve 2026-09-29 as unavailable.
6. Continue read-only settlement/evidence work for later dates.
7. Keep V5 target at 2026-10-15 without lowering evidence gates.
8. Do not alter Production V4 model/selector/TOP6/TOP2/stake without explicit approval.

Current gate:

`PROD_FALLBACK_0825_SAFE / PR452_GREEN_DRAFT_NOT_MERGED / 929_FORMAL_UNAVAILABLE / V4_8_OF_20_ROI_147_73 / S03_63_OF_100_ROI_160_63 / V5_TARGET_20261015 / NO_RETUNE / PURCHASE_FALSE`
