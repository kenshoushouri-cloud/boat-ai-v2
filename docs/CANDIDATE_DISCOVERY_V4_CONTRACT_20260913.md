# Candidate Discovery V4 frozen contract — 2026-09-13

## Purpose

V4 is the next research candidate for the broad Boat AI main feed. It is designed to improve ranking quality without returning to narrow EV or absolute-odds eligibility gates.

This document freezes the calculation order before any integrated live V4 performance result is used for tuning.

## Fixed calculation chain

For each six-lane race:

1. **BASE raw lane strength**
   - same v24-style structural race-card strength basis used by Candidate Discovery V1/V2.
   - probability temperature remains `2.20`.

2. **Racer Course neutral-missing enrichment**
   - fixed coefficient: `0.50`.
   - use only exact racer/date/course observations that satisfy the separately frozen timing-safe Course contract.
   - z-score observed usable lanes only.
   - missing/unusable Course lane: `z=0`, preserving BASE raw strength for that lane.
   - no coefficient search.

3. **Opponent Pressure enrichment — first place only**
   - fixed coefficient: `1.0`.
   - signal is the frozen lane-level difference `adj_win - base_win` from Opponent Pressure v2.
   - apply the delta only to the six normalized **first-place** probabilities, clip positive, then renormalize.
   - preserve the Course-adjusted BASE conditional probabilities for second and third place.
   - fixed trifecta mapping:
     `P(a,b,c) = P_opp_first(a) * P_base(b|a) * P_base(c|a,b)`.
   - this head-only mapping is frozen because existing Opponent Pressure research found that applying the same adjusted lane weights to every Plackett–Luce stage can hurt realized ticket ranking, while Opponent Pressure is supported primarily as an incremental first-place signal.
   - only timing-clean Opponent Pressure evidence is eligible: v2 identity, train end before race date, complete six-lane matched-opponent evidence, and the separately frozen morning/deadline timing contract.
   - no coefficient search.

4. **Ordered trifecta construction**
   - create all 120 exact-order trifecta probabilities using Opponent-adjusted P(first) and unchanged Course-adjusted BASE second/third conditionals.

5. **Motor2 support factor**
   - fixed beta: `0.06`.
   - ticket position weights: first `1.0`, second `0.6`, third `0.3`.
   - apply the exponential Motor2 factor to the 120-ticket distribution and renormalize.
   - if complete six-lane Motor2 evidence is unavailable, the pure contract preserves the pre-Motor distribution.

6. **Candidate feed**
   - no `raw_ev` eligibility gate.
   - no minimum/maximum absolute odds band for candidate inclusion.
   - provisional main-feed target remains 6 races/day and 2 tickets/race, with legacy S01-S05 carryover kept separately while the new system accumulates Forward evidence.

## Candidate versus purchase separation

V4 produces prediction candidates. It does not authorize purchase.

- `purchase_action=false`
- odds can remain display/context metadata outside the pure ranking contract.
- any later purchase recommendation layer must be evaluated separately and must not retroactively alter the frozen candidate feed.

## Timing / leakage rules

A Forward candidate set must be frozen before race results are known. Later-arriving signals may create a separately timestamped refinement observation, but must not rewrite an earlier frozen observation.

The official first Candidate Discovery Forward freeze remains the V1/V2 main-feed artifact from 2026-09-13 run `34726186753`; V4 was not retroactively substituted into that freeze.

## Current implementation boundary

Pure implementation:
- `research/candidate_discovery_v4_contract.py`
- `tests/test_candidate_discovery_v4_contract.py`
- `.github/workflows/candidate-discovery-v4-contract.yml`

The pure contract contains no DB, network, Railway, LINE, or purchase integration. Tests explicitly lock the head-only Opponent behavior: changing P(first) must not change the relative second/third conditional ratios for a fixed first-place lane.

A direct integrated live-DB V4 evaluator was not added after the platform safety layer blocked that path; no bypass is permitted.

## Promotion rule

No Production promotion is implied by a successful pure contract. Before any Production candidate-system change, prospective evidence must compare at minimum:

- candidate races/day and tickets/day;
- hit rate by A/B/C tier;
- exact-ticket hit rate;
- month/day stability;
- losing streaks;
- legacy overlap/containment;
- realized flat-stake ROI as a diagnostic, without using ROI to rewrite already-frozen candidate rules;
- timing integrity and missing-data behavior.

`RESEARCH_ONLY / FIXED_COURSE_0.50 / FIXED_OPPONENT_HEAD_ONLY_1.0 / FIXED_MOTOR2_0.06 / NO_EV_GATE / NO_ABSOLUTE_ODDS_GATE / PURCHASE_ACTION_FALSE / NO_PRODUCTION_CHANGE`
