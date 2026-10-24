# 新競艇AI開発プロジェクトNo.2 — 現行短縮引継（2026-10-24 19:06 JST）
**Current handoff（こちらを正本とする）。** 古い`LIVE_HANDOFF_20261024_1710_COMPACT.md`と巨大な20261023手渡しファイルは履歴。毎回読み直さない。実行SHA/表行数/運用状況は必要なものだけliveで再確認。

## 目的・費用・安全
- V5主力のボートレースAI。本番用V5研究（6艇確率、三連単120券、paper-only shadow記録・日次評価、前日13Counter）を再利用し、2025-07以降の全データを検証。精度を下げる要素は使用せず収集は継続。目標2026年10月末の**非購入限定運用**（保証ではない）。自動購入は本番モデル確定・実first-observation・実ROI・試験後の別承認までOFF。
- Railwayは月$15–20を超えないよう最低コスト（Railway Agent/AI使用禁止）。ConoHa VPSと`railway` Postgresが主、`/opt/boat-ai-v5`がGit checkout。`/opt/boat-ai-collector`はGit管理外。1回1作業、短いツール呼出、Termiusへ貼れる明瞭な短いコードを提示。

## 原本とステージの確定マップ
- 恒久的な保存先一覧：`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`、技術マップ`docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json`、コード正本`boat_shared_storage_contract.py`。
- 主DB`railway`の13物理`public.v2_*`が現在の書込元、`boat_data.*`13系統は非更新VIEWでV5から参照可能。**新物理stage先は一律`boat_data_stage.<共通VIEWの短名>`へ統一**。すでに存在する`boat_data_stage.venues`24件を再コピー・再作成しない。`v5_data.raw_*`は昔の候補名であり今回のstage直接コピー先として使わない。現状stage1/13、live物理切替0/13 NO-GO。
- 履歴は別DB`boat_history_archive`（`public.v2_recent_form_archive`とarchiveのレース/選手条件snapshotなど）。ローカルバックアップ`/var/backups`あり、同VPSでの限定復元検証のみ。Google Drive`v5_gdrive:`新規書込403 RATE_LIMITでSTOP、完全独立外部復元証明なし。V3/V4原本/バックアップを削除・上書き禁止。
- 2026-10-24 17:39のREAD ONLY六日標本展示6艇順位完全：2025/07/15 155/156、10/15 141/144、2026/01/15 165/168、04/15 132/132、07/15 167/168、10/20 29/144。展示の`historical/final_ab/conoha_forward`など複数ラベルが既にある。探し直すよりV5への整理が主。historicalや事後取得・mutable `snapshot_at`は真の決定時点初観測を証明せず、ROI/BUY根拠にしてはならない。

## 直近の実行済み結果
- V5研究合成：as-of bridge9/9、shadow journal6/6、日次3/3=18/18 PASS。
- 18:41 一括準備`deploy/conoha/v5_cutover_one_command_prepare_20261024.sh` PASS。`PREPARATION_REPORT=/var/backups/v5_prepare_wLz5IWY7`、source unchanged。18:20 writer監査は4timer active、瞬間に他DB接続0、root/postgres cron該当0（全書込経路認証ではない）。
- 18:50 `v5/offline_stage_batch_plan.py`旧ルートで合成5/5 PASS。
- 18:56 原本13表のPK/NULL/default/identity/serial/FK/trigger`deploy/conoha/v5_stage_13_key_schema_gate_readonly_20261024.sql` 13行READ ONLY/ROLLBACK PASS。一部原本にshared sequence defaultがある。
- 19:06 `v5/offline_stage_chunk_copy_sql.py`旧ルートで6/6 PASS。**異なる合成検査29/29 PASS（19:06までの旧stage-map）。** 本番実コピーと段階同期の証明ではない。
- **19:06以降のGitHub新規実装・修正（まだテスト未実行）**：
  - `v5/offline_stage_batch_plan.py`の12候補のschemaを`boat_data_stage`へ整合し、`boat_shared_storage_contract.py`のvenues `STAGED_PILOTS`も実在`boat_data_stage.venues`に訂正。対応テスト2本を更新。
  - `v5/offline_stage_chunk_copy_sql.py`に`make_key_select`を追加。既存`make_window`を再利用しSELECT後の実末尾PKからbounded INSERTを生成する。
  - `deploy/conoha/v5_online_stage_batch_copy.py` は**実行器コードの新規追加**。default read-only preview、`--all`は12ソースのStage実在/PK/形状/危険のみ短く表示、COPYなし。`--copy`は単一ソース、物理stageが存在し列/PK/sequence/trigger互換、環境許可`V5_ALLOW_STAGE_COPY=YES`と別証拠ファイルにCOPY_GATES全部trueが必要。ステージの新規作成、VIEW切替、買い、サービス停止、夜間予約はしない。***実DBでの動作・オフライン新テスト6件は未確認。***
  - `tests/test_v5_online_stage_batch_copy.py`6件追加。`tests/test_v5_offline_stage_batch_plan.py`、`tests/test_v5_offline_stage_chunk_copy_sql.py`、`tests/test_boat_shared_storage_contract.py`は新stage名への修正後**未再実行**。既存`deploy/conoha/boat_shared_staging_delta_plan_offline.py`全PK INSERT/UPDATE/DELETE差分計画を再利用。
