# V4 post-result evaluation contract — 2026-09-20

Status: `RESEARCH_ONLY / POST_RESULT_ONLY / OFFLINE / NO_PRODUCTION_IO`

## Purpose

Formal Candidate Discovery V4 evidence is frozen before results. After races are final, the frozen artifact still needs a reproducible evaluation step. This contract separates that post-result scoring from the pre-result capture path.

The evaluator consumes only:

1. one immutable `candidate_discovery_v4_main_feed_v1` JSON artifact that already passed the prospective pre-deadline guard; and
2. a caller-supplied finalized outcomes JSON.

It does not query Production, Railway, BOAT RACE websites, LINE, or purchase systems.

## Formal metrics

Only the six structural `DISCOVERY_CORE` races and their exact two tickets each are included in formal V4 metrics.

Legacy S01-S05 carryover remains visible in the original artifact but is excluded from formal core result metrics.

For each core race the evaluator records:

- exact trifecta hit;
- head-lane/first-place hit;
- first+second ordered-prefix hit;
- `third_only_miss`: the actual first and second lanes match at least one frozen core ticket prefix, but neither frozen exact ticket matches the third lane.

The final summary records:

- six formal core races / twelve tickets;
- exact-hit race count;
- head-hit race count;
- first-second prefix-hit race count;
- third-only-miss race count;
- fixed stake investment;
- exact-hit gross return;
- profit and ROI.

A payout is counted only for an exact frozen ticket match. No partial-hit return is invented.

## Fail-closed rules

Evaluation refuses:

- non-prospective or late-rejected artifacts;
- artifacts without `all_frozen_rows_pre_deadline=true`;
- `purchase_action=true`;
- anything other than exactly six formal core races;
- anything other than core orders 1 and 2 for each core race;
- duplicate core tickets;
- malformed/duplicate/missing outcomes;
- malformed trifecta lane order or invalid payout values.

A missing final outcome blocks the full-day evaluation rather than silently shrinking the denominator.

## Leakage boundary

This evaluator is intentionally post-result. Outcome/payout data may be supplied only after the immutable prospective artifact already exists. Results never flow back into candidate generation, artifact eligibility, rank ordering, or same-day reconstruction.

Historical, BASELINE, formal V4 prospective, legacy auxiliary, and later Production evidence remain separate evidence classes.

## Current corpus

As of the 2026-09-20 review:

- 2026-09-18: formal prospective artifact available;
- 2026-09-19: formal prospective artifact available;
- 2026-09-15/16/17/20: unavailable and must not be scored as formal prospective days.

Therefore the current formal evaluable V4 corpus is two days, twelve core race selections, twenty-four frozen tickets.

## Safety

This module has no database/network/Railway/LINE/purchase path and no Production write surface. Any future automated outcome acquisition or Production result-table read is a separate review/approval boundary.
