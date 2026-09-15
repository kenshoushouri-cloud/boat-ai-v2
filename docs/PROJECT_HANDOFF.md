# boat-ai-v2 Project Handoff

更新: 2026-09-15 23:24 JST

この文書はトーク上限・担当交代時のSource of Truthです。再開時は、ここに書かれたSHA・件数・Railway状態を固定値とみなさず、必ずGitHub `main` / open PR / Railway Productionを再取得してから作業してください。

## 再開時の最初の指示

> `kenshoushouri-cloud/boat-ai-v2` の `docs/PROJECT_HANDOFF.md` と `docs/CURRENT_STATE.md` を最初に読み、GitHub main / open Draft PR / CI / Railway Production health をread-onlyで再確認してから続行する。GitHub mainをコードのSource of Truth、Railway PostgreSQLをProduction dataのSource of Truthとする。安全なread-only監査、research、Draft PR、CI、docs更新は継続可。Productionへ影響する変更は明示承認まで実施しない。

## Source of Truth / approvals

- Boat repository: `kenshoushouri-cloud/boat-ai-v2`
- Current main at this update: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- TOTO repository: `kenshoushouri-cloud/toto-ai-v1`
- TOTO current main: `74fe4cdf470f553883da88b6e19528ec82e9b079`
- Boat Railway project: `boat-v2-postgres`
- Production PostgreSQL service: `postgres-recovery`
- Production volume: `postgres-volume`, 20GB, mount `/var/lib/postgresql/data`
- Safety default: fail-closed / `purchase_action=false`

明示承認が必要:
- Production-effect PR merge
- Railway Production Variables / Cron / service / volume / migration変更
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Production model / coefficient / threshold / candidate logic変更
- LINE actual-send behavior変更
- Production Forward persistence新規変更
- automatic purchase
- paid data contract
- external inquiry send

ユーザーは安全なread-only監査、研究、Draft PR、CI、docs/handoff更新を継続してよいと承認済み。必要データは容量節約だけを理由に捨てない。

## 新システム本命アーキテクチャ

本命は以下:

`朝の構造評価 / candidate freeze -> 直前の展示・ST・天候・完全オッズ等で全再検証 -> 条件合格時だけ将来自動購入 + LINE`

重要:
- 朝はPurchase確定ではなくCandidate Discovery。
- 旧morning/day/nightの3回PREは、そのまま新システムへ継承しない。
- 直前判定で朝候補を全て却下して0件でもよい。
- Challengerとして `直前のみ全対象を評価 -> BUY/SKIP` をShadow比較する。
- Primary vs Challengerはprospective 30/50/100 casesで比較し、結果後に都合のよい方式を選ばない。
- automatic purchaseは別途明示承認とfail-closed safety validation完了まで有効化しない。

旧Production FINALはT-30..0分を15分刻みで回し、通常は約15〜30分前にdecision/LINEへ入る。したがって現在のStage2 `0..7m` はlate-market research専用で、将来の人間向けLINE/購入時刻へそのまま流用しない。

## Candidate Discovery V4

固定Stage1 research contract:
- 6 races/day
- TOP2 exact-order trifecta = 12 core tickets
- Course coefficient `0.50`
- Opponent Pressure `1.0`, first-place only
- Motor2 beta `0.06`, weights `1.0 / 0.6 / 0.3`
- 4 structural metrics equal-weight rank
- Stage1 EV/odds gateなし
- legacy S01-S05 carryoverは現在比較用に残る
- `purchase_action=false`

Stage2 frozen hypothesis:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- complete 120-ticket market snapshot, deadline 0..7m
- core_order1のみ市場TOP2 support注記
- Stage1を削除・rerankしない
- milestone 30/50/100 supported cases
- post-outcome retuning禁止

Trio副研究はDraft PR #362で別track。trifectaとpoolしない。

### 9/13 BASELINE

これはV4ではない。immutable baseline artifactをexact評価済み:
- core 6 races / 12 tickets / 2 hits / +220 JPY / ROI 118.333%
- legacy 2 races / 2 tickets / -200 JPY
- total +20 JPY / ROI 101.429%
- source JSON SHA256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

1日だけのBASELINE結果をV4性能やthreshold調整へ混ぜない。

### 9/15 formal V4 incident

2026-09-15 formal V4 evidenceは:

`UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`

