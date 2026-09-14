# boat-ai-v2 Current State

更新日時: 2026-09-14 13:50 JST

このファイルは短い運用スナップショットです。再開時は必ずGitHub main / open PR / Railway Productionを再取得し、ここに書かれたSHAや件数を固定値だと仮定しないでください。

## Current main / open research

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Current main: `0fadbce7b3795b455f81489acb877abdf4c6d48c`
- PR #352: merged。minimal read-only V4 prospective freeze pathをdefault branchへ追加。
- Draft PR #351: open / research-only / mergeable。Candidate Discovery V1-V4 + market corroboration + evaluator/stability safety。
- PR #351 head: `110af472860bd00ae6d98835ea51b4c8d9d11825`

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

## 2026-09-13 immutable baseline Forward

This is **BASELINE, not V4**.
- run `34726186753`
- artifact `10308110102`
- 180/180 scheduled/evaluable
- baseline core 6 races / 12 tickets
- legacy 2 races / 2 tickets
- JSON SHA256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

Never regenerate or relabel it. Exact evaluation must use official result rows only and must remain in `baseline_core`; `v4_core` must stay zero for this date.

## 2026-09-14 V4 prospective evidence

PR #352 merged before morning operation, and workflow `candidate-discovery-v4-prospective-freeze.yml` exists on main.

However GitHub Actions read-only audit at 2026-09-14 13:50 JST found **zero `workflow_dispatch` runs** in this repository. Therefore a timestamp-proven V4 pre-result freeze was not captured through the guarded workflow.

Decision:
- 2026-09-14 is unavailable as formal V4 prospective Forward evidence.
- Do not reconstruct candidates after outcomes.
- Resume on the next date with a valid pre-result freeze before earliest deadline.

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
- main operational Cron services: SUCCESS

Do not DELETE/VACUUM or change Cron/Variables/config without explicit approval. Do not place other-sport datasets in the boat Production DB.

## Racer Course / Opponent Pressure

Frozen research coefficients:
- Course 0.50
- Opponent Pressure 1.0

Opponent Pressure timing-safe natural Cron validation continues. Even after sufficient clean days, Production promotion requires a separate explicit review/approval.

## Cross-project blockers

TOTO:
- Draft PR #161 now contains the complete minimal Round 1654 pair fix for weekly selector + current-model LINE loader.
- head `b873c49e7a07735ccc1efb59c1d2380e91609d7a`
- CI run `34789065745`: SUCCESS
- pair by same `round_no`, require complete A+B, effective deadline = earlier of A/B deadlines
- no threshold/model/LINE-copy/purchase change
- Production merge still requires explicit approval
- Railway still has accidental `diagnostic-round-1654-reader`; a single staged removal awaits dashboard 2FA.

地方競馬:
- Issue #353
- `TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`
- no bulk download / persistent training / Production DB until rights are clear.

## Immediate next work

1. If 9/13 exact BASELINE evaluation is still outstanding, evaluate immutable artifact only against official results.
2. Mark 9/14 V4 Forward as missed/unavailable; never backfill it after outcome.
3. Capture next-date V4 pre-result freeze with run/artifact/SHA provenance.
4. Continue PR #351 fixed Forward evidence without retuning.
5. TOTO: validate PR #161 read-only plan for Round 1654; merge only after explicit Production approval.
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
