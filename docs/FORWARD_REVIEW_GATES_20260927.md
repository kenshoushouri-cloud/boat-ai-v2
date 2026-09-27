# Forward review-gate status contract — 2026-09-27

Pure status helper only. It mirrors already-frozen review contracts and creates no new economic rule.

## V4 formal TOP2

Frozen review gates:
- 10 resolved FORMAL_AVAILABLE days;
- 20 resolved FORMAL_AVAILABLE days;
- 30 resolved FORMAL_AVAILABLE days.

Current pre-9/27-settlement baseline:
- resolved formal days: 6;
- next gate: 10;
- remaining: 4.

A formal artifact day counts as resolved only when its frozen races can be officially settled. Pending results do not count.

## S03_M2_POSITIVE_V1

Frozen full review:
- 100 officially evaluated observations.

Current baseline:
- evaluated: 53;
- remaining: 47.

Invalid/cancelled rows remain void and do not increase the evaluated count.

## V4 day-strength shadow

First descriptive review requires all:
- target dates >= 2026-09-28 only;
- >=10 economically resolved future formal days;
- >=3 KEEP_SHADOW days;
- >=3 SKIP_SHADOW days.

The review gate cannot change formal TOP6/TOP2.

## Nightly result timing note

Production `cron-nightly-results` remains:
- `30 14 * * *` UTC = 23:30 JST.

Recent Stage 1 starts:
- 2026-09-23: 23:34:01 JST;
- 2026-09-24: 23:30:14 JST;
- 2026-09-25: 23:30:55 JST;
- 2026-09-26: 23:30:20 JST.

Recent full nightly pipelines completed around 23:38..23:42 JST.

Operationally, a manual Forward refresh after **23:45 JST** gives reasonable separation from the observed nightly completion window. This is an observation, not a new schedule.

No workflow is scheduled by this contract.

`GATES_ONLY / V4_10_20_30 / S03_100 / DAY_STRENGTH_10_AND_3_3 / NO_AUTO_PROMOTION / PURCHASE_FALSE`
