# Candidate Discovery Forward artifact identity correction — 2026-09-13 JST

Status: **research-only / correction frozen before 2026-09-13 outcome evaluation**

## Correction

The immutable pre-result artifact from GitHub Actions run `34726186753` / artifact `10308110102` is the **V1/V2 main-feed baseline artifact**, not an integrated V4 artifact.

This is confirmed by both sources of truth in the research branch:

- the freeze commit `53506eb88e37c51b1ce9d102c44bcbe2c0fb59f3` generated candidates with `.github/scripts/candidate_discovery_main_feed_pg.py`, whose core uses the V2 BASE distribution plus Motor2 support tagging;
- `docs/CANDIDATE_DISCOVERY_V4_CONTRACT_20260913.md` explicitly states that the official first 2026-09-13 freeze remains the V1/V2 main-feed artifact and that V4 was not retroactively substituted into it.

Therefore any later handoff/comment wording that calls the 2026-09-13 core `V4 core` is a labeling error. It must not change the immutable artifact itself.

## What remains valid

The 2026-09-13 artifact remains a valid immutable **baseline Forward observation**:

- run `34726186753`;
- artifact `10308110102`;
- ZIP SHA-256 `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`;
- JSON SHA-256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`;
- 180 / 180 scheduled/evaluable;
- core 6 races / 12 tickets;
- legacy carryover 2 races / 2 tickets;
- total 8 races / 14 tickets.

It must still be evaluated exactly as frozen. Do not regenerate, replace, add, or remove candidates after outcomes.

## What does not count

- 2026-09-13 must **not** be counted as exact V4 Forward evidence.
- The 2026-09-13 late-market annotation is wiring-only and remains excluded from `MKT_LATE07_TOP2_SUPPORT_V1` prospective milestones.
- A post-outcome V4 reconstruction for 2026-09-13 may be used only for plumbing/comparison diagnostics, never as prospective performance evidence.

## True V4 Forward boundary

Exact V4 prospective evidence requires an immutable pre-result artifact generated from the frozen V4 chain:

1. BASE structural raw strength;
2. Course coefficient `0.50`, missing lane neutral;
3. Opponent Pressure `adj_win - base_win`, coefficient `1.0`, first-place only;
4. Motor2 beta `0.06`, position weights `1.0 / 0.6 / 0.3`;
5. four equal-weight structural metrics;
6. TOP6 races × TOP2 trifecta tickets;
7. no EV or absolute-odds gate.

The research branch now contains `.github/scripts/candidate_discovery_v4_main_feed_pg.py` as the read-only integrated generator. It reads no outcomes/payouts and performs no DB mutation, LINE send, purchase action, or Production change.

A calendar date counts toward exact V4 Forward evidence only if this V4 artifact was actually frozen before results. If a day is missed, record it as unavailable; do not reconstruct it after the outcome.

`MKT_LATE07_TOP2_SUPPORT_V1` remains predeclared from 2026-09-14 JST, but its 30/50/100 exact-V4 milestones count only qualifying immutable V4 artifacts created pre-result on or after that date.

## Safety

- Production selector/model/threshold: unchanged
- DB write/schema: 0
- LINE: 0
- BUY: 0
- Railway Production config/Cron/service: unchanged
- `purchase_action=false`
- promotion blocked pending Forward evidence and explicit approval