- **注意：今回の新実行器はコピー先がまだ存在しない12表へは書き込めない**。stage DDL作成/配備と追加の明示実行前ゲートを先に実装。途中までコピーした内容の一貫性・再開checkpoint・完全差分追込も未検証。新スクリプトの動作を合格と主張しない。

## 深夜の無人切替
- ユーザーは夜中に手動不可、収集の短時間停止・後日補完を許容。提案窓 **将来の03:30〜04:00 JST**、01:20 catchup完了と07:00 morningまでの復旧を前提。**今夜2026-10-25の本番切替は予約していない／NO-GO。**
- 独立バックアップ復元、全writer/child job、最後の一貫した全PK insert/update/delete差分、スタート/ストップ/復元・rollback自動訓練と別の切替承認が必須。公式K/結果は過去補完可。後取得の瞬間オッズ/気象/展示初回時刻は元のbefore-decision証明と混同しない。
## 2026-10-24 19:30 JST：ステージ統合24テストPASS、DBプレビューはdriver欠如で未確認
- ユーザーTermius画面：修正後のstage関連17テスト、storage契約7テスト、**計24/24 PASS**（19:06時点29件の一部と重複。29+24を固有テスト数とは数えない）。`V5_STAGE_TESTS_PASS`。
- 続く実DB `--all` は `STOP: psycopg not installed in runner environment`。**DBのプレビューが実行されていない**。ライブラリ新規導入や既存サービス停止不要。
- GitHub `deploy/conoha/v5_online_stage_batch_copy.py`を修正：`--all` のみ `psycopg`未導入時は既存`psql`で`railway`の12固定ソース/ステージのカタログだけREAD ONLY/Rollback取得。単一表`--copy`は引き続きpsycopgと独立復元・明示証拠が必要で、何も自動実行しない。`tests/test_v5_psql_stage_preview.py`4件を追加。**新4件と実psqlプレビューは未実行**。
- 本番13 VIEW維持、stage venues 1/13、live physical 0/13 NO-GO。03:30未予約、Drive403停止、BUY OFF。
## 2026-10-24 19:38 JST：psql fallback及び12ステージ状態監査PASS
- ユーザーTermiusスクリーンショット：`tests/test_v5_psql_stage_preview.py`の4件`Ran 4 tests`/`OK`。psycopg未導入でも既存psql READ ONLYを使う`--all`が`12 rows`、`ROLLBACK`、`V5_STAGE_ALL_12_PREVIEW_READ_ONLY_FINISHED`、`STAGE_CANDIDATES=12 COPY_PERFORMED=NO CUTOVER=NO_GO`で正常終了。
- 全12 source `public.v2_*` はrelkind=r、全12 `boat_data_stage.*` は`ABSENT`、PKは`id`、`race_id`、`race_id,lane`混在。既存venues `boat_data_stage.venues`は保持、stage1/13、live cutover0/13 NO-GO。
- GitHub `deploy/conoha/v5_stage_12_bootstrap_plan_readonly_20261024.sql`を追加。12テーブルのsource PK/default/generated/FK/trigger/サイズと、共有`nextval`を避けた`CREATE TABLE ... LIKE INCLUDING CONSTRAINTS INCLUDING INDEXES`候補をREAD ONLYで一括出力する。**未実行**。実際のDDL実行は別途独立復元/明示承認のgate後。
- 差分追従、局所チャンクCOPY、切戻しは未完了。Drive403 STOP、BUY OFF。03:30無人切替未予約。

## Next ONE task
**既存SQLの12表空ステージ作成計画をConoHa READ ONLYで1回だけ検証**（`deploy/conoha/v5_stage_12_bootstrap_plan_readonly_20261024.sql`）。確認後、独立バックアップ復元・実表DDLの安全条件を踏まえて12物理stage一括作成スクリプトを仕上げる。実コピー/DDL/VIEW切替/collector STOPはまだしない。チャットごとに保存先探索を繰り返さない。
