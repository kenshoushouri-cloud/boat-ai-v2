# boat-ai-v2 Current State

更新日時: 2026-09-11 JST

このファイルは、`docs/PROJECT_HANDOFF.md` / `docs/PROJECT_HISTORY.md` の長期記録を補完する現在地点の短い運用スナップショットです。再開時は必ずGitHub mainとRailway productionを再取得し、この内容を固定の現在値だと仮定しないでください。

## Current main / open PR

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- 確認時main: `0f44d401107f9b68fb74faeacdc973c867f776c3`（PR #330）。
- PR #330: merged。Opponent Pressureをtiming-safe Railway Cronへ移行。
- Open PR: #329 `Research: audit Course + Opponent pre-production timing integrity` のみ。Draft / research-only。
- PR #331: SELECT-only zero-write監査。2026-09-11の0書込み確認後、証拠を#329へ移して未マージclose。

## Railway production

Project: `boat-v2-postgres`

主要既存service:
- `cron-racer-course-stats`: `python -u collect_racer_course_stats_pg.py`, Cron `15 22 * * *` UTC = 07:15 JST, SUCCESS。
- `cron-final-check`: SUCCESS。
- `cron-learning-all`: SUCCESS。
- PostgreSQL `postgres-recovery`: SUCCESS / 1 replica / 5,000 MB volume。

Opponent Pressure dedicated service:
- service: `cron-opponent-pressure-v2-live`
- source: `kenshoushouri-cloud/boat-ai-v2`
- branch: `runtime/opponent-pressure-railway-cron`
- start: `python -u .github/scripts/opponent_pressure_shadow_v2_compact.py`
- Cron: `0 22 * * *` UTC = 07:00 JST
- restart: `NEVER`
- latest deployment: SUCCESS

Migration試行時に作られた補助service:
- `cron-opponent-pressure-v2`: 空 / Cronなし。
- `cron-opponent-pressure-v2-runner`: Cronなし。Production実行経路として使用しない。

### STAGED patch safety

- 現在、新しいRailway environment STAGED patchが存在し、確認時は180 changes。
- patch IDや件数は将来変わり得るので再開時に再取得する。
- **内容を独立確認するまでaccept-deployしない。**
- active `cron-opponent-pressure-v2-live` の07:00 JST Cron / restart NEVERはすでに実効設定として確認済み。

### PostgreSQL capacity

2026-09-11 24h read-only metrics:
- disk current: 約4.107 GB / 5 GB = 約82.1%
- disk max: 約4.107 GB
- memory current: 約1.162 GB
- memory 24h average: 約0.731 GB
- CPU: low

判断:
- DB volume headroomは約0.893 GB。
- 地方競馬等の別競技データをこのDBへ同居させない。
- Opponent追加はcompact daily rowsのみとし、容量監視を継続する。

## Realtime trifecta odds

PR #320後:
- 公式`official_odds3t`由来の120/60/24完全ticket集合のみ採用。
- 不完全fallbackはfail-closed。
- 自然Production CronでLIVE_VALIDATED済み。

ただし2026-09-08 historical market odds値そのものは独立認証できていないため、その値を使うhistorical ROI承認/model-threshold promotionは引き続きBLOCK。

## Racer Course Top3

Frozen contract:
- BASE = current v24
- COURSE = BASE raw strength + `0.50 * z(official racer-by-course top3 rate)`
- coefficient 0.50固定。再探索しない。
- exact-date official source
- source timestamp <= 08:15 JSTかつrace deadline前
- 必要6艇の当該lane Top3が揃わなければfail-closed

2026-09-10 research evidence:
- evaluated: 1,168 races
- LogLoss delta: `-0.23874376`
- Brier delta: `-0.00606810`
- winner rank delta: `-7.2877`
- 23/23 venues、13/13 datesで3指標すべて改善
- paired bootstrap 5,000 reps: 3指標の95% CIはいずれも0未跨ぎ

2026-09-11 natural collector validation:
- collector version: `2026-09-10 partial-slots-v3`
- target racers: 530
- success: 518
- partial: 22
- failed: 12
- saved rows: 3,045
- racer coverage: 97.7%
- failed 12は`no_usable_metrics`
- timing-safe six-lane Top3 coverage: **117/144 = 81.25%**
- fail-closed: 27 races

