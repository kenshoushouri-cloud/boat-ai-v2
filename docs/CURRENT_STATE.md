# boat-ai-v2 Current State

更新日時: 2026-09-10 JST

このファイルは、`docs/PROJECT_HANDOFF.md` / `docs/PROJECT_HISTORY.md` の長期記録を補完する、現在地点の短い運用スナップショットです。再開時はGitHub mainとRailway productionを再確認し、この内容を固定の現在値だと仮定しないでください。

## Current main

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- この更新開始時に確認したmain: `d514b8a52c4dd15e820f5e47e29c424d6b675e55`（PR #325 docs-only current-state更新後）。この文書更新自体でmainが進む可能性があるため、再開時は必ず再取得する。
- 最新の機能コード変更基準: `7f64a11c397bb8f41e6348ca0fc8c8068bee5adb`（PR #324）。
- PR #320: merged。リアルタイム3連単公式parserを構造化し、120/60/24の完全ticket集合だけを採用。不完全なbase odds fallbackをfail-closed化。自然CronでLIVE_VALIDATED済み。
- PR #324: merged。Racer Course statsで公式`-`を欠損として位置保持し、部分的に取得できたコース値を安全に保存。欠損列はupsert対象から外し、既存有効値を消さない。

## PR cleanup

- PR #169: temporary base-odds refresh。未マージでclosed。復活させない。
- PR #319: historical odds evidence research。修正を#320へ移した後、未マージでclosed。
- PR #321: stale documentation snapshot。後続変更で陳腐化したため未マージでclosed。
- PR #322: Opponent Pressure incremental Forward research。証拠保持後、未マージでclosed。
- PR #323: one-shot Forward health bundle。証拠保持後、未マージでclosed。
- PR #326: Racer Course 0.50 + Opponent Pressure 1.0 fixed combined Forward research。証拠保持後、未マージでclosed。
- #326 close後のfeature/research open PRは0件。このcurrent-state更新用Docs PRはmergeまで一時的にopenになり得る。

## Railway production

Project: `boat-v2-postgres`

- source-linked servicesは#324 main merge後の自動deployで確認対象すべてSUCCESS。
- `cron-racer-course-stats` start command: `python -u collect_racer_course_stats_pg.py`
- `cron-racer-course-stats` schedule: `15 22 * * *` UTC = 07:15 JST
- `cron-final-check`: SUCCESS
- `cron-learning-all`: SUCCESS
- PostgreSQL `postgres-recovery`: SUCCESS / 1 replica
- Railway variables/config/Cronは手動変更していない。
- environmentに既存のSTAGED patch 174 changesが残っている。未適用のまま維持し、目的を確認せずaccept-deployしない。

## Realtime trifecta odds incident

2026-09-08 historical auditで、固定19Rの`v2_odds_trifecta`と`v2_realtime_odds_snapshots`が完全120ではない問題を調査。

確定した原因:
- realtime側の旧簡易`parse_odds3t`が現行公式ページ構造と非互換。
- 公式取得が80件未満になると、不完全な`v2_odds_trifecta`へfallback。
- その部分集合がrealtime snapshotへ伝播していた。

PR #320後の自然Production Cronでは:
- `official_odds3t`由来の120通りsnapshotを継続確認。
- 早い時点で不完全なレースはodds=0でfail-closedし、後のCronで120へ回復。
- 観測区間で`v2_odds_trifecta_fallback`再伝播0件。

判断: `LIVE_VALIDATED`。

ただし2026-09-08当時の市場オッズ値そのものは独立認証できていないため、historical ROI承認やその証拠を使うmodel/threshold promotionはBLOCKのまま。

## Racer Course Top3

Frozen Forward contract:
- BASE = current v24
- COURSE = BASE raw strength + `0.50 * z(official racer-by-course top3 rate)`
- coefficient 0.50固定。後付け再探索しない。
- exact-date official source
- source timestamp <= 08:15 JSTかつdeadline前
- 必要な6艇の当該lane Top3値が揃わなければ適用しない。

2026-09-10 read-only Forward evidence:
- evaluated: 1,168 races
- LogLoss delta: `-0.23874376`
- Brier delta: `-0.00606810`
- winner rank delta: `-7.2877`
- observed venues: 23/23で3指標すべて改善
- observed dates: 13/13で3指標すべて改善
- paired bootstrap 5,000 reps: 3指標の95% CIはいずれも0未跨ぎ
- promotion state: `BLOCK_MANUAL_REVIEW_ONLY`

Source coverage bottleneck:
- 2026-09-10 collector target 493 racers
- old complete-only parser: 458 complete / 35 `parse_incomplete`
- 35 racer failuresが49/132 racesのeligibility欠損へ波及
- structural read-only simulation: baseline safe 83/132 = 62.88% -> partial-slot parserなら105/132 = 79.55%
- recovered 22 races / remaining fail-closed 27 races / valid distributions 105

