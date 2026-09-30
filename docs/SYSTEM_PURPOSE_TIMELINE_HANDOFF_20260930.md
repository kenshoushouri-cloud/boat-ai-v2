# Boat AI — Comprehensive System Purpose / Timeline / Work Handoff

## Latest comprehensive handoff — 2026-09-30 14:21 JST

This document is the **current high-level handoff** for the boat-racing AI project.

For every new chat/session, read in this order:

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
4. then re-fetch current GitHub `main`, open PRs, CI, Railway Production, and current DB/evidence state before acting.

GitHub `main` is the code Source of Truth.
Railway PostgreSQL is the Production-data Source of Truth.

Do not trust an old SHA, count, Cron, deployment, ROI, acquisition range, or PR state without re-reading the current sources.

---

## 1. Project purpose

The project is building a boat-racing prediction / selection / notification system whose practical objective is:

> **produce a repeatable, timing-safe, prospectively validated positive-economics policy that can be operated reliably, while preventing outcome leakage, post-result reconstruction, overfitting, and unsafe automatic purchase.**

Operational goals:

- identify roughly **1–3 high-quality notification races/day** when naturally available;
- zero-bet / zero-notification days are acceptable when quality is insufficient;
- long-run ROI must be >100%, but ROI alone is not sufficient;
- practical monthly planning target is **+50,000 JPY net profit/month**;
- risk must also be controlled: drawdown, losing streak, hit concentration, chronological degradation;
- automatic purchase remains disabled until separately approved.

The monthly +50,000 JPY target is a **scaling objective, not a selector-retuning objective**.
Never loosen thresholds or manufacture candidate volume merely to hit a monthly profit number.

---

## 2. Current generations

### Production baseline: V4

Production prediction/selection remains the frozen V4 baseline.

Core inputs / contract:

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
  - `concentration`;
- formal **TOP6 races**;
- formal **TOP2 tickets**;
- formal selector does not use odds/EV;
- missing Course/Opponent/Motor remains neutral;
- stake unchanged;
- `purchase_action=false`.

Do not modify model / coefficient / selector / threshold / stake / LINE real-send behavior without a separate Production proposal and approval.

### Research target: V5 core

Target review date:

- **2026-10-15**

This means a V5 core specification should be ready for deliberate review/freeze if the evidence gates mature.
It does **not** mean guaranteed profit, automatic Production promotion, or purchase activation.

Mandatory V5 core gates:

1. formal V4: **>=20 resolved FORMAL_AVAILABLE days**;
2. S03_M2: **>=100 officially evaluated observations**;
3. evidence contract remains clean.

Settled evidence currently recorded through 2026-09-28:

- V4: **8/20**
- S03_M2: **63/100**
- V4 ROI: **147.7273%**
- V4 profit: **+4,200 JPY**
- S03_M2 ROI: **160.6349%**
- S03_M2 profit: **+3,820 JPY**
- S03_M2 second-half ROI: **56.5625%**

2026-09-29 formal V4 is permanently **UNAVAILABLE** because of the fallback timing incident.
Do not reconstruct it and do not count it.

Later dates must be re-settled/read from current evidence before changing these counts.

---

## 3. Economic objective: monthly +50,000 JPY

The project now explicitly tracks:

- monthly net profit target: **+50,000 JPY**

At flat 100 JPY/ticket, 30 days/month, TOP2:

- 1 notified race/day -> 6,000 JPY monthly investment -> required ROI **933.33%**
- 2/day -> 12,000 JPY -> required ROI **516.67%**
- 3/day -> 18,000 JPY -> required ROI **377.78%**

Therefore the desired 1–3 race/day frequency cannot by itself create +50,000 JPY at a 100-JPY stake unless ROI is unrealistically high.

At the currently recorded formal V4 economics:

- 6 races/day;
- 2 tickets/race;
- 100 JPY/ticket;
- ROI 147.7273%;

the descriptive 30-day projection is about:

- investment: **36,000 JPY**
- profit: **+17,182 JPY**

