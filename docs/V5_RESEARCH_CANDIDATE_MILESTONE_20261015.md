# V5 research candidate milestone — target 2026-10-15

Status: `RESEARCH ONLY / NO PRODUCTION ACTIVATION`

The project has outgrown a simple "V4 coefficient tweak" interpretation.

Production remains V4. This document defines a **V5 research-candidate milestone** only: the point at which enough independent prospective evidence exists to freeze a next-generation candidate specification for further Forward evaluation.

## Target

Research candidate freeze review target:
- **2026-10-15**

This is a planning target, not a profitability guarantee.

"Complete by mid-October" means:
- evidence streams reach their preregistered review checkpoints;
- the V5 research architecture can be frozen without using post-hoc outcome tuning;
- a candidate can enter a new Forward phase.

It does **not** mean:
- long-run ROI >100% is proven;
- Production can be switched automatically;
- purchase can be enabled.

## Required evidence before V5 core freeze review

The core freeze review has two mandatory evidence gates. Optional new layers keep their own unchanged admission gates and cannot delay the core milestone.

### 1. Formal V4 baseline
- >=20 resolved FORMAL_AVAILABLE days.
- Current pre-9/27-settlement baseline: 6.
- 10-day checkpoint remains an intermediate review; 20 days is the V5 freeze-review minimum.

Reason:
the current positive V4 TOP2 checkpoint should survive materially more natural Forward exposure before becoming the baseline of a new generation.

### 2. S03_M2 independent prospective track
- >=100 officially evaluated observations.
- Current baseline: 53.

Reason:
S03_M2 currently has strong overall economics but a weaker second half. It must reach its already-frozen 100-observation review before it can inform V5 architecture.

### 3. Evidence contract remains clean
Required:
- immutable formal artifacts selected before result access;
- invalid/cancelled results remain void;
- no reconstructed unavailable days;
- no post-outcome retuning;
- no hidden odds/EV gate in formal selection.

## Optional-layer admission

### Future-only day-strength
Its frozen gate is unchanged:
- >=10 economically resolved target days from 2026-09-28 onward;
- >=3 KEEP_SHADOW days;
- >=3 SKIP_SHADOW days.

If this is not ready by 2026-10-15:
- do not lower the gate;
- do not invent SKIP/KEEP volume;
- freeze the V5 core without day-strength;
- keep day-strength shadow-only until its own gate is naturally reached.

### F-count
Not required for the 2026-10-15 core milestone.
Its live capture remains separately approval-gated and future-only.

## Proposed V5 research architecture

Do **not** combine all experimental features.

Freeze candidate architecture from only evidence that survives prospective review:

### Layer A — probability core
Start from current V4 probability core:
- racer class;
- national win rate;
- national place2 rate;
- local place2 rate;
- average ST;
- venue/course bias;
- Racer Course coefficient 0.50;
- Opponent Pressure 1.0 first-place-only;
- Motor2 beta 0.06;
- probability temperature 2.20.

V5 does not automatically change these coefficients.

### Layer B — race/ticket structural selection
Start from current:
- head_p1;
- head_margin;
- top3_mass;
- concentration;
- TOP6 races;
- formal TOP2 tickets.

Any replacement must beat the frozen baseline prospectively; historical optimization alone is insufficient.

### Layer C — independent economic/selection evidence
Potential inputs to a V5 candidate only after their frozen reviews:
- S03_M2;
- future-only day-strength shadow.

These should initially remain separate shadow signals. Do not blend them merely because both look profitable at a small checkpoint.

### Layer D — optional future features
Not required for the 2026-10-15 milestone:
- F-count;
- exhibition;
- weather/water;
- other late pre-race information.

F-count remains especially gated:
- no historical backfill;
- no historical coefficient search;
- live prospective capture requires separate explicit approval.

A mid-October V5 candidate should **not** be delayed merely to force unproven extra inputs into it.

## Milestone interpretation

When the mandatory core gates are reached:
`V5_CORE_FREEZE_REVIEW_READY`

Optional layers have separate admission readiness and do not inherit core readiness.

That status only authorizes a research review.

It does not authorize:
- Production merge;
- Railway changes;
- model/selector/stake changes;
- LINE send;
- purchase.

## Current baseline — 2026-09-27 before nightly settlement

- V4 resolved formal days: 6 / 20
- S03_M2 evaluated: 53 / 100
- mandatory V4: 6 / 20
- mandatory S03_M2: 53 / 100
- evidence contract: clean
- optional day-strength: 0 / 10 future resolved, KEEP 0 / 3, SKIP 0 / 3
- optional F-count: not active

## Schedule feasibility

If natural evidence continues at roughly the recent rate:
- V4 10-day review should occur well before mid-October;
- V4 20-day review is compatible with roughly early-to-mid October;
- S03 100 observations is compatible with roughly early-to-mid October at its recent observation pace;
- day-strength 10 future resolved days is compatible with early October if formal days remain available, but its KEEP/SKIP balance is not schedule-controllable.

Therefore 2026-10-15 is a **reasonable V5 core research-candidate freeze target**. Optional layers cannot be forced merely to meet the date. The main schedule risks are missing formal days, result/data outages, or V4/S03 evidence failing its frozen economics/robustness review.

`TARGET_20261015 / EVIDENCE_FIRST / NO_POSTHOC_RETUNE / V5_RESEARCH_NOT_PRODUCTION / PURCHASE_FALSE`
