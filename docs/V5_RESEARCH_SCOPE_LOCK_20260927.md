# V5 research scope lock — 2026-09-27

Target:
- **2026-10-15 V5 core freeze review**

Purpose:
protect the schedule from feature creep while preserving evidence quality.

## Production remains V4

Nothing in this scope lock changes Production.

The current V4 probability/selector contract is the baseline from which a V5 research candidate may later be frozen.

## Locked V5 core baseline

Probability inputs already in the baseline:
- racer class;
- national win rate;
- national place2 rate;
- local place2 rate;
- average ST;
- venue/course bias;
- Racer Course;
- Opponent Pressure;
- Motor2.

Fixed current contract:
- Course 0.50;
- Opponent Pressure 1.0, first-place-only;
- Motor2 beta 0.06;
- temperature 2.20;
- selector: head_p1 / head_margin / top3_mass / concentration;
- TOP6 races;
- TOP2 tickets;
- no odds read for formal selection;
- no EV filter in the formal selector.

## Mandatory evidence before V5 core freeze review

- formal V4: >=20 resolved FORMAL_AVAILABLE days;
- S03_M2: >=100 officially evaluated observations;
- clean evidence contract.

These counts are not lowered to meet the calendar target.

## Optional layers

### Day-strength
May be admitted only if its existing frozen gate is naturally reached:
- >=10 future resolved days;
- >=3 KEEP;
- >=3 SKIP.

If not:
- keep shadow-only;
- do not delay or weaken the V5 core gate.

### F-count
Not required for the V5 core milestone.

Still:
- live activation unapproved;
- no historical backfill;
- no historical coefficient search.

## Deferred from the 2026-10-15 core

Do not add merely because time remains:
- recent_form;
- L-count;
- exhibition ST;
- exhibition time;
- weather/water;
- odds/EV selector;
- any new unpreregistered feature.

These can become post-V5/V5.1 research instead.

## Change control

Until the 2026-10-15 core review:
- no new feature enters V5 core;
- exception: an already-listed optional layer may be admitted only by satisfying its existing prospective gate;
- no threshold/gate lowering to meet the deadline;
- no post-outcome retuning.

This makes "mid-October completion" mean a controlled research-candidate freeze, not an endless feature search.

`SCOPE_LOCKED / V4_BASELINE / V4_20_S03_100 / OPTIONAL_NONBLOCKING / NO_FEATURE_CREEP / PURCHASE_FALSE`