This is not a forecast; it is feasibility arithmetic.

Correct economic sequence:

1. prove prospective edge;
2. measure natural quality-backed volume;
3. confirm conservative robustness:
   - later-half ROI;
   - leave-one-day/hit sensitivity;
   - drawdown;
   - losing streak;
   - concentration;
4. define bankroll / risk limits;
5. only then review stake scaling as a separate Production change.

Merged PR #461 adds the monthly target block to the routine combined V5 checkpoint.

Never raise stake just to force the +50,000 JPY target.

---

## 4. Daily operating timeline

All times are JST unless stated otherwise.

### 08:15 — source cutoff reference

Prospective evidence must respect the pre-result/predeadline contract.

### 08:16 — nominal GitHub primary schedule

GitHub scheduled delivery has previously been delayed, so it cannot be trusted as the only path.

### 08:20 — Railway fallback

Current Production fallback service:

- `candidate-discovery-v4-fallback-dispatcher`
- service ID: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- Cron: `20 23 * * *` UTC = **08:20 JST**

PR #452 was merged and aligned the internal dispatcher checkpoint to 08:20.

Current Railway read-back at 2026-09-30 14:21 JST:

- Cron: **08:20 JST**
- latest deployment: `839be48f-af8f-4a53-8ba4-5b8abdc13f8a`
- status: **SUCCESS**
- commit: `647a43e60d627938e55de4239af15265819659bd`
- staged config: none

### 08:32 — availability hard-stop

If evidence cannot be frozen within the formal timing contract, fail closed.

Never reconstruct a missed formal day after results are known.

### During the day

- formal artifact remains immutable;
- optional shadow labels may be generated only from valid pre-result evidence;
- no result-based retuning;
- no candidate replacement after outcome knowledge.

### 23:30 — nightly results

Production nightly results run at approximately 23:30 JST.

Do not settle by clock alone.
Confirm DB terminal readiness first.

After results are terminal:

- settle exact frozen V4 evidence;
- update S03_M2;
- update combined V5 checkpoint;
- update monthly +50,000 feasibility gap;
- invalid/cancelled races remain zero-investment voids.

---

## 5. 2026-09-29 fallback incident

Historical incident:

- Railway Cron was moved to 08:20;
- dispatcher code still had an internal 08:25 checkpoint;
- at 08:23:33 JST it returned:
  `action=NOT_DUE reason=before_0825_checkpoint`;
- no fallback dispatch occurred;
- natural GitHub schedule later started around 11:33 JST and correctly failed closed.

Result:

- **2026-09-29 formal V4 artifact is unavailable**
- no reconstruction;
- no backfill;
- no day-strength label;
- no V4 resolved-day count increment.

The mismatch was fixed by merged PR #452.
Current code and Railway Cron are both aligned to 08:20.

---

## 6. F-count policy

### Prospective F-count

Merged PR #460 activated future-only F-count companion capture.

Contract:

- run only after a valid formal V4 freeze;
- exact formal six races;
- lanes 1..6;
- exact 36 rows;
- read only `race_id,lane,f_count`;
- PostgreSQL READ ONLY;
- separate hash-bound companion artifact;
- failure is isolated and cannot invalidate the formal V4 artifact;
- no rerank/replacement;
- no LINE/stake/purchase change.

F-count remains optional for V5 core and is mainly a V5.1 evidence stream.

### Historical F-count — current approved interpretation

Earlier blanket prohibition on historical F-count backfill has been superseded.

Current approved rule:

- **official target-day pre-race racelist/B-file F-count may be used as historical predeadline input** because it is naturally available before the race deadline;
- provenance must be retained;
- historical reconstructed data must remain separately labeled from prospective timestamp-clean data;
- do **not** use historical F-count for outcome-guided coefficient/threshold fishing;
- Production model changes remain separately controlled.

---

## 7. Historical missing-data acquisition strategy

Historical acquisition is now an active priority.

Purpose:

- determine whether poor 2025-07 onward backtests were partly caused by incomplete/mismatched historical inputs;
- reconstruct a closer matched-contract historical dataset;
- keep historical evidence separate from prospective Forward evidence.

