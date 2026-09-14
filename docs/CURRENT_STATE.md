# boat-ai-v2 Current State

更新日時: 2026-09-14 14:22 JST

このファイルは短い運用スナップショットです。再開時は必ずGitHub main / open PR / Railway Productionを再取得し、ここに書かれたSHAや件数を固定値だと仮定しないでください。

## Current main / open research

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Current main: `0fadbce7b3795b455f81489acb877abdf4c6d48c`
- PR #352: merged。minimal read-only V4 prospective freeze pathをdefault branchへ追加。
- Draft PR #351: open / research-only / mergeable。Candidate Discovery V1-V4 + market corroboration + evaluator/stability safety。head `110af472860bd00ae6d98835ea51b4c8d9d11825`。
- Draft PR #357: 2026-09-13 immutable BASELINE exact eval、head `a31ed3ff8c41d4860783ffac7d467926257a5d8b`。
- Draft PR #355: future V4 prospective freezeを08:16 JSTにscheduleする案、head `02869b57f9fad493ccce26a359be538623e5fe87`。main未merge。

## Candidate Discovery current boundary

V4 Stage 1 fixed research contract:
- 6 races/day × TOP2 exact-order trifecta
- Course 0.50, missing lane neutral
- Opponent Pressure 1.0, first-place only
- Motor2 beta 0.06, weights 1.0/0.6/0.3
- 4 structural metrics equal-weight daily rank
- no Stage-1 EV gate / absolute odds gate
- legacy S01-S05 retained
- `purchase_action=false`

Frozen Stage 2 hypothesis:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- deadline 0..7m market TOP2 support
- 30/50/100 exact V4 supported-case milestones
- no post-outcome retuning

## 2026-09-13 immutable baseline Forward — exact evaluation complete

This is **BASELINE, not V4**.
- source run `34726186753`
- source artifact `10308110102`
- 180/180 scheduled/evaluable
- baseline core 6 races / 12 tickets
- legacy 2 races / 2 tickets
- source JSON SHA256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

Draft PR #357 / CI run `34808905754`でofficial-results-only exact評価完了:
- baseline_core: 6 races / 12 tickets / 2 hits / 投資1,200円 / 払戻1,420円 / **+220円 / ROI 118.333%**
- legacy: 2 races / 2 tickets / 0 hits / **-200円 / ROI 0%**
- total: 8 races / 14 tickets / 2 hits / 投資1,400円 / 払戻1,420円 / **+20円 / ROI 101.429%**
- `v4_core=0`
- `MKT_LATE07_TOP2_SUPPORT_V1 cases=0`
- evidence artifact `10333917048`, ZIP SHA256 `c2420e48d633ada46d4bc02466b78deeb0d729ac33dc9d5907b8e6638689ad4b`
- DB write=0 / LINE=0 / `purchase_action=false` / Production change=0

Never regenerate or relabel the source artifact. This one BASELINE day is not sufficient evidence for profitability or threshold/model retuning.

## 2026-09-14 V4 prospective evidence

PR #352 merged before morning operation and guarded workflow exists on main, but a timestamp-proven V4 pre-result freeze was not captured for 2026-09-14.

Decision:
- 2026-09-14 is unavailable as formal V4 prospective Forward evidence.
- Do not reconstruct candidates after outcomes.
- Do not count the day in V4 or `MKT_LATE07_TOP2_SUPPORT_V1` milestones.
- Resume on the next date with a valid pre-result freeze before earliest deadline.

## Next V4 capture

Draft PR #355 adds a future daily `08:16 JST` schedule and explicit JST target-date resolution while preserving all existing fail-closed guards. Related CI on head `02869b57f9fad493ccce26a359be538623e5fe87` is green.

Because this changes the default-branch workflow schedule, it remains approval-gated and is **not merged**. If main remains unchanged on the next Forward date, capture must still be initiated manually before the earliest deadline.

## Evaluator / metric safety

PR #351 includes:
- official-only result guard (`result_status` and `race_status` both official)
- positive payout validation
- BASELINE/V4 segment separation by source contract
- no DB write / no LINE / no BUY / no Production promotion

## Railway production

Project `boat-v2-postgres` read-only status at update time:
- environment staged changes: none
- `postgres-recovery`: SUCCESS / 5GB volume
- `cron-nightly-results`: 23:30 JST
- `cron-racer-course-stats`: 07:15 JST
- `cron-opponent-pressure-v2-live`: 07:00 JST
- main operational services: SUCCESS

Do not DELETE/VACUUM or change Cron/Variables/config without explicit approval. Do not place other-sport datasets in the boat Production DB.

## Racer Course / Opponent Pressure

Frozen research coefficients:
- Course 0.50
- Opponent Pressure 1.0

Opponent Pressure timing-safe natural Cron validation continues. Even after sufficient clean days, Production promotion requires a separate explicit review/approval.

## Cross-project blockers

TOTO:
- Draft PR #161 contains the complete minimal Round 1654 pair fix, head `b873c49e7a07735ccc1efb59c1d2380e91609d7a`.
- same `round_no`, complete A+B, exact two product rows, effective deadline=`min(A,B)`.
- stacked Draft PR #162 head `0e718e22bfca116b5146dddb4e1209149afbb5a1` completed safe evidence replay.
- validation run `34809289024`: SUCCESS; full CI `34809288926`: SUCCESS.
- Production natural-Cron evidence: Round 1654 mini A/B each 5 matches / 5 live vote snapshots.
- official deadlines: A 2026-09-19 17:50 JST / B 18:20 JST.
- frozen selector resolves target 1654 / effective 17:50 JST.
- classification: `EVIDENCE_REPLAY_NOT_LIVE_DB_EXECUTION` because TOTO Postgres has no public TCP proxy; no Production infra was changed to force live-DB execution.
- DB/Forward write=0 / LINE=0 / `purchase_action=false` / Production config change=0.
- PR #161 Production merge still requires explicit approval.
- Railway still has accidental `diagnostic-round-1654-reader`; a single staged removal awaits dashboard 2FA.

地方競馬:
- Issue #353
- `TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`
- no bulk download / persistent training / Production DB until rights are clear.

## Immediate next work

1. Keep 9/13 exact BASELINE result frozen as BASELINE-only evidence; no retune from one day.
2. Keep 9/14 V4 Forward missed/unavailable; never backfill it.
3. Capture next-date V4 pre-result freeze with run/artifact/SHA provenance. #355 is approval-gated, so use manual dispatch if it is still unmerged.
4. Continue PR #351 fixed Forward evidence without retuning through 30/50/100 milestones.
5. TOTO PR #161 evidence replay is complete; Production merge remains approval-gated.
6. TOTO Railway: user applies only the staged accidental-service removal with 2FA, then verify original three-service state.

## Safety boundary

Do not change without explicit approval:
- Production v24/FINAL logic
- Course 0.50 / Opponent 1.0 or other coefficients/thresholds
- BUY/WATCH/SKIP
- LINE behavior
- Railway Production config/Cron/Variables
- Production DB schema/writes/deletes/VACUUM
- automatic purchase

Keep fail-closed and `purchase_action=false`.
