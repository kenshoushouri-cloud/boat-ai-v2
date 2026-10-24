# V5データ保存先・集約進捗ボード（2026-10-24 17:39 JST）

> **最新優先：2026-10-25 08:16 JST — 初回物理stageコピー13/13完了。** 先行venues24行に加え12系統の全初回COPYが10/25 02:50〜02:53 JSTで `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。計12系統13,129,507行。原本 `public.v2_*` と13 live VIEWは現状維持（本番route切替0/13）。**更新/削除/追加の追込・独立復元・本番切替は未完了**。以降の旧「1/13」「未コピー」は過去時点の記録。次は `deploy/conoha/v5_stage_13_snapshot_proof_readonly_20261025.sql` をConoHaで実行しメタ検査。再コピーしない。BUY OFF。

**次チャット以降はこの1ファイルを最初の正本として使う。** 保存先を探し直さず、差分が生じたらこのボードのみ更新。GitHub `docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json`が13表write/read routeの技術的な基準。旧長文handoffの一括再読は不要。履歴は削除しない。

## 現在どこに保存されているか（新規推測を含まない）
- ConoHa PostgreSQL `railway`：現行物理原本`public.v2_*`、V5用共有参照`boat_data`（13件、すべて非更新VIEW）。**V5は現時点でもVIEW経由で既存原本を参照可能。** その意味の「使用可能」と、物理正本がV5へ移管済みであることは別。
- 同VPS `boat_history_archive`：既存履歴`public.v2_recent_form_archive`約826MB、`archive.v2_realtime_race_condition_snapshots`約118MB、`archive.v2_realtime_racer_condition_snapshots`約117MB。最近の展示データはこの保管DBではなく主に`railway`現行表から確認。2026-10-24 filtered catalogにexhibition専用テーブル名なし。DBを増設・再COPYしない。
- Git管理コード：`/opt/boat-ai-v5`、Git外collector：`/opt/boat-ai-collector`。ConoHaローカルバックアップ：`/var/backups`。従来V3/V4/Railwayと以前のGoogle Driveは別世代保全資産であり上書き・消去しない。Google Drive `v5_gdrive:`書込403 RATE_LIMIT以降はSTOP。
- 原本の全期間、収集時刻、完全性の認証は**未完了**。特定VIEWで0件でも「過去原本が消失」と言わない。

## 共有13系統の固定ソースマップ
| group | 物理原本（railway） | 共通参照（boat_data VIEW） | V5集約状況 |
|---|---|---|---|
| 会場 | `public.v2_venues` | `venues` | **隔離`boat_data_stage.venues`へ24件初回コピーのみ完了、同一時点差分0** |
| レース | `public.v2_races` | `races` | 本番移管未実施 |
| 出走 | `public.v2_race_entries` | `entries` | 本番移管未実施 |
| 結果 | `public.v2_results` | `results` | 本番移管未実施 |
| 艇別結果/K | `public.v2_result_entries` | `racer_results` | 本番移管未実施 |
| 3連単オッズ | `public.v2_odds_trifecta` | `trifecta_odds` | 本番移管未実施 |
| 選手コース統計 | `public.v2_racer_course_stats_snapshots` | `racer_course_stats_snapshots` | 本番移管未実施 |
| 直前出走 | `public.v2_realtime_entry_snapshots` | `entry_snapshots` | 本番移管未実施 |
| 直前展示 | `public.v2_realtime_exhibition_snapshots` | `exhibition_snapshots` | 本番移管未実施 |
| 直前3連単odds | `public.v2_realtime_odds_snapshots` | `odds_snapshots` | 本番移管未実施 |
| 気象 | `public.v2_realtime_weather_snapshots` | `weather_snapshots` | 本番移管未実施 |
| レース水面条件 | `public.v2_realtime_race_condition_snapshots` | `race_condition_snapshots` | 本番移管未実施 |
| 選手直前状態 | `public.v2_realtime_racer_condition_snapshots` | `racer_condition_snapshots` | 本番移管未実施 |

集約の目標は**V5で論理的に統合参照でき、最終的にはV5用の物理正本へ移管**すること。VIEWのみで物理整理完成とは呼ばない。現状`stage=1/13`、**live physical=0/13 NO-GO**。一部研究テーブル（V24 motor shadow等）は正式な予測原本に混ぜない。

## 展示原本の場所は確認済み：再取得より再利用
10/24 17:39 ConoHa read-only六日標本（`deploy/conoha/v5_exhibition_6_dates_coverage_readonly_20261024.sql`、ROLLBACK）：
- 2025-07-15：156レースのうち同一ラベルで展示6艇/順位6=155
- 2025-10-15：144→141
- 2026-01-15：168→165
- 2026-04-15：132→132
- 2026-07-15：168→167。うち`historical`167、`final_ab`74（ラベル間重複のため合計しない）
- 2026-10-20：144→29。うち`conoha_forward`28、`conoha_timeout_probe`1（**診断用除外**）
- 日別標本は母集団全期間の実レース充足率を証明しない。`snapshot_at`時刻が締切前でも**当時初回取得・モデル判断時点の証明にならない**。学習候補の型チェックと実ROI可否は別gate。
- 前回10/20の`historical`限定監査が0だったのは保存先ラベルの問題。既存原本の大規模再取得・上書きは不要とみなし、まず統合を優先。

## 開発を速める集約実行計画（既存収集を止めずに段階実施）
1. **探す作業は停止**：上表を固定マップとし、旧チャット検索を日常工程から外す。個別の障害だけ原本元・保存期間を再点検。これまでのV5研究コードは再利用、合成18/18 PASS。
2. **既存VIEWでV5予測入力アダプタを先行実装**：6艇・K履歴・展示・oddsを同一snapshotで結合。特徴量は既存の前日確定13Counter/5因子研究コードを使う。履歴展示は「学習再構成のみ」・forward観測は実first-capture未認証のHOLDで明確に分類。再実装やコピー完成待ちで予測本体開発を止めない。
3. **物理stage移行は1表ずつ手動調査の無限ループを廃止**。既存`docs/V5_COPY_FIRST_CUTOVER_20261022.md`、`docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json`、`deploy/conoha/v5_copy_first_preflight_readonly_20261022.sql`を再利用し、**複数表を一度のバッチ計画で容量・key・schema/索引・writerの可否を評価**。優先：レース/出走/前日K結果/直前展示/オッズ/出走snapshot、その後その他とarchive。既存venues stage再コピー禁止。
4. **安全なオンラインstage（別途実行承認）**：新規専用実表へ小チャンクでコピー、コピー中も旧writer/収集稼働。ソース別主キー/UNIQUE、NULL、default/sequence、FK・trigger・grantを個別保持。回収時刻/生原本情報を失わず、insert/update/delete差分追跡。COPYに伴うWAL/容量/負荷を制限し、row/内容パリティ監査。保存元は残す。
5. **切替は単一夜間窓・別途明示承認**：独立バックアップと復元試験、全writer経路+rollback証明、欠損/後続結果PENDING=0、timer/サービス停止と再開、全13対象の差分追込・atomic route切替・nonbuy canaryをすべて確認。満たさなければ切替せず既存収集継続。手順の提案は深夜自動切替の予約ではない。
6. **終了後**：V5本体+共有正本をV3/V4と別のDriveに定期暗号化保全する。403解消と独立復元確認まではバックアップ完了と呼ばない。旧正本を削除するのは長期検証＋別承認後。

## 2026-10-24 GitHubで集約作業を短縮する準備
- `deploy/conoha/v5_stage_13_batch_gate_readonly_20261024.sql`を追加。既存12表preflightの欠けていた選手コース統計を含め**共有13種類を1度に**メタデータ点検。ソーステーブルサイズ/実体/UNIQUE/FK/trigger、V5物理候補、venues隔離stageを一括出力する。実コピー・稼働切替なし。
- 表ごとの物理正本移管先は「V5向け候補」であり確定運用経路ではない。`v5_data.venues`と`boat_data_stage.venues`など既設の名前/重複保全を精査し、**既存のstagingを自動再作成しない**。
- 安全化を作業の最後へ放置するのでなく、**一括で準備 → コンパクトに承認 → 旧収集継続中に低負荷分割stage → 一括差分検証 → 承認済み切替**の順で進める。

## 17:55 13系統バッチgate PASS、短時間停止＋補完方針
- Termius画面で13行、`railway`容量3479MB、`boat_data_stage.venues`は実表(r)、`boat_data.venues`はVIEW(v)、READ ONLY/ROLLBACK、`V5_13_SOURCE_BATCH_GATE_READONLY_DONE_NO_COPY`確認。見えている一部`v5_data.raw_*`はABSENT。**新V5物理targetの一括作成・COPY・本番切替はまだ実施していない**。
- ユーザー方針：**短い計画停止はやむを得ない。停止中の欠落は元資料から回収できる種類なら後日補完**。GitHubに`docs/V5_SHORT_MAINTENANCE_AND_RECOVERY_FASTPATH_20261024.md`作成。多数表を事前オンライン低負荷stage後、最終差分の短時間のみ全関連writer/timers/child workerを限定停止。予め安全復旧・欠落補完・復元可否を確認する。
- **ただし展示・刻々変化するオッズ・風水面などは後日同一時点の原本が再取得できない場合がある**。正確に復元できないものは`UNKNOWN_AT_DECISION`としてHOLD。後取得は`RETROSPECTIVE_BACKFILL`、本物の締切前に観測された予測証拠と混ぜない。
- 本日の停止・既存サービス無断操作・VIEW切替・物理コピーの実行承認はまだない。現行収集を維持しつつ停止計画の確認を先行。
## 2026-10-24 18:41 一括準備の合格とオフラインstageバッチプラン
- Termius`/var/backups/v5_prepare_wLz5IWY7`で13manifest・DB/read-only・writer監査・disk/backupの一括レポート作成成功。`PRODUCTION_CUTOVER=NO_GO`、`NIGHT_AUTOMATION=NOT_ARMED`で現行収集無変更。
- GitHub`v5/offline_stage_batch_plan.py`: 原本固定mapに対し、既存venues stage 1件は保護、波1六件（レース/出走/結果/K/公式オッズ/展示）、波2六件（コース統計/直前出走/オッズ/気象/条件/選手条件）の純粋オフライン計画。決してDBへ接続しない。
- `tests/test_v5_offline_stage_batch_plan.py`の5ケースを追加したがテスト実行結果は未取得。モデル前向き予測と物理コピー完成は別のgate。独立外部復元・writer/CDC差分/自動切戻しは未証明。
## 18:50 合成テスト5/5 PASS／13表schema-key一括gate
- `v5/offline_stage_batch_plan.py`の`tests/test_v5_offline_stage_batch_plan.py`をTermius隔離実行で5/5 `OK`。従来研究18/18と累計23/23合成PASS。移行用DB書込はまだ行っていない。
- GitHubに`deploy/conoha/v5_stage_13_key_schema_gate_readonly_20261024.sql`追加、13ソースのPK/unique/NULL/default/sequence/FK/triggerを一括メタ読取。オンライン分割COPY時の`id`・`nextval`の誤配線・更新/削除差分の不一致を防ぐための境界。
- 本番への一括stage作成やCOPY、後続差分＋rollbackは**未実装**、独立バックアップ復元未証明。現行収集維持、stage1/13、本番0/13、03:30 timer未予約。
## 18:56 13系統のPK/sequence/fk metadata監査
- Termius`V5_STAGE_13_KEY_SCHEMA_READ_ONLY_NO_COPY`, 13 rows, ROLLBACK。更新追従用のキーは`id`/複合`(race_id,lane)`等混在、複数の`nextval` defaultあり。`CREATE TABLE LIKE INCLUDING ALL`のdefaultを無条件共有しない。
- 以前から`deploy/conoha/boat_shared_staging_delta_plan_offline.py`に全主キー整列ハッシュ差分（insert/update/delete）計画コードが存在。**使い回す**。`boat_data_stage.<view>`と提案`v5_data.raw_*`の宛先不一致を修正しないまま実SQLを実行しない。
- `v5/offline_stage_chunk_copy_sql.py`はオンライン分割COPYのためのオフラインSQL生成器、実行不可・PK/スキーマ証拠が揃わなければ拒否。`tests/test_v5_offline_stage_chunk_copy_sql.py`6件は未実行。運用RUNNER／本物のCOPYは未完了。

## 2026-10-25 08:21 JST 実機catalog確認
- 2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

## 2026-10-25 08:40 JST venues stage一致
- 2026-10-25 08:40 JST: ConoHa Termiusでvenues source/stage各24、`VENUES_STAGE_DELTA_TRANSACTION_PASS upserted=24 deleted=0 bidirectional_equal_in_transaction=YES legacy_source_untouched=YES live_view_untouched=YES continuous_cdc=NO cutover=NO_GO BUY=OFF`、`VENUES_STAGE_ONLY_DELTA_COMMITTED_NOT_CDC_NOT_LIVE`確認。**venues stage差分反映・同一snapshot照合成功**。元public/VIEW unchanged。初回物理stage13/13、live物理切替0/13。
- 12表向けキー範囲stage同期コードはGitHub登録済み、実同期は未実施。13全体の更新差分完了とは呼ばない。

## 2026-10-25 08:51 races stage差分反映
- 2026-10-25 08:51:38 JSTユーザーのConoHa画面で `races` stage差分反映が成功。`DELTA_VERIFIED races source_rows=74064 stage_rows=74064 insert_update_delete=[168, 0, 0] bounded_windows=19`、`DELTA_TABLE_COMMITTED races`、`STAGE12_DELTA_SNAPSHOT_PASS families=1`、旧原本/VIEW不変更・BUY OFF・CDC=NOを確認。初回コピー13/13、stage差分反映2/13（venues+races）、本番物理切替0/13。
- 残11差分の03:05一度限りステージ専用予約installer準備済み。現時点VPS未予約。旧原本維持。

### Next ONE task
**Next ONE task:** 2026-10-25 JST中にTermius rootから `deploy/conoha/v5_stage11_delta_schedule_once_20261025.sh`（commit `227d3c30c3921bccb5957abb7933468a7e5bc23f`）を1回実行し、`PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED` / `Next=2026-10-26 03:05 JST`を確認する。**実VPSへの予約は未適用、残11の差分は未反映**。予約成功後10/26深夜に残11系統をsource size昇順・表ごとのrepeatable-readトランザクションで同期・INSERT/UPDATE/DELETE/Pk/内容照合。失敗時その表のみrollback、旧collector・13 live VIEW・public原本は変えない。完了は翌日journalで系統ごとに確認し、CDC/独立復元/route切替は引き続きNO-GO、BUY OFF。