旧complete-only実績 83/132=62.88%、事前構造simulation 105/132=79.55%に対し、実運用でもcoverage改善を確認。

判断: source parser/readinessは改善確認済み。ただしCourse 0.50のProduction昇格はまだ許可しない。

## Opponent Pressure

Historical research evidence:
- evaluated: 2,579 races
- winner Brier delta: `-0.00098501`
- winner LogLoss delta: `-0.01503974`
- winner rank delta: `-0.0450`
- fixed coefficient 1.0

Fixed Course 0.50 + Opponent 1.0 common timing-clean sample 1,144R:
- COMBINED vs COURSE LogLoss: `-0.02814106`
- Brier: `-0.00082388`
- rank: `-0.4685`
- paired bootstrap 95% CIはいずれも0未満

### Timing problem and migration

2026-08-25..2026-09-10 read-only timing audit:
- 15 dates / 2,256 rows
- created after 08:15 cutoff: 1,932
- created at/after race deadline: 183
- cutoffを満たした観測日は2/15のみ
- observed later mutation `updated_at > created_at`: 0

このためquality evidenceだけではProductionに上げず、PR #330でcollectorをtiming-safe Railway Cronへ移行。

New collector contract:
- 07:00 JST natural Cron
- complete card必須
- 08:15 JST cutoff
- race deadline前必須
- first-write-wins `ON CONFLICT DO NOTHING`
- GitHub側の旧書込み経路は停止

2026-09-11:
- migration deploymentは約08:28 JSTに初回起動したためcutoff guardが拒否。
- Production DB SELECT-only監査で当日Opponent rows=0、cutoff後created=0、updated=0を確認。
- したがって9/11はnatural success dayに数えない。

次gate:
- 2026-09-12 07:00 JSTから5日連続の自然Cronを監査。
- 毎日、完全行数・model_version・train_end・6艇配列・matched opponents・created/updated timing・deadline timing・後更新有無をread-only確認。
- 5/5でも自動昇格しない。別のProduction promotion reviewが必要。

Current decision:
`RAILWAY_MIGRATION_COMPLETE / OPPONENT_5_DAY_TIMING_VALIDATION_PENDING / BLOCK_NO_PRODUCTION_CHANGE`

## Exhibition ST / Motor GUARD05

Exhibition ST:
- evaluated: 865
- directionally positive but venue heterogeneous
- `BLOCK_MANUAL_REVIEW_ONLY`

Motor GUARD05:
- evaluated: 262
- `affected_evaluated=0`
- treatment effect未識別
- `BLOCK_MANUAL_REVIEW_ONLY`

## Production boundaries

明示的な追加判断なしに変更しない:
- Production v24/FINAL probability logic
- Racer Course coefficient 0.50
- Opponent Pressure coefficient 1.0 / filter
- Racer Course + Opponent combined logic
- BUY/WATCH/SKIP
- LINE notification behavior
- automatic purchase
- N01/N02/Bao thresholds/coefficients
- Railway variables/config/Cron
- 現在のRailway STAGED patch

## Next safe boundary

1. 2026-09-12 07:00 JST `cron-opponent-pressure-v2-live` の最初の自然Cronをread-only監査。
2. 5日連続timing-clean gateを積み上げる。
3. Racer Courseは117/144 source readinessを基準に、欠損27Rの原因分布をread-onlyで追跡する。
4. Production昇格・係数変更・手動backfill/collector再実行はしない。
5. PostgreSQL disk usageを継続監視し、5GB volumeの余裕を守る。

## Restart checklist

1. current GitHub main SHAを確認。
2. open PRを確認。
3. Railway production statusとSTAGED patch件数をread-only確認。
4. `cron-opponent-pressure-v2-live` のsource/start/Cron/restartを確認。
5. `docs/CURRENT_STATE.md`、`docs/PROJECT_HANDOFF.md`、`docs/PROJECT_HISTORY.md`を読む。
6. Issue #42の最新監査ログを確認。
7. 研究結果とProduction昇格を混同しない。
