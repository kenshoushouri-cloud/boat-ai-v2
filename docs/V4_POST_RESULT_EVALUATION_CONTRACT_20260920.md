# V4 post-result evaluation contract — 2026-09-20

Status: `RESEARCH_ONLY / POST_RESULT_ONLY / OFFLINE / NO_PRODUCTION_IO`

## Purpose

Formal Candidate Discovery V4 evidence is frozen before results. After races are final, the frozen artifact still needs a reproducible evaluation step. This contract separates that post-result scoring from the pre-result capture path.

The evaluator consumes only:

1. one immutable `candidate_discovery_v4_main_feed_v1` JSON artifact that already passed the prospective pre-deadline guard; and
2. a caller-supplied finalized outcomes JSON.

CLI evaluation also requires the expected SHA-256 of the immutable artifact JSON. The file digest is verified before JSON parsing/evaluation so a locally altered copy cannot silently enter formal metrics.

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
- any outcome race outside the exact six-race formal core;
- any explicit non-final outcome status such as cancelled/postponed/abandoned;
- malformed trifecta lane order or invalid payout values;
- malformed or mismatched immutable-artifact SHA-256 in CLI evaluation.

A missing final outcome blocks the full-day evaluation rather than silently shrinking the denominator. Extra outcome rows are also rejected rather than silently ignored, so formal scoring consumes an exact six-race outcome set matching the frozen formal core.

### Cancellation / postponement edge case

A formal core race that is cancelled, postponed, abandoned, or otherwise has no finalized same-date trifecta result/payout is **not** converted into a loss, a zero-yen payout, or a smaller denominator. The formal day remains pre-result-artifact-valid but post-result-unevaluable under this contract.

Do not:
- synthesize an outcome or payout for the cancelled race;
- score only the remaining five races;
- move a postponed race's later-date result back onto the frozen original date;
- regenerate a replacement candidate after the cancellation becomes known.

This is a fail-closed evaluation-availability rule, not a model/threshold change.

## 2026-09-21 pre-freeze race-availability finding

A later audit of **pre-freeze observable information** found that the BOAT RACE official today's-race page was already updated at 08:25 JST showing Toda as cancelled/postponed, while the immutable V4 artifact was generated at 10:03:12 JST.

Therefore the Sep21 blocker is not merely a cancellation learned after freeze. It is also a race-universe quality gap:

- official same-day venue cancellation was observable before the formal freeze;
- current-main V4 loaded all target-date rows from `v2_races`;
- current-main V4 required complete six-lane entries and a deadline, but did not apply a pre-result cancelled/postponed availability filter;
- `v2_races` does not currently provide a compatible pre-result race-status field for this purpose;
- result/payout data was not used to identify this gap.

Machine-readable evidence:
`research/evidence/v4_pre_freeze_race_availability_gap_20260921.json`

Evidence-strength limitation: the 08:25 displayed update time was observed on the official same-day race-list page, but the exact raw 08:25 response was not preserved with a content digest. Because that official URL is mutable during the day, the pre-freeze timing observation is useful historical evidence but is not cryptographically reproducible from the URL alone. This limitation does not change the current post-result fact that Toda was cancelled/postponed; it does constrain how strongly the historical 08:25 page state can be replayed.

Any future Production-effect availability guard must preserve the exact official observation (or equivalent immutable raw representation) and a deterministic SHA-256 before parsed availability status can be treated as eligible evidence.

This finding does **not** authorize an immediate Production candidate-logic change. A future timing-safe official race/venue availability source and exclusion contract must be preregistered and separately approved before any Production behavior change.

## 2026-09-21 observed blocker

The immutable 2026-09-21 formal artifact includes core race `20260921_02_08` (Toda 8R, frozen deadline 14:16 JST). BOAT RACE official same-day pages later marked Toda as cancelled/postponed for 2026-09-21. Therefore the current six-outcome contract cannot produce a formal 2026-09-21 evaluation unless an authoritative same-date final result/payout for that exact race exists; a later postponed race must not be substituted.

Official source paths used for the cancellation classification:
- `https://www.boatrace.jp/owpc/pc/race/index?hd=20260921`
- `https://www.boatrace.jp/owpc/pc/race/pay`
- `https://www.boatrace.jp/owpc/pc/race/racelist?hd=20260921&jcd=02&rno=5`

## Artifact integrity boundary

The immutable artifact digest is part of the evaluation input, not a comment-only convention.

For CLI use:

- `--artifact-sha256` is required;
- it must be exactly 64 lowercase hexadecimal characters;
- SHA-256 is calculated from the raw artifact JSON bytes before parsing;
- a mismatch aborts evaluation;
- the digest must come from the frozen prospective artifact evidence/manifest, not from a regenerated post-result file.

For 2026-09-21, the re-verified immutable JSON SHA-256 is:

`1af00a1a7cc1742c4e93a5f816e4aaf90fb181ac45be9ee4d88ad09c4d5f6175`

The separately frozen canonical core SHA remains:

`d07ec4347ccd30eb82c8511da9118784a124cbe90459fe8d2ce5f4c2773debaf`

These checks protect evidence identity only; they do not make the cancelled 2026-09-21 formal day evaluable.

## Leakage boundary

This evaluator is intentionally post-result. Outcome/payout data may be supplied only after the immutable prospective artifact already exists. Results never flow back into candidate generation, artifact eligibility, rank ordering, or same-day reconstruction.

Historical, BASELINE, formal V4 prospective, legacy auxiliary, and later Production evidence remain separate evidence classes.

## Current corpus

As of the 2026-09-20 review:

- 2026-09-18: formal prospective artifact available;
- 2026-09-19: formal prospective artifact available;
- 2026-09-15/16/17/20: unavailable and must not be scored as formal prospective days.

Therefore the current formal evaluated V4 corpus remains two days, twelve core race selections, twenty-four frozen tickets.

2026-09-21 adds a third **formal available artifact** (six core races / twelve tickets), but it must not be added to evaluated metrics while the Toda cancellation leaves one frozen core race without a same-date finalized result/payout.

## Safety

This module has no database/network/Railway/LINE/purchase path and no Production write surface. Any future automated outcome acquisition or Production result-table read is a separate review/approval boundary.