確定事実:
- planned primary: 08:16 JST
- natural scheduled run `34917166205`
- started 10:25:18 JST, 約2h09m遅延
- read-only feedは6 core races / 12 ticketsを計算
- earliest frozen-feed deadlineは09:36 JST
- deadline後だったためwrapperが正しくfail-closed
- artifact uploadなし
- backfill / manual reconstruction / result-after relabelingなし

これはmodel品質失敗ではなくcapture orchestration/timing failure。

Draft PR #364 `Research: preregister V4 capture resilience after 9/15 schedule delay`:
- open / Draft / mergeable
- head `52c081871d38b10b5709eb5a7aa2d2784cb1d7c7`
- primary 08:16 GitHub schedule維持
- future-only independent fallbackを08:25頃に検討
- duplicate valid capture時は最初のvalid post-08:15 artifactだけformal
- Railway Cron/serviceをfallbackとして有効化する場合は別途明示承認が必要
- 自動merge禁止

## Motor2 cleanup — 完了

ユーザー明示承認済みの限定cleanupは完了済み。

Fresh manual backup:
- 2026-09-15 08:27 JST
- Railway UI表示は約4.28GB referenced
- restore可能なfresh safety pointとして確認済み

Cleanup:
- exact candidate 44,203 rows
- 2,456 races
- 908 snapshot keys
- range 2026-08-20..2026-09-12
- SHA256 `8d178d854d7b6bfb6a5c6ffdd183e1977f8c6258bd3658c9b0f75fbbf91f203f`
- run `34909832046`: `SUCCESS_COMMITTED`
- protected intersection=0 / ambiguous latest=0
- Performance/PRE/FINAL/latest-PRE-health outputs diff=0
- post rows=137,030
- conservative final/final removable=0 after cleanup
- `VACUUM FULL`未実施

Production `MOTOR2_FINAL_SNAPSHOT_MODE=latest_per_race` は既に自然Cronで有効。再設定不要。Motor2 one-time cleanupを再実行しない。

## Storage / Archive / October cost plan

Draft PR #363 `Research: preregister V4 storage ownership migration`:
- open / Draft / mergeable
- branch `research/v4-storage-ownership-migration-20260915`
- current head at this update `7f5198082e0c3362d701906c1eeb9aea382fc0e9`
- latest listed CI / read-only workflows are all SUCCESS
- Production mutationなし

Latest read-only retention audit (2026-09-15):
- `v2_odds_trifecta`: 7,981,493 rows / logical payload 830,075,423 bytes / relation 1,844,002,816 bytes
- 30d reference: hot 545,940 rows / 56,777,757 bytes; cold 7,435,553 / 773,297,666
- `v2_realtime_odds_snapshots` relation: 536,854,528 bytes
- `final_ab`: 1,056,020 rows; 30d hot 498,208 / 94,924,296 bytes; cold 557,812 / 106,331,968
- `learning_all`: 467,690 rows; 30d hot 445,565 / 84,861,496; cold 22,125 / 4,248,000
- 30dは承認済みretention cutoffではない。容量比較用referenceのみ。
- DELETE直後のphysical volume reclaim値ではない。

Archive pilot / exact-output equivalence:
- July `v2_odds_trifecta` verified archive: 588,156 rows
- online/archive exact-output PASS:
  - Historical readiness
  - Feature Lab
  - `compare_motor_boat_ab_pg.py`
  - `analyze_final_ab_features_pg.py`
  - probability calibration: ready 4,889 / ticket rows 586,680
  - N02 walk-forward: 13 bets
  - N02 rolling: 13 bets
  - N02 time-split: 13 bets
  - N01/N02 diagnostics: N01 25 bets / N02 13 bets
  - candidate-filter historical: ready 4,889 / rule selections 586
  - Motor2 base-feature: processed 4,853 / candidate rows 75
  - V24 Motor2 historical: processed 4,853
- all are Production read-only, ephemeral archive, permanent uploadなし
- current PR also has realtime archive export/entry footprint/read-through validation; latest corresponding CIはSUCCESS

重要なblocker:
- Permanent archive/Bucketはまだ作成していない。
- old rowsのDELETEはまだBLOCK。
- `run_odds_window_pg.py` / daily prepare等のcurrent-day Production pathはKEEP ONLINE。
- manual OOS / historical consumersはarchive read-through対応またはretirement proofが必要。
- `learning_all`はold FINALのprevious-odds/drift/steamへ間接依存するため、blind stop/delete禁止。
- `v2_odds_trifecta`は「無駄」ではなくresearch/backtest asset。archive-first。