PR #324で部分slot保持をmainへ反映。ただし9/10は08:15 cutoff後だったため手動再収集は行っていない。最初の正しい実運用確認は2026-09-11 07:15 JSTの自然Cron。

## Opponent Pressure

2026-09-10 incremental Forward over current v24:
- evaluated: 2,579
- winner Brier delta: `-0.00098501`
- winner LogLoss delta: `-0.01503974`
- winner rank delta: `-0.0450`
- Brier/LogLoss improved on 16/17 days
- Brier improved on 19/24 venues; LogLoss improved on 20/24 venues
- fixed coefficient 1.0; subgroupを後付けで除外しない

判断: `PROMISING_INCREMENTAL_FORWARD_RESEARCH_ONLY` / `BLOCK_NO_PRODUCTION_CHANGE`。

## Fixed combined Forward: Racer Course 0.50 + Opponent Pressure 1.0

PR #326で、係数探索・後付けsubset選択なしのread-only固定併用比較を実施。

固定条件:
- COURSEはfrozen Racer Course Forwardの120-ticket分布をそのまま使用。
- Racer Course coefficient = 0.50固定。
- Opponent Pressure coefficient = 1.0固定、保存済み`adj_win - base_win`を使用。
- Opponent Pressureは1着周辺確率だけを調整し、元分布の `P(2着,3着 | 1着)` を保持。
- BASE / COURSE / OPP / COMBINEDを同じ共通レースで比較。

Timing-clean common sample:
- joined: 1,261
- official evaluated: **1,144**
- pending: 93
- invalid Course: 0
- invalid Opponent: 24
- invalid result: 0
- Opponent除外24件は**全件 `created_at_or_after_deadline`**。締切後作成行をForward証拠に使わず除外した。

1,144Rの結果:
- BASE: LL `4.49065800` / Brier `0.98565326` / rank `32.6469`
- COURSE: LL `4.25117257` / Brier `0.97958549` / rank `25.2028`
- OPP: LL `4.46394449` / Brier `0.98505901` / rank `30.9677`
- COMBINED: LL **`4.22303151`** / Brier **`0.97876161`** / rank **`24.7343`**

COMBINEDのCOURSEに対するincremental delta:
- LogLoss: **`-0.02814106`**
- Brier: **`-0.00082388`**
- ticket rank: **`-0.4685`**

安定性（COMBINED vs COURSE）:
- 13日: LogLoss 13/13改善、Brier 13/13、rank 10/13、3指標同時10/13
- 23場: LogLoss 19/23改善、Brier 20/23、rank 13/23、3指標同時13/23

Paired bootstrap 5,000 reps / seed 20260910、COMBINED - COURSE:
- LogLoss 95% CI **[-0.03429284, -0.02201693]**
- Brier 95% CI **[-0.00101761, -0.00062761]**
- rank 95% CI **[-0.75526661, -0.18791521]**

判断: `SUPPORTS_FIXED_COMBINED_FORWARD_RESEARCH_ONLY`。

意味:
- 現在のtiming-clean common sampleではOpponent PressureはCourse 0.50に対して追加価値を示した。
- ただしこれはProduction昇格許可ではない。
- Racer Course partial-sourceの自然Cron readiness確認と、別のpre-production reviewが必要。
- promotionは `BLOCK_NO_PRODUCTION_CHANGE`。

## Exhibition ST / Motor GUARD05

Exhibition ST:
- evaluated: 865
- directionally positive but venue heterogeneous
- promotion: `BLOCK_MANUAL_REVIEW_ONLY`

Motor GUARD05:
- evaluated: 262
- `affected_evaluated=0`
- treatment effectは未識別
- promotion: `BLOCK_MANUAL_REVIEW_ONLY`

## Production boundaries

明示的な追加判断なしに変更しない:
- Production v24/FINAL probability logic
- Racer Course coefficient 0.50
- Opponent Pressure coefficient/filter
- Racer Course + Opponent combined logic
- BUY/WATCH/SKIP
- LINE notification behavior
- N01/N02/Bao thresholds/coefficients
- Railway variables/config/Cron
- 174 STAGED changes

## Next safe boundary

1. 2026-09-11 07:15 JST `cron-racer-course-stats` の自然実行をread-only監査する。
2. `target_racers / success_racers / partial_racers / failed_racers / saved_rows / coverage`を確認する。
3. partial-slot parserで当日08:15前の必要lane coverageが実際に改善したか評価する。
4. 手動collector再実行やbackfillはしない。
5. Racer Course Top3単独またはOpponent Pressure併用のProduction昇格は、上記source readiness確認後も別の明示判断とpre-production reviewを要求する。

## Restart checklist

1. current GitHub main SHAを確認。
2. open PRを確認。
3. Railway production statusと174 STAGED changesをread-only確認。
4. `docs/CURRENT_STATE.md`、`docs/PROJECT_HANDOFF.md`、`docs/PROJECT_HISTORY.md`を読む。
5. Issue #42の最新監査ログを確認。
6. 研究結果とProduction昇格を混同しない。
