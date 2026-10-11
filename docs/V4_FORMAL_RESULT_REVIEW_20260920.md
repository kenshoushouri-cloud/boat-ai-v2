# V4 formal result review — 2026-09-18 / 2026-09-19

Status: `RESEARCH_ONLY / POST_RESULT_EVALUATION / NO_RETUNING / PURCHASE_FALSE`

## Evidence boundary

This review scores only the two immutable formal V4 prospective artifacts that passed the pre-result deadline guard:

- 2026-09-18: artifact `10527500527`; prospective JSON SHA-256 `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
- 2026-09-19: artifact `10574052434`; prospective JSON SHA-256 `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`

The late-rejected 2026-09-15/16/17/20 dates remain unavailable and are not reconstructed, backfilled, or scored as formal prospective evidence.

Final outcomes were collected only after the immutable artifacts existed. Exact result pages were cross-checked from public race-result pages; official BOAT RACE indexed/result pages were used where retrievable. Outcome acquisition is separate from the candidate-generation path and cannot change the frozen candidates.

## Outcome source ledger

### 2026-09-18

| race_id | Venue/R | Final trifecta | Payout | Public result page |
| --- | --- | ---: | ---: | --- |
| 20260918_22_07 | Fukuoka 7R | 1-3-4 | ¥490 | https://race.kyotei.club/info/info-20260918-22-7.html |
| 20260918_17_07 | Miyajima 7R | 1-5-2 | ¥610 | https://race.kyotei.club/info/info-20260918-17-7.html |
| 20260918_14_09 | Naruto 9R | 5-4-1 | ¥14,500 | https://race.kyotei.club/info/info-20260918-14-9.html |
| 20260918_11_07 | Biwako 7R | 1-2-4 | ¥1,200 | https://race.kyotei.club/info/info-20260918-11-7.html |
| 20260918_24_09 | Omura 9R | 2-6-5 | ¥10,600 | https://race.kyotei.club/info/info-20260918-24-9.html |
| 20260918_13_01 | Amagasaki 1R | 5-1-3 | ¥11,300 | https://race.kyotei.club/info/info-20260918-13-1.html |

### 2026-09-19

| race_id | Venue/R | Final trifecta | Payout | Public result page |
| --- | --- | ---: | ---: | --- |
| 20260919_02_08 | Toda 8R | 2-4-6 | ¥580 | https://race.kyotei.club/info/info-20260919-02-8.html |
| 20260919_24_07 | Omura 7R | 1-5-6 | ¥2,360 | https://race.kyotei.club/info/info-20260919-24-7.html |
| 20260919_17_10 | Miyajima 10R | 1-2-3 | ¥1,140 | https://race.kyotei.club/info/info-20260919-17-10.html |
| 20260919_02_07 | Toda 7R | 1-4-3 | ¥1,640 | https://race.kyotei.club/info/info-20260919-02-7.html |
| 20260919_04_03 | Heiwajima 3R | 1-3-2 | ¥880 | https://race.kyotei.club/info/info-20260919-04-3.html |
| 20260919_04_06 | Heiwajima 6R | 4-2-1 | ¥6,650 | https://race.kyotei.club/info/info-20260919-04-6.html |

## Reproducible evidence files

- `research/evidence/v4_formal_outcomes_20260918.json`
  - SHA-256: `839850a1e1499f523005b1ce7e0bfb40c1ec898c74ec75245bf49daea3f228fe`
- `research/evidence/v4_formal_eval_20260918.json`
  - SHA-256: `d39a127741ec52736ee51a34c8fa5395f1c1bf37574f8a1f3c7670ac6d59b636`
- `research/evidence/v4_formal_outcomes_20260919.json`
  - SHA-256: `5f0a7deebb5ab86ae5b08e00d355a26340701314f5d6f4f8fb1db07c5adaaf3b`
- `research/evidence/v4_formal_eval_20260919.json`
  - SHA-256: `c2d3696d40db398878182f0e6f5b9c46227f27d827279d2b2767e329e99bc069`

## 2026-09-21 strict artifact replay check

Both retained formal Actions artifacts were re-downloaded read-only and verified against their recorded immutable JSON SHA-256 values before replay:

- 2026-09-18 artifact `10527500527`: JSON SHA `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
- 2026-09-19 artifact `10574052434`: JSON SHA `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`

The stricter evaluator contract was applied with:
- exact six formal core races;
- exact two core tickets per race;
- exact outcome-set matching;
- missing/extra/non-final outcomes rejected;
- legacy excluded;
- `purchase_action=false`;
- artifact SHA verified before evaluation.