Railway Hobbyはper-volume 5GB上限。現在の20GB volumeはin-place downsize不可なので、Pro→Hobbyは**fresh <=5GB compatible volume/serviceへのlogical migration**が前提。必要データを削って5GBへ押し込まない。fresh restore後の実サイズ/headroomで判断する。

Cost target:
- October: ChatGPT Go + Railway Hobby/low usageでcombined <= USD20/monthを目標
- Oct 1–2: read-only usage/storage/dependency audit
- Oct 3 billing boundary: independence/data-preservation/migration safetyが通ればRailway Pro→Hobbyを検討
- Oct 14までにChatGPT Plus→Goを検討
- コスト回収のためにprediction threshold/stake/candidate countを変えない

## Old-system retirement

Issue #360 `Migration: retire old selector data after V4 independence` がgate。

旧システム専用データを広く削除する条件:
1. V4 feedがlegacy shadowを読まない
2. Stage2 market ownershipが新システム側で保全
3. prospective evidence蓄積
4. old selector/report停止が新システムへ無影響
5. fresh dependency scanでzero consumers
6. exact inventory rows/date/size + digest
7. recovery proof
8. shared tables除外
9. explicit approval後にbounded delete/drop + verify

旧daily/monthly report LINE actual-sendは既にDRY_RUN=1へ変更済み。

Railway no-Cron audit/maintenance servicesはcleanup候補だが、依存確認と明示承認なしに削除しない。特に監査のためにaudit serviceを再deployする方法は使わない。過去にread-only監査のつもりでstaged Function作成やaudit service redeployが発生したため、今後はProduction service mutationを伴わない経路だけ使う。

## TOTO handoff

Repository `kenshoushouri-cloud/toto-ai-v1`。

PR #161はユーザー明示承認でmerge済み:
- current main `74fe4cdf470f553883da88b6e19528ec82e9b079`
- Railway `toto-ai-core` deployment `b9475314-be87-4f3c-b496-1ac4cca3ba64`: SUCCESS
- Cron `0 */12 * * *`
- same-round A/B pairing / effective deadline=`min(A,B)` fail-closed

Round 1654 Production natural validation:
- 2026-09-15 09:04 JST: PASS
- 2026-09-15 21:04 JST: PASS
- A=5 matches / 5 live votes
- B=5 matches / 5 live votes
- target_round=1654
- effective deadline = 2026-09-19 17:50 JST
- delivery_window=`too-early`
- Forward A/B=0/0
- `TOTO_WEEKLY_PIPELINE=SKIP reason=delivery-window-too-early`
- `purchase_action=false`
- manual rerun / retuneなし

Round1653 frozen baseline:
- A 4/5
- B 1/5
- combined 5/10
- mini-toto ticket 0/2
- post-result retune禁止

Unrelated `diagnostic-round-1654-reader` staged removalは別Production action。自動適用しない。

## Local horse

Issue #353。

Current decision:
`TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`

権利が明確になるまで:
- NAR bulk ingestしない
- long-term storageしない
- persistent ML trainingしない
- commercialize/distributeしない
- external inquiryを勝手に送らない

ここは容量ではなく利用権がblocker。

## Immediate next work

1. 9/15 V4を正式unavailableのまま固定し、後付け再構築しない。
2. PR #364 fallback設計をreviewし、Production scheduler変更が必要ならユーザー承認を取る。
3. PR #363で残るhistorical/manual consumersをverified archive read-throughへ移すかobsolete retirementを証明する。
4. Permanent archive先を決める前にold rowsを削除しない。
5. archive + online hot-set + fresh logical restoreの実サイズでHobby 5GB readinessを証明する。
6. Issue #360の旧システムzero-consumer gateを継続する。
7. TOTO Round1654は自然Cronだけを監視し、締切前にmanual rerunしない。
8. V4 / TOTO / Storage evidenceを混ぜず、historical / BASELINE / V4 prospective / Productionを明確に分離する。

## 最後の安全ルール

- fail-closed
- `purchase_action=false`
- thresholdを候補数・料金回収・月利益目標のために緩めない
- 結果後にForwardを作り直さない
- historical / BASELINE / V4 Forward / Production evidenceを混ぜない
- 必要なraw/timing/reproducibility dataを容量節約だけで捨てない
- Production mutationは必ず明示承認範囲を確認する
