# Candidate Discovery V4 trio Forward preregistration — 2026-09-14

Status: **RESEARCH ONLY / PRE-RESULT PREREGISTRATION / NO PRODUCTION CHANGE**

## Purpose

Preregister a separate **trio (3連複)** Forward research track before the first valid scheduled V4 prospective freeze on 2026-09-15 JST.

This track does **not** change the existing trifecta V4 candidate feed or `MKT_LATE07_TOP2_SUPPORT_V1`. Trifecta remains the primary V4 track. Trio is an independent secondary research track because the prior timing-safe proxy was positive but too small for promotion.

## Historical motivation only

Historical proxy window 2026-08-14..2026-09-12:

- trifecta late-window market TOP2 support: n=34, ROI 107.941%, profit +270 JPY;
- trio late-window market TOP2 support: n=47, ROI 109.149%, profit +430 JPY;
- exacta late-window market TOP2 support: n=43, ROI 53.488%, profit -2,000 JPY.

These are development/proxy results, not exact V4 Forward evidence. They justify prospective observation only.

## Frozen trio hypothesis

Name: `MKT_LATE07_TOP2_SUPPORT_TRIO_V1`

Prospective start: **2026-09-15 JST**.

A row can count only when its source is an immutable, timestamp-proven pre-result V4 artifact with:

- source contract `candidate_discovery_v4_main_feed_v1`;
- `prospective_evidence_eligible=true`;
- `counts_as_prospective=true`;
- race date >= 2026-09-15;
- `purchase_action=false` at the source boundary.

The missed 2026-09-14 V4 day remains unavailable and must not be reconstructed.

## Structural trio definition

Use only the existing V4 **`core_order=1` trifecta ticket** from each of the six core races.

Convert the ordered trifecta ticket to exactly one unordered trio combination by sorting the three distinct lanes numerically.

Examples:

- `2-3-6` -> trio `2-3-6`
- `2-6-3` -> trio `2-3-6`
- `5-1-3` -> trio `1-3-5`

No `core_order=2` extension is allowed in this version. No additional trio ticket is created from other V4 permutations.

Therefore the maximum structural trio universe is **6 trio candidates/day**, one per V4 core race.

## Market trio definition

Use the same timing-safe complete trifecta market snapshot family already used by the late-market study:

- 0.0..7.0 minutes before race deadline;
- complete 120 distinct trifecta tickets;
- all odds finite and > 1.0;
- coherent snapshot spread <= 60 seconds;
- snapshot and update timestamps pre-deadline in the live annotator boundary.

For the pure market transform:

1. score every trifecta ticket as `1 / odds`;
2. de-vig across all 120 tickets so the probabilities sum to 1;
3. map each ordered trifecta ticket to its unordered three-lane trio combination;
4. sum all six permutations for each trio combination;
5. obtain exactly 20 trio probabilities;
6. rank by aggregated trio probability descending, deterministic combination order as tie-break;
7. retain market trio TOP2.

`market_top2_support_trio = structural_trio is in market trio TOP2`.

No TOP3/TOP4 expansion, odds band, EV threshold, venue exclusion, race-number exclusion, rank carveout, or lead-time sub-window is allowed in this version.

## Result evaluation

Trio settlement must use the **official trio result and official trio payout**, never a trifecta payout converted after outcome.

Primary normalization: flat **100 JPY per supported evaluated trio candidate**.

Report independently from trifecta:

- prospective days;
- late-snapshot available cases;
- supported cases and supported days;
- zero-supported days;
- settled supported cases;
- hits / hit rate;
- investment / return / profit / ROI;
- longest losing supported-case streak;
- maximum drawdown;
- positive-day rate;
- maximum single-hit share of returns;
- race-rank and venue diagnostics only where separately preregistered.

## Milestones

Use independent trio supported-evaluated milestones at **30 / 50 / 100 cases**.

- 30: integrity / early signal only;
- 50: stability review;
- 100: first serious review of whether trio deserves a separate future BUY experiment.

No milestone automatically authorizes Production promotion.

## Relationship to trifecta

Keep the two tracks separate:

- trifecta: existing primary `MKT_LATE07_TOP2_SUPPORT_V1`;
- trio: secondary `MKT_LATE07_TOP2_SUPPORT_TRIO_V1`.

Do not add their profits, tickets, or supported counts into one ROI number. A race may be supported in one track, both tracks, or neither.

No cross-track rule such as `buy if either wins historically` may be created from observed outcomes without a new prospective preregistration.

## Safety boundary

This preregistration authorizes research reporting only.

No change to:

- Production V24/FINAL;
- V4 candidate ranking or 6-race/12-trifecta-ticket contract;
- Course / Opponent Pressure / Motor2 coefficients;
- existing trifecta Stage2 contract;
- Railway Variables / Cron / services / volumes;
- Production DB schema or rows;
- LINE sends;
- Forward persistence;
- real BUY/WATCH/SKIP;
- real stake;
- automated purchase.

`purchase_action=false` and `promotion_allowed=false` remain mandatory.