Historical truth rule:

> use the value that would have been available before the target race deadline.

Allowed historical input classes:

1. BOAT RACE official target-day pre-race program/racelist/B data;
2. BOAT RACE official prior-only reconstruction from events strictly before the target race deadline;
3. external pre-race archives when their semantics establish pre-race availability;
4. 艇国データバンク as supplemental gap-fill/cross-check when an as-of cutoff can be proven.

Never use target-race outcome information to construct features.

Historical evidence does **not** count toward:

- V4 20 resolved prospective days;
- S03_M2 100 prospective observations.

### Source priority

Preferred order:

1. **BOAT RACE official**
2. approved pre-race archives such as BoatraceCSV when official bulk coverage is unavailable/inconvenient and pre-race semantics are documented
3. **艇国データバンク** supplemental/cross-check only

艇国 operating rule:

- >=3 seconds between automated accesses;
- one IP;
- known URLs only;
- do not repeatedly fetch static assets;
- do not use current aggregate values as historical as-of values unless the historical cutoff is provable;
- official BOAT RACE source remains preferred for program/result/racer-term categories.

---

## 8. Historical acquisition current status

Latest GitHub main at this handoff:

- `647a43e60d627938e55de4239af15265819659bd`
- title: **Add long-range historical beforeinfo campaign (#496)**

Merged infrastructure now supports:

- bounded long-range historical beforeinfo campaigns;
- <=500 day requested span;
- <=220 day serialized segments;
- <=31 day runtime chunks;
- fill-missing-only;
- no result/odds/payout read;
- no Production decision change.

Issue #42 is the operational command/audit lane for historical campaigns.

### Official racelist / entry reconstruction

Current recorded progress:

- official racelist numeric backfill confirmed through at least 2025-08-11 in the earlier checkpoint;
- later batches continued after that;
- racer_name / branch / origin fill-missing-only support merged via #474;
- issue #42 shows later historical entry work around 2025-08-26 onward;
- additional B-file backfill was requested for 2025-09-09..09-22.

Always re-audit actual DB coverage before assuming a range is complete.

### Historical beforeinfo

Read-only coverage audit showed:

- 2025-07: complete_beforeinfo **97.31%**
- later months had strong exhibition/wind/wave coverage but many lacked temperature/water-temperature, so complete_beforeinfo was often 0 before backfill.

Merged #488/#495/#496 provide the repaired serialized long-range beforeinfo acquisition path.

A long campaign for:

- **2025-07-01 .. 2026-09-29**

has been requested through issue #42.

Check current workflow run / issue comments before launching duplicate work.

### Racer term data

Official BOAT RACE racer term archives have been captured/researched for:

- 2025 H2
- 2026 H1
- 2026 H2

Historical term reconstruction fields include:

- class;
- national win rate;
- national place2 rate;
- average ST.

Course 2025 H2 proxy acquisition was recorded complete in the prior checkpoint.
Course 2026 H1 acquisition was running.

### Opponent prior-only replay

Recorded:

- 2025-07 complete;
- 2025-08 complete;
- 2025-09 previously timed out while concurrent historical entry writes were active.

Retry only after checking current DB coverage and I/O state.
Do not change Opponent scoring logic merely to make the replay finish.

### recent_form

Current preferred reconstruction:

- official BOAT RACE K-derived prior-day history;
- only dates strictly earlier than target date;
- same-day target results excluded;
- future results excluded;
- no `v2_results` / odds / payout read as feature source;
- fill empty historical `recent_form` only;
- historical reconstruction label retained.

Current active replacement PR:

- **#498** `Research: reconstruct historical recent_form from prior-day official K (rebased)`

Do not use a post-outcome reconstructed same-day feature.

### July 2025 external pre-race archive

Current active PR:

- **#500** `Research: acquire July 2025 historical pre-race data`

Actual acquisition CI succeeded:

- run: `36670259441`
- Race Cards: **31/31 days**, 5,072 rows
- Recent Local: **31/31 days**, 5,072 rows
- Recent National: **31/31 days**, 5,013 rows
- transport/runtime errors: 0
- July early-period Race Title/Waku10/Motor Stats: unavailable in that archive

No DB import or backtest action has occurred from #500 yet.

---

## 9. Current important open PRs

Re-fetch state before acting.

Highest-current work:

- **#500** — July 2025 historical pre-race acquisition; Draft; raw artifact acquisition succeeded; no DB import yet.
- **#498** — historical recent_form prior-day official-K reconstruction; rebased Draft.
- **#497** — isolate historical beforeinfo write lane; Draft; prevents beforeinfo jobs being displaced by other historical write campaigns.
- **#482** — docs historical acquisition progress; open.
- **#459** — LINE candidate volume / near-miss diagnostic; Draft.
- **#458** — preserve V4 count across unavailable formal day; Draft.

Older evidence/provenance PRs remain open as research records:

- #405 — S03_M2 frozen Forward evidence
- #409 — immutable V4 settlement provenance
- #412 — fallback timing study
- #413 — F-count compatibility proof

Many older research PRs are intentionally not Production blockers.
Do not merge old research blindly just because they are open.

---

## 10. Candidate-volume / LINE diagnosis

Recent Production audit for 2026-09-23..09-29 showed:

- 1,029 day/night target races;
- 846 ready;
- roughly 553 session-eligible;
- frozen low-core matches: only 2;
- actual pre-LINE candidate: 1.

LINE transport itself worked on 2026-09-24 with HTTP 200.

Therefore the current Production LINE scarcity is primarily a **selector scarcity** issue, not a notifier outage.

Do not simply loosen Production conditions.

PR #459 created read-only near-miss diagnostics.

Result-blind S03_M2 volume diagnostic for 2026-09-23..09-29 showed:

- 19 unique M2-positive races;
- mean **2.71 races/day**;
- 5/7 days naturally in the 1–3 race/day context.

However:

- historical timing-safe S03_M2 economics were poor;
- original-window timing-safe ROI about **26.18%**;
- all-available strict timing-safe ROI about **19.51%**;
- current recent Forward overall is positive but second-half weak.

Therefore S03_M2 is a frozen anomaly under evaluation, not a historically proven policy.

Continue to 100 without retuning.

---

## 11. Historical backtest interpretation

Long-history V4 work from 2025-07 onward showed poor economics with the available historical contract.

Examples already recorded:

- 1R/day all-period ROI: about 97.08%;
- 1R/day later pure blocks: about 75.13%;
- 6R/day later pure blocks: about 69.75%;
- fixed point-count historical policies remained <100%.

This does not automatically prove V4/V5 can never work because historical feature coverage was uneven.

Earlier historical coverage examples:

- Motor: high (~97.8%);
- Course: low (~14.7%);
- Opponent: very low (~3.0%).

Hence the present historical acquisition work is intended to answer:

> was the poor long-history result partly caused by insufficient/mismatched pre-race inputs, or is the underlying policy genuinely weak?

Use a **matched-contract backtest** after the historical acquisition/provenance work is sufficiently complete.

Do not count reconstructed historical evidence as prospective evidence.

---

## 12. 2026-10-15 execution strategy

Primary objective is still the mid-October V5 core review.

Do not let historical acquisition derail prospective evidence collection.

Parallel tracks:

### Track A — mandatory prospective V5 core

- preserve every valid formal V4 day;
- keep 08:20 fallback healthy;
- settle formal V4 only from immutable artifacts;
- continue S03_M2 frozen to 100;
- combined checkpoint after terminal results.

### Track B — historical matched-contract improvement

- continue missing-data acquisition;
- fill only with predeadline-valid provenance;
- audit coverage;
- build matched-contract historical replay;
- compare with old incomplete-contract backtests.

### Track C — V5.1 future data

- prospective F-count companion collection;
- historical F-count only under approved predeadline semantics;
- recent_form historical prior-only reconstruction;
- later optional exhibition/weather/water/other independent features after scope review.

Do not automatically add every acquired field into V5 core by 10/15.

---

## 13. Approval / safety boundaries

### Safe / already normal work

- read-only audits;
- historical coverage audits;
- prospective Forward evaluation;
- Draft PR creation/update;
- CI;
- docs/handoff;
- pure/offline helpers;
- result-blind diagnostics;
- existing approved historical missing-data campaigns under their merged provenance/safety contracts.

### Historical write work

Historical reconstruction/backfill was explicitly approved in this project, but must remain bounded by the merged workflow contracts:

- predeadline-valid source only;
- provenance retained;
- fill-missing-only where specified;
- no target outcome leakage;
- no silent overwrite of model-critical canonical values outside the approved workflow;
- no model/selector/stake/LINE/purchase change.

A new table target, destructive overwrite, schema change, or broader Production behavior still requires separate approval.

### Explicit approval still required

- Production model/coefficient/threshold/candidate changes;
- Production stake changes;
- new LINE real-send behavior;
- purchase activation;
- destructive Production DB writes / schema / VACUUM;
- new Railway Variables/service/volume/migration changes outside an already-approved bounded campaign;
- paid/external actions.

### Never

- reconstruct an unavailable formal prospective day after outcome knowledge;
- use target-race outcomes to build historical features;
- lower evidence gates just to meet 10/15;
- loosen selectors merely to create notification volume/profit;
- expose/list Railway plaintext variables;
- call Railway variable-list functionality;
- activate automatic purchase without explicit approval.

---

## 14. Immediate next-session checklist

1. Read:
   - `docs/PROJECT_HANDOFF.md`
   - `docs/CURRENT_STATE.md`
   - `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
2. Re-fetch:
   - current GitHub main;
   - open PRs;
   - CI;
   - Railway fallback service config/deployment;
   - current evidence/DB counts.
3. Confirm fallback remains:
   - 08:20 JST;
   - code checkpoint aligned;
   - latest deploy SUCCESS;
   - no staged config.
4. Preserve 2026-09-29 as unavailable.
5. Check whether current-day formal V4 artifact exists and whether results are terminal before settling.
6. Continue S03_M2 frozen toward 100.
7. Continue historical acquisition without duplicate campaigns:
   - inspect issue #42 comments/runs first;
   - inspect #497/#498/#500.
8. Re-audit historical coverage before launching retries.
9. Build matched-contract historical backtest only after enough inputs are restored.
10. Keep monthly +50,000 JPY as a scaling objective, not a tuning target.
11. Keep Production V4 model/selector/stake unchanged unless separately approved.
12. Keep `purchase_action=false`.

---

## 15. Current snapshot at this handoff

- GitHub main: `647a43e60d627938e55de4239af15265819659bd`
- latest main work: #496 long-range historical beforeinfo campaign
- Railway fallback Cron: **08:20 JST**
- fallback latest deploy: `839be48f-af8f-4a53-8ba4-5b8abdc13f8a` — **SUCCESS**
- Railway staged config: none
- settled V4 through 9/28: **8/20**, ROI **147.7273%**, +4,200 JPY
- settled S03_M2 through 9/28: **63/100**, ROI **160.6349%**, +3,820 JPY
- 9/29 formal: **UNAVAILABLE**
- prospective F-count capture: active
- historical missing-data acquisition: active
- monthly target: **+50,000 JPY**
- desired practical notification context: roughly **1–3 quality races/day**
- Production model/selector/stake: unchanged
- `purchase_action=false`

`MAIN_647A43E / FALLBACK_0820_SUCCESS / V5_TARGET_20261015 / V4_8_OF_20_SETTLED_THROUGH_0928 / S03_63_OF_100_SETTLED_THROUGH_0928 / 0929_FORMAL_UNAVAILABLE / HISTORICAL_ACQUISITION_ACTIVE / FCOUNT_PROSPECTIVE_ACTIVE / MONTHLY_PLUS_50000_TARGET / NO_RETUNE / PURCHASE_FALSE`