The replay exactly reproduced the committed metrics:
- 2026-09-18: `-100 JPY / ROI 91.667%`
- 2026-09-19: `+1,020 JPY / ROI 185.000%`
- combined: `+920 JPY / ROI 138.333%`

Evidence: `research/evidence/v4_formal_repro_check_20260921.json`.

This strengthens reproducibility only. It does not enlarge the formal corpus, change any threshold/model coefficient, or make the cancelled 2026-09-21 formal day evaluable.

## Daily formal V4 results

| Date | Core races | Tickets | Exact-hit races | Head hit | 1st+2nd prefix hit | Third-only miss | Investment | Return | Profit | ROI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-09-18 | 6 | 12 | 2 | 4 | 2 | 0 | ¥1,200 | ¥1,100 | -¥100 | 91.667% |
| 2026-09-19 | 6 | 12 | 2 | 3 | 3 | 1 | ¥1,200 | ¥2,220 | +¥1,020 | 185.000% |
| **Combined** | **12** | **24** | **4** | **7** | **5** | **1** | **¥2,400** | **¥3,320** | **+¥920** | **138.333%** |

Combined descriptive rates:

- exact-hit race rate: 4 / 12 = 33.33%
- exact ticket hit rate: 4 / 24 = 16.67%
- head/first-place hit rate: 7 / 12 = 58.33%
- ordered first+second prefix hit rate: 5 / 12 = 41.67%
- third-only miss rate: 1 / 12 = 8.33%

The single formal third-only miss is `20260919_24_07` (Omura 7R): frozen core included `1-5-2`, while the final trifecta was `1-5-6`. This is consistent with a third-place miss on that one race, but **does not establish a systematic third-place weakness**.

## Tier view — descriptive only

With only four races in each tier, these figures are not decision-grade:

| Tier | Races | Exact hits | Head hits | Prefix hits | Third-only miss |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 4 | 3 | 4 | 4 | 1 |
| B | 4 | 1 | 2 | 1 | 0 |
| C | 4 | 0 | 1 | 0 | 0 |

Tier A appearing stronger and Tier C having no exact hits are observations only. `n=4` per tier is far too small for coefficient, threshold, tier, ticket-count, or feature changes.

## Decision

`FORMAL_V4_CORPUS=2_DAYS_12_RACES_24_TICKETS / PROFIT_YEN=+920 / ROI=138.333% / EXACT_RACES=4_OF_12 / THIRD_ONLY_MISS=1_OF_12 / DESCRIPTIVE_ONLY / NO_RETUNING / NO_PROMOTION / PURCHASE_FALSE`

No Production model/coefficient/threshold/candidate logic, Railway configuration, DB state, LINE behavior, Forward persistence, or purchase behavior is changed by this review.


## 2026-09-22 fallback arbitration and post-result blocker

Natural fallback evidence for 2026-09-22 is now available.

Capture channels:

- Railway fallback dispatched the guarded GitHub workflow at 08:26 JST because no valid primary artifact was observable at the 08:25 checkpoint.
- fallback run `35667553345` completed at 08:26 JST with formal `6R / 12T`, artifact `10670080150`, JSON SHA `3e59a58c3704baeb991a102c58a4a92ff56670e1b1e7039cd5df42c6e68dd7d9`, canonical core SHA `1514b991505565763f412bdc3515eb64613c4de61d49cd51748fb01af61373d9`, `purchase_action=false`.
- the delayed scheduled primary later appeared at 10:35 JST as run `35676316305`; it was also predeadline-valid and produced the same canonical core SHA, while auxiliary legacy rows differed.
- under the preregistered arbiter, the unique earliest valid capture is the formal artifact; the later scheduled capture is diagnostic only. The day is therefore not double-counted.

Post-result evaluation is nevertheless blocked:

- the frozen formal core contains `20260922_09_05` (津 5R);
- the current BOAT RACE official 2026-09-22 state marks 津 as cancelled;
- no exact same-date finalized trifecta result/payout exists for that frozen core race.

Therefore 2026-09-22 is classified:

`FORMAL_AVAILABLE / POST_RESULT_UNEVALUABLE_CORE_RACE_CANCELLED / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

Important timing limitation: the current official cancellation state is post-result evidence. This review does not claim that the exact pre-freeze cancellation time is cryptographically proven, because no immutable pre-freeze raw official payload for this event is recorded here.

Machine-readable evidence:

`research/evidence/v4_formal_eval_blocker_20260922.json`

The formally evaluated corpus therefore remains Sep18 + Sep19 only:
`2 days / 12 races / 24 tickets / profit +920 JPY / ROI 138.333%`.
