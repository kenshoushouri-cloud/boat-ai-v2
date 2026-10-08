# Race Incident Handling Contract

Status: initial fail-closed contract for V4/V5 operations and research.

## Purpose

Handle withdrawals, start incidents, in-race incidents, post-race penalties, and race cancellation without:

- fabricating missing data;
- deleting raw official data;
- mixing abnormal races into the current six-boat V4/V5 core by accident;
- counting a void as a loss;
- using information that was not available before the prediction/bet deadline.

Raw official data is always retained. Eligibility is controlled separately.

## Evidence rule

Incident timing must be decided from evidence that was actually available at the relevant time.

A result-side code alone does **not** prove that a withdrawal was known before prediction.

Use, in priority order:

1. timestamped pre-race official evidence captured before the deadline;
2. timestamped odds/beforeinfo evidence captured before the deadline;
3. result/K-file evidence after the race.

Historical after-the-fact pages may prove that an abnormality existed, but must not be used to pretend that the abnormality was known before a historical prediction cutoff.

## Participant result codes already observed

Official K parsing already preserves accident/status codes including:

- `S0`: disqualification, non-racer-responsibility;
- `S1`: disqualification, racer-responsibility;
- `S2`: disqualification/obstruction, racer-responsibility;
- `L0`: late start, non-racer-responsibility;
- `L1`: late start, racer-responsibility;
- `K0`: withdrawal, non-racer-responsibility;
- `K1`: withdrawal, racer-responsibility;
- `F` and textual abnormal statuses such as capsize/fall/sink/obstruction/disqualification.

These codes are preserved as data, not collapsed into one generic "bad result".

## Common handling

| Incident state | Prediction / BUY | Primary V4/V5 training | Backtest / economics | Raw data |
| --- | --- | --- | --- | --- |
| Normal six-boat race | eligible | eligible | official settlement | retain |
| Withdrawal known before prediction | exclude race | exclude from current six-boat core | no hypothetical six-boat bet | retain |
| Withdrawal learned after prediction but before deadline | invalidate existing prediction; no BUY unless a separately validated reduced-field model re-predicts | exclude from current six-boat core | only real already-placed exposure is settled | retain |
| Start incident (F/L etc.) only known at/after start | original timing-clean prediction remains evidence | exclude from primary ability/core fitting initially; keep for separate incident research | settle actual recorded bet by official rules | retain |
| In-race accident/disqualification | original timing-clean prediction remains evidence | exclude from primary ability/core fitting initially; keep for separate incident research | settle actual recorded bet by official rules | retain |
| Post-race penalty/result correction | original pre-race prediction remains evidence | exclude from primary ability/core fitting initially until separately validated | use final official settlement | retain |
| Whole-race cancellation / VOID | no new BUY; existing prediction becomes void evidence | exclude | zero-investment/VOID under existing common economics contract | retain |
| Timing or incident class unknown | fail closed | exclude | do not reconstruct a hypothetical result | retain |

"Exclude" means eligibility exclusion only. It never means deleting source rows.

## Reduced-field races

The current V4/V5 core has been validated as a six-boat model.

Therefore 5-boat and 4-boat races are **not automatically fed into the existing model**.

A future reduced-field model may be evaluated separately:

- 5 active boats => complete trifecta market has 60 permutations;
- 4 active boats => complete trifecta market has 24 permutations;
- 6 active boats => 120 permutations.

Adoption requires separate timing-clean backtesting and OOS/Forward validation. Until then, pre-deadline withdrawal is fail-closed for prediction/BUY.

## Odds completeness

Odds completeness must use the active-lane set, not a hard-coded 120-ticket requirement.

A snapshot is complete only when:

- every retained odds value is valid;
- the active lane set is exactly 4, 5, or 6 boats;
- the ticket set equals every 3-permutation of those active lanes;
- the count is therefore exactly 24, 60, or 120.

Never invent odds for a withdrawn lane and never fill a missing ticket from neighboring values.

If the parser cannot prove the exact active-lane ticket set, classify the snapshot as incomplete/unavailable.

## Historical safety

For historical research, if the incident existed but its timing relative to the prediction cutoff cannot be proven:

- do not reconstruct what the model "would have known";
- exclude the race from primary model fitting/comparison;
- preserve it in abnormal-race coverage counts;
- use actual economics only when a timing-clean recorded purchase exists.

This prevents result leakage.

## Current concrete case: 2026-10-06 venue 02 race 5

Observed official/result facts:

- lane 5 has K status `K0`;
- lane 5 has no start course or start timing;
- the official closing trifecta page marks lane-5 combinations as withdrawal;
- the official page contains a reduced active-field market;
- both current legacy and safe odds parsers currently fail to parse that reduced table;
- candidate-v4 therefore contains only two odds tickets and must not be treated as a complete 120-ticket race.

For historical V4/V5 core use, the exact time at which the withdrawal became known relative to the original prediction cutoff has not been proven by a timing-clean snapshot. Therefore this race is excluded from primary six-boat model fitting/comparison and retained as abnormal evidence.

## Implementation order

1. add a non-destructive incident classifier/eligibility guard;
2. make realtime pre-deadline withdrawal fail closed for current V4 prediction/BUY;
3. make research/backtest eligibility use the same contract;
4. repair reduced-field official odds parsing to prove exact 60/24 sets;
5. only then research a separate reduced-field prediction model.

No change to Production prediction, LINE, purchase, stake, Railway plan, or volume is authorized by this document alone.
