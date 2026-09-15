# boat-ai-v2 Current State

更新日時: 2026-09-15 23:24 JST

再開時はGitHub main / open PR / Railway Productionを必ず再取得し、この文書のSHA・件数を固定値とみなさないでください。

## Current source of truth

- Boat main: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- Railway project: `boat-v2-postgres`
- PostgreSQL service: `postgres-recovery`
- Volume: 20GB
- Safety: fail-closed / `purchase_action=false`
- Production mutationは明示承認制

## V4

本命アーキテクチャ:
`朝の構造評価/freeze -> 直前の展示・ST・天候・完全オッズ等で全再検証 -> 条件合格時だけ将来自動購入+LINE`

Stage1:
- 6 races / 12 TOP2 exact-order trifecta tickets
- Course 0.50
- Opponent Pressure 1.0 first-place only
- Motor2 beta 0.06, weights 1.0/0.6/0.3
- no Stage1 EV/odds gate
- `purchase_action=false`

Stage2:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- 0..7m complete120 market support
- research-only timing; future LINE/manual purchase timingには流用しない

9/15 formal V4:
- `UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`
- natural run `34917166205`
- 08:16予定 -> 10:25:18 JST開始
- 6 races / 12 ticketsは計算したがearliest deadline 09:36後
- fail-closed、artifactなし、backfill禁止

Draft PR #364:
- V4 capture resilience preregistration
- head `52c081871d38b10b5709eb5a7aa2d2784cb1d7c7`
- fallback scheduler未有効化 / 未merge

## Motor2 cleanup

完了済み:
- fresh Manual backup 2026-09-15 08:27 JST
- 44,203 redundant rows削除
- SHA256 `8d178d854d7b6bfb6a5c6ffdd183e1977f8c6258bd3658c9b0f75fbbf91f203f`
- run `34909832046` SUCCESS_COMMITTED
- protected/ambiguous=0
- evaluator/output diff=0
- post rows=137,030
- `VACUUM FULL`なし
- `MOTOR2_FINAL_SNAPSHOT_MODE=latest_per_race`有効
- one-time cleanup再実行禁止

## Storage / archive

Draft PR #363:
- `Research: preregister V4 storage ownership migration`
- head `7f5198082e0c3362d701906c1eeb9aea382fc0e9`
- latest listed CI/read-only workflows SUCCESS
- Production mutationなし

Latest retention measurement:
- base odds `v2_odds_trifecta`: 7,981,493 rows / relation 1,844,002,816 bytes
- 30d ref: hot 545,940 / cold 7,435,553
- realtime odds relation 536,854,528 bytes
- final_ab 30d: hot 498,208 / cold 557,812
- learning_all 30d: hot 445,565 / cold 22,125

30dはcutoff承認ではなく容量比較のみ。old rows DELETEはBLOCK。

July verified archive 588,156 base-odds rowsでonline/archive exact-output PASS済み:
- probability calibration
- N02 walk-forward / rolling / time-split
- N01/N02 diagnostics
- candidate-filter historical
- Motor2 base-feature
- V24 Motor2 historical
- Feature Lab
- motor/boat A/B
- final_ab analysis

Permanent archiveは未作成。current-day Production consumersはonline保持。`learning_all`はold FINAL previous-odds/drift/steam依存があるためblind stop/delete禁止。

Railway Hobbyは5GB/volume上限。20GB volumeはdownsize不可なので、Hobby移行はfresh <=5GB logical migration + restore-size/headroom proofが必要。

## Old-system retirement

Issue #360が削除gate。legacy/shared dependenciesがゼロになるまで広い削除はしない。

旧daily/monthly LINE reportはDRY_RUN=1済み。

監査用no-Cron serviceやmaintenance serviceは、dependency proof + explicit approvalなしに削除しない。監査目的でservice redeployしない。

## TOTO

- main `74fe4cdf470f553883da88b6e19528ec82e9b079`
- PR #161 merge済み
- `toto-ai-core` deployment `b9475314-be87-4f3c-b496-1ac4cca3ba64` SUCCESS
- natural Cron 9/15 09:04 / 21:04 JSTともRound1654 pairing PASS
- A/B each 5 matches + 5 live votes
- effective deadline 2026-09-19 17:50 JST
- `delivery_window=too-early`
- Forward A/B=0/0
- `purchase_action=false`
- manual rerun/retune禁止
- unrelated `diagnostic-round-1654-reader` removalは自動適用しない

## Local horse

`TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`

権利明確化までbulk ingest / persistent training / commercial use / external inquiry sendなし。

## Immediate next work

1. 9/15 V4 unavailableを固定し、後付け再構築しない。
2. PR #364 fallback設計をreview。Production scheduler変更なら承認を取る。
3. PR #363で残るhistorical/manual consumerのArchive対応またはretirement proofを続ける。
4. Permanent archive先決定前にold rowsを削除しない。
5. fresh logical restoreサイズでHobby 5GB readinessを証明する。
6. Issue #360のzero-consumer gateを継続する。
7. TOTO Round1654は自然Cronだけ監視する。

## Safety boundary

明示承認なしで変更しない:
- Production v24/FINAL
- coefficients / thresholds / BUY/WATCH/SKIP
- LINE actual send
- Railway Production config/Cron/Variables/services/volume
- Production DB writes/deletes/schema/VACUUM
- automatic purchase

必要データを容量節約だけで削除しない。historical / BASELINE / V4 Forward / Production evidenceを混ぜない。
