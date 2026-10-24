# 新競艇AI No.2 — CURRENT compact handoff（2026-10-23 16:22 JST）
本ファイルが唯一のcurrent運用要約。古いLIVE_HANDOFF/PROJECT_HISTORY/長いworkflowは通常参照しない。次の1作業に必要なSHA・日時・件数はliveで確認し、タイムアウト回避のため1回1作業。

## 目標・制約
- 主力はConoHa上のV5実3連単予測。基本履歴は2025-07以降、事前as-of証拠に基づくwalk-forward/バックテスト→非購入運用→実予測。将来V6も同じ元データを参照。目標月純利益+5万円・1日1〜3Rまたは見送りは**未検証**。自動購入は最後に別承認、現時点BUY OFF。
- **ユーザー優先事項：分散した元データ保存先をV5/V6共通基盤へ統一し、現行収集を失わず段階的に物理移行**。モデルの精度を悪化させる特徴は採用しないが原本収集は継続。未確認の展示/事故/返還/初回取得時点はHOLD。既存サービスや設定を変更する場合は明示承認。
- ConoHa低費用・低CPU/RAM/通信を維持、Railway Agent/AI使用禁止。Railway Hobbyは10/23解約、11/03終了予定。複数GBのblind COPY、不要な新DB/課金、旧データ削除は禁止。

## 現在のDBと共有化方式
- GitHub `kenshoushouri-cloud/boat-ai-v2`、ConoHaコード`/opt/boat-ai-v5`、PostgreSQL DB`railway`。
- **共通正本の最終設計**：`railway.boat_data`内の13物理テーブルをV5/V6で共有。現在は**13個の非更新VIEW**のみ（旧`public.v2_*`物理テーブルに依存）。10/23 06:45 13/13 read-only gate PASS。稼働writer/readerはlegacyのまま、**データの実移動は未完了**。`v5_data.venues`は旧venue24件コピー（EXCEPT ALL差分0）のステージで本番正本ではない。`boat_data.venues`はVIEWなので`shared_venues_v1`の書込みrouting有効化禁止。
- 別DB`boat_history_archive`実表3件約1,069MBは別正本として保持し、将来共通read-only adapterで参照。無理にrailwayへ再コピーしない。`v5_research`/将来`v6_research`にはモデル固有出力を分離。PostgreSQLスキーマはOS上の物理共有フォルダではない。
- 詳細設計：`docs/BOAT_SHARED_DATA_PLATFORM_20261022.md`。**絶対実行禁止**：`deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh`及び`boat_shared_bulk_stage_20261023.py --apply`（VIEW13件と衝突）。DROP/ALTER SET SCHEMA/大容量COPY/旧ルート切替はバックアップ＋復元＋全writer判定＋明示承認が必要。

## 10/23 実測（ユーザーTermius画像、実作業のみ）
- 16:22 `deploy/conoha/boat_common_physical_inventory_readonly_20261023.sql`が**COMMIT／監査正常終了**。13の旧物理表→13の共通非更新VIEW、全て`SOURCE_PHYSICAL_CANONICAL_READ_VIEW_ONLY`。物理容量の例：旧realtime odds651MB、racer_results247MB、weather188MB、exhibition135MB、entry33MB（画面に表示された値、固定値ではない）。その他は旧表。研究用`v2_exhibition_shadow_*`・ST・Bao及び隔離`v4_exhibition_quarantine_20261017`（22MB）は**正本へ自動統合しない**。ステージ`v5_data.venues`48KB。カタログ監査はCOPY/writer変更していない。
- 16:16 別保存先の限定検査：10/10,15,17,18,19の旧`public.v2_exhibition`も0件。10/01と10/05は各`final_ab`/`learning_all`ラベルで完全6艇162/127レース（同じレースを二重集計しない）。展示関連物理表は複数だがraw元時点と用途は別監査。
- 16代表日：2025-07/10、2026-01/04/07/09、10/01,05はhistorical等の展示6艇多数。10/10,15,17,18,19は共通VIEW内0、10/20=29/144、10/21=129/156、10/22=150/168。**別テーブルや別DBまで全期間欠落とは断定不可**。後日のhistorical/可変`snapshot_at`は締切前初回取得の証拠でない。
- 10/18,19,20の3日で432レース・K正常履歴候補399、展示6艇29、両方27（10/20のみ）。10/20全144/出走6=144/K正常6=132/展示6=29/共通候補27。公式K特殊着順12R／14艇のうち進入欠損3艇。結果`official`でも事故/返還ゼロの独立証明は**ない**。
- 13系統Counter（27fit形状候補＋132K履歴形状候補）構造総数・非ゼロセル検査済み。合成数学/日次チェーンのオフライン回帰最大22/22 PASS（個々のフローはIssue #581）。**本番モデル学習・原本証明・真正なforward ROI・BUYは未実装/未認証、HOLD継続**。

## 10/23 16:29 稼働writer監査と深夜自動移行のユーザー提案
- Termiusの`v5_active_writer_routes_readonly_20261022.py`正常終了（`V5_ACTIVE_WRITER_ROUTES_READONLY_COMPLETE_NO_DB_WRITES`）。forward子`v5.conoha_realtime_window_pg → v21_realtime_collector_pg_safe.py → v21_realtime_collector_pg.py`と日次/K/補完/DDLへの旧表参照の存在を確認。ただし`NO_RUNTIME_WRITE_PATH_CERTIFICATION_YET`＝**全writer経路の保証なし**。共通側13は非更新VIEWで物理正本でない。
- ユーザー案「稼働中に複製→深夜に自動切替」は**設計上可能で推奨**。ただし時刻固定でGOにしない：23:00/01:20等の収集、UPDATE/DELETE差分、最新外部バックアップ+復元、13writer/reader/DDL統一・短期静止・非購入canary・ロールバックが**全部検証済み**の場合だけ条件付きGO。未達なら**旧収集を維持しNO-GO/延期**。現時点は**GO不可能、予約も未実施**。`docs/BOAT_SHARED_UNATTENDED_CUTOVER_PLAN_20261023.md`をGitHub追加。既存`boat_shared_bulk_*20261023`はVIEW13件と衝突し実行禁止。

## 10/23 共有13元表の機械可読経路管理表（GitHub準備）
- `docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json`追加。**13対すべて**（master1/core2/result2/odds1/feature1/realtime6）の`public.v2_*`旧物理→`boat_data.*`非更新VIEW、コード上の候補writer/reader/DDL、朝夜・5分forward・深夜catchup・K補完・選手コース履歴・DDL候補、モデル固有/時点証拠のHOLDを機械可読に記載。JSONを再読し13件/重複なし/全件NO-GOを確認。**コード上の候補であり稼働writer完全証明ではない**。
- Googleドライブ旧バックアップはユーザー申告（実ファイルの世代・復元性未照合）。整理中の全量上書きは避け古い世代を保持するが、実物理切替前には当日差分を含む独立の新世代バックアップ・復元試験が必須。
- `cutover_ready=false`, `unattended_cutover_scheduled=false`; 本ターンConoHa/Google Drive実体/cron/DBに変更なし。

## 収集・移行の安全条件
- 現行ConoHaのmorning07:00/night23:00、forward毎5分（期限9〜24分）、midnight catchup01:20等のtimer/子processを停止しない。oneshot inactiveやflockコード75だけでは故障とは限らない。旧writerを片方だけ切替するとsplit-brain・差分漏れの危険。固定時刻になっただけで停止しない。
- ユーザー申告ではGoogleドライブに以前のバックアップあり（**内容・復元可能性は未検証**）。**整理途中の全量バックアップを何度も上書きせず、古い世代は保持**。整理・共通化を終えた段階で新しい世代を保存する。ただし10/19以降の展示・オッズ等は旧世代だけでは守れないため、**物理切替の直前までに、当日変更分を含む整合した別世代バックアップと限定復元試験を必須**とする。バックアップが未準備なら深夜切替はNO-GO/延期。新世代の復元・照合までは古いGoogle Drive世代を上書き/削除しない。全writer/reader・最終delta・ロールバックも必須。旧表削除は別承認。
- 移行は13ソースの書込責任者/読み込み依存を洗い出し、まずvenues24件pilotでroute/read/rollback検証、大きなオッズ/展示は容量/WALとlive追記を見積もって表単位で段階切替。データ欠損を補完したことと当時のforward証拠を再現したことを混同しない。
- `v5_daily_table_routes.py`や`v5_realtime_table_routes.py`にopt-in案があっても、**現行共通VIEWへINSERTできず、全子ジョブ対応の保証もない**。既存flagsはlegacyから変更禁止。

## 10/23 Google Driveバックアップ実体の読取確認
- **2つの接続済みGoogleドライブ**を直接フォルダ一覧（検索のみでは一部非表示）で検査し、**実ファイル8件**確認：10/19メイン`main_current_20261019.dump.age` 297756932 bytes がA/B双方、10/18メイン297740778、10/19履歴`archive_current_20261019.dump.age` 52130144、10/16名履歴52125309、V3のdump/ZIP・V4 dump。詳細`docs/BOAT_GDRIVE_BACKUP_METADATA_20261023.md`。**存在のみ検証**、暗号解除/pg_restore/復元/ハッシュ/中身/10/19以降の差分は未検証。旧世代を上書き/削除しない。

## V5専用・旧V3/V4とは別ドライブへの定期バックアップ方針
- 毎日の自動保全対象は**稼働V5本体/ローカル設定・モデル状態、共有データの実物理原本、V5で必要な別DB履歴`boat_history_archive`、予測・学習・監査の復旧必須分**に限定する。移行前は`boat_data`13件がVIEWなので旧`public.v2_*`実表も含める。V3/V4旧システム・不要な研究shadowは自動対象外だが、V5に必要な唯一の原本が残っていないか除外前に監査。
- 保存先は既存2アカウントのうち**V5用Googleドライブ側（B）に新しい定期バックアップ専用フォルダ**を設ける方針。旧V3/V4は別アカウント（A）側で世代維持。今ある暗号化8ファイルと鍵復旧資産は削除/移動/上書きしない。`v5_gdrive:`は過去の接続名のため、実運用前に生きた接続・空き容量を確認。詳細`docs/BOAT_SHARED_BACKUP_POLICY_20261023.md`。
- 開発・データ移行を優先し、初回DB変更前にConoHaローカルで新世代の保護用バックアップと復元試験。深夜切替前には同一VPS障害にも耐える独立保全と差分整合が必須。整理済みの自動Drive暗号化バックアップは移行後に別承認で設定、現時点は**未予約・未実行**。

## 10/23 共有13テーブルの安全な物理移行コード準備
- GitHub `deploy/conoha/boat_shared_staging_delta_plan_offline.py`新規。13旧物理表/現行13非更新VIEWの厳密マッピングを読み、VIEWに衝突しない**`boat_data_stage.*`の複製先計画**を生成（**17:47時点では未作成**。19:50にvenues1表だけ作成済み。後掲最新状態を優先）。`v5_data.venues`の既存24行ステージは変更なし。
- 全件PK昇順・全列digestの2入力からINSERT/UPDATE/DELETEの**差分計画候補**をストリーム検出する関数を実装。日時watermarkだけで削除を見落とさないための仕様であり、**CDCも実SQL同期も実装・実行していない**。13の現行コード候補とGO/NO-GOを分離、証拠がない限りNO-GO。
- `tests/test_boat_shared_staging_delta_plan_offline.py`に8件の単体試験を新規追加。さらに`deploy/conoha/boat_shared_staging_offline_test_once_20261023.sh`で`origin/main`から必要4ファイルだけを隔離`/tmp`へ取得し、**ConoHaの現行worktreeを変更しない**単体試験を1回実施できるよう用意。GitHub作成とreadbackは確認済、**当初未確認だったが10/23 17:47 ConoHa 8/8 PASS、19:28 venues個別7/7 PASSを確認済み**。現行収集・DB/Drive・BUY・timerは変更していない。

## 10/23 17:47 JST オフラインステージ検査（実証済み）
- ユーザーTermiusスクリーンショット：`deploy/conoha/boat_shared_staging_offline_test_once_20261023.sh`実行、`ISOLATED_OFFLINE_STAGE_TESTS_BEGIN`、**8 tests / 0.002s / OK**、`OFFLINE_STAGE_AND_COMPLETE_KEY_DELTA_TESTS_PASS_NO_DB_NO_BUY`、rootシェル復帰。GitHubから必要ファイルのみisolated取込のオフライン試験。13のVIEWと衝突しないstaging計画、PK完全キーのINSERT/UPDATE/DELETE差分計画、未検証時のNO-GOが**合成ケースでPASS**。
- **17:47時点で未実施だったもの**：ConoHa DBのstage/venues物理複製、差分適用/CDC、バックアップ復元、夜間切替予約、V5実予想・BUY。**stageと限定復元のみ19:50までに完了**（最新状態は後掲）。旧`public.v2_*` writer収集継続。合成試験を実DBの正確さや準備完了とは扱わない。
- バックアップ合意：初の物理DB変更前はConoHaローカルの新世代＋復元試験。深夜本番切替前はVPS障害にも耐える独立保全が必須。整理後の自動Drive保存はV5本体・共通原本・必要な履歴/設定/モデルのみに限定し、V3/V4は別アカウント側に旧世代を保持。未設定。

## 10/23 19:52 JST 更新：venues初回物理複製完了（ユーザーTermius画像）
- GitHub `deploy/conoha/boat_shared_venues_pilot_offline_20261023.py`追加。隔離取得して**個別オフライン7/7 PASS**（`VENUES_OFFLINE_GATES_PASS_NO_DB_NO_COPY_NO_BUY`）。共有13表の既存合成テスト**8/8 PASS**も維持。これらは実DB同期の証明ではない。
- ConoHa容量：/ 99GB中使用28GB/空き67GB（19:29観測）。DB `railway` 3464MB、別DB `boat_history_archive` 1069MB（19:30観測）。
- ConoHa内 **railway単独** 新世代`/var/backups/boat-railway-20261023-*/railway.dump` 375MB（19:32）。**venuesのアーカイブ取り出しPASS**、隔離テストDBへ**venues24件を限定復元PASS**、後の残存一時DB=0。**railway全体/別DB履歴の復元試験ではない**。このバックアップはstage作成前の世代。Drive独立新世代や定期自動化は未実施。
- 19:39 read-only：`public.v2_venues`物理表(r)24件、`boat_data.venues`既存VIEW(v)、`v5_data.venues`旧物理stage(r)24件、作成前`boat_data_stage.venues`なし。原本vs旧stageは**全24行updated_atのみ差**（旧stageは10/22、原本は10/23朝更新）。venue_code PK、6列・制約・unique venue_id等の基本監査済み。旧原本の外部キー依存=0、VIEW依存`boat_data.venues`。全実行writer経路/権限継承/ロールバック保証は依然未認証。
- **19:50 ユーザー明示承認後 ConoHa本番DB `railway`内に新規`boat_data_stage` schema＋`boat_data_stage.venues`物理表をCREATEし、旧原本から24行INSERT、全列EXCEPT ALL両方向0、unique index2件確認後COMMIT。** マーカー`VENUES_STAGE_24_COPY_AND_PARITY_PASS_NO_CUTOVER`。旧`public.v2_venues`・`v5_data.venues`・`boat_data.venues`VIEWは維持、collector/cron/BUY・route未変更。**このstageを再作成・再複製・DROPしてはいけない**。
- 19:51再監査：原本24/stage24/VIEW24、双方向全列差分0、stage物理(r)、owner postgres、PUBLIC権限REVOKE済（個別ロール権限は別確認要）。19:52 `REPEATABLE READ READ ONLY`全PK/JSONB比較で **SAME24、INSERT0/UPDATE0/DELETE0、ROLLBACK**。**一時点で差分0という意味**で、継続差分同期/CDC、writer完全監査、夜間自動切替は未実装・未承認。
- **重要：`boat_data`の13関係は依然すべて既存非更新VIEWであり、共通物理正本への本番切替完了数は0/13。** 隔離stageの初回複製だけ1/13。ConoHa稼働収集はlegacyのまま継続。差分追跡、外部独立バックアップ＋復元、全writer/readers/DDLゲート、非購入canaryが未確認の間は**NO-GO**。

## 10/23 19:52以降：GitHubのみvenues差分同期オフライン計画を追加
- 新規`deploy/conoha/boat_shared_venues_delta_plan_offline_20261023.py`：既存`plan_full_key_delta`再利用。venuesの全6列をSHA256で厳密比較（timestamptzはUTC正規化）し、全PKでINSERT/UPDATE/DELETEとSAMEを合成スナップショットから検出する**実SQL不含の計画のみ**。24件一斉`updated_at`更新、追加/更新/削除同時、全列差、時差表現、重複PK/uniqueID、欠落列、不完全snapshot、取得トークン不一致、誤ったVIEW route、空ソース時の大量削除防止など**17単体試験を定義**。
- マーカー`VENUES_FULL_KEY_DELTA_OFFLINE_TESTS_PASS_NO_DB_NO_BUY`は**Python実行時に17/17 PASSした場合のみ出る**。GitHub保存/readbackと静的検査はPASS、**10/23 20:01 JST、ユーザーTermius画像で17 tests / 0.011s / OK + 成功マーカーを確認済み**。scriptにはDB接続・DML・DDL・予約処理なし、証拠が揃っても`decision=NO_GO`。
- 共有マニフェスト`docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json`に`isolated_staging_progress.venues`追記：初回24行複製済・point-in-time差分0、二重COPY禁止、canon `boat_data`物理切替0/13、全writer未証明。旧`tables[].physical_copy_completed=false`は本番物理正本切替未完了を示す（stage複製済みとは区別）。既存13 route gateは変更せず。
- ConoHa DBと既存worktree、collector、Drive、cron、BUYには今のGitHub作業で変更なし。

## 10/23 20:01 JST：venuesフルキー差分オフライン17/17 PASS
- ユーザーTermiusスクリーンショットで`Ran 17 tests in 0.011s`、`OK`、`VENUES_FULL_KEY_DELTA_OFFLINE_TESTS_PASS_NO_DB_NO_BUY`、rootプロンプト復帰を確認。隔離`/tmp`でGitHubの必要3ファイルを実行し、**ConoHa本番DB/既存stage/収集/BUY変更なし**。合成データ上の全PK・全列 INSERT/UPDATE/DELETE検出と不完全入力NO-GOを確認。**自動差分同期・CDC・本番書込・夜間切替は一切実施/認証していない**。19:52の実DB差分0は一時点の結果のみ。
- 既存`boat_data_stage.venues`24件は再CREATE・再COPY・DROP禁止。共通物理正本への切替依然0/13。旧原本収集継続。ConoHaローカル旧世代dumpを保持。独立保全・全writer証明・非購入canary・切替承認未完了。

## 10/23 20:01以降：GitHub上のvenues現行writerルート一次監査（静的・実行変更なし）
- `repair_month_all_pg.py` 1317-1319 `main()`で`ensure_venues()`を呼ぶ。312-325で24会場`venue_code=venue_id`、`updated_at=_now_iso()`を作り、`upsert_rows("v2_venues", rows, "venue_id")`。既存原本vs旧stageの毎朝24件timestamp差と整合的だが、**稼働実トレースの証明ではない**。
- 同ファイル287-307の`upsert_rows`は`v5_daily_table_routes.resolve_table`経由で`db_pg.upsert_rows`へ。後者は`ON CONFLICT (venue_id) DO UPDATE`（競合キー以外の送信列を更新）として動く。**物理PKはvenue_codeでありUNIQUE venue_idと両方保護必要**。入力にないcreated_atは維持する。更新日時のみの差分も完全列照合でUPDATE候補扱い。
- `v5_daily_table_routes.py`は既定`legacy`、opt-in二重/三重gate。**`shared_venues_v1`は現在非更新VIEWの`boat_data.venues`に向けるため、有効化禁止**。既存`v5_data.venues`向けprofileも今回作成した`boat_data_stage.venues`の安全同期手段ではない。`db_pg.py`の許可済みスキーマ名に`boat_data_stage.venues`はなく、writer切替・DB処理は未実装/未承認。
- ConoHaにはこのGitHub読取で一切操作なし。現行稼働writer完全認証・複数子ジョブ・DDL・readers網羅は未完了。旧収集継続、stage初回24件は再コピー禁止。

## 10/23：venues安全な差分反映プロトコルをGitHub設計（新しいConoHa操作なし）
- `docs/BOAT_VENUES_DELTA_APPLY_SAFETY_PROTOCOL_20261023.md`を追加し、GitHub readback/静的12確認PASS。**設計のみでSQL/DML・CLI・DB実行・cronは新規なし**。
- 現行`repair_month_all_pg.py`の`ON CONFLICT(venue_id)` UNIQUEと原本PK `venue_code`の違い、全6列・全PK・同一スナップショット、UPDATE/INSERT/DELETE（不完全原本からの誤DELETE禁止）、書込み競合ロックの順序、単一writerと子ジョブ静止、失敗時ROLLBACK、異常な差分/UNIQUE衝突時NO-GO、外部独立バックアップ＋限定復元、非購入canary、別操作承認の各ゲートを記載。
- 19:50作成済の`boat_data_stage.venues`24行は**再作成/再COPY禁止**。物理正本切替0/13、共通VIEW13件そのまま。ConoHa本番DBへの反映や実際の静止/rollback試験は**未実施**、既存収集維持。

## 10/23 20:01以降：venues差分反映fail-closed合成テストをGitHub追加
- `deploy/conoha/boat_venues_delta_apply_guard_offline_20261023.py`新規。**24件のPython unittestを定義**しGitHub保存/readback・静的13項目PASS。完全キー・同一スナップショット、独立backup復元、writer静止/子job認証、別承認、巨大/不明DELETE、venue_code PK/venue_id UNIQUEの衝突、試験用メモリ内の故障時ROLLBACKなどを保守的に判定。`production_decision=NO_GO`固定、DB接続/実SQL/cron/BUYなし。
- **10/23 21:17 JST、ユーザーTermius画像で24 tests / 0.004s / OK、成功マーカー、rootプロンプト復帰を確認（24/24 PASS）**。成功マーカー予定：`VENUES_DELTA_APPLY_FAIL_CLOSED_OFFLINE_PASS_NO_DB_NO_BUY`。GitHub上の静的検査とConoHa/Python実行を区別。
- ConoHa内で作成済`boat_data_stage.venues`24件には触れていない。原本とVIEWも維持、本番切替0/13、旧writer収集継続。リアルの独立バックアップ・全writer証明・stage差分適用/rollback演習は未実施。

## 10/23 21:17 JST venues fail-closed合成24/24 PASS（実証）
- ユーザーTermius画像：隔離`/tmp`で`boat_venues_delta_apply_guard_offline_20261023.py --self-test`実行、`Ran 24 tests in 0.004s`、`OK`、`VENUES_DELTA_APPLY_FAIL_CLOSED_OFFLINE_PASS_NO_DB_NO_BUY`。過去の8/8、7/7、17/17と合わせ**合成検査累計56/56 PASS（異なる検査群）**。**本番DB上の同期・ロック・ROLLBACKを実証したわけではない**。
- `boat_data_stage.venues`は19:50の初回24件複製済みで再コピー禁止。現時点で物理正本切替0/13、実CDC/同期DML/BUY/cron/無人切替未実施。ローカル`railway`dumpのvenues限定復元のみPASS、VPS外独立保全や全writer経路確認は未完了。

## 10/23 21:19 JST venues実DB最新差分read-only確認（ユーザーTermius画像）
- `BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`、statement_timeout=10秒、原本`public.v2_venues`と隔離物理stage`boat_data_stage.venues`のフルキー/全列JSONB比較、`boat_data.venues`relkind=**v**。**source_rows=24、stage_rows=24、SAME=24、INSERT=0、UPDATE=0、DELETE=0**、`ROLLBACK`正常終了、rootシェル復帰。
- **一時点の差分ゼロ**であり連続同期/CDC/実DML/本番切替の成功ではない。19:50に作成済みのstageを再CREATE・再COPYしない。現行収集writerは旧原本、`boat_data`13件はVIEW、本番物理正本切替0/13、独立外部保全・writer全経路保証は未完了。

## 10/23 21:22–21:30 JST：ConoHa V5の4タイマー・実行先の静的確認
- Termius画面にてsystemd 22 timersのうち`boat-v5-forward-window.timer`, `boat-v5-daily@morning.timer`, `boat-v5-daily@night.timer`, `boat-v5-midnight-catchup.timer`を確認。朝夜は`/opt/boat-ai-collector/daily_v5_safe.sh`→`/opt/boat-ai-v5/repair_month_all_pg.py`を参照。forward/midnightサービスには`flock`・`timeout`・venv Pythonが設定され、`systemctl show ExecStart`で`-m v5.conoha_realtime_window_pg`, `-m v5.conoha_midnight_results_pg`をConoHa live設定として確認。
- GitHub現行source静的調査：`v5/conoha_realtime_window_pg.py`は子`v21_realtime_collector_pg_safe.py`をsubprocess起動する候補。`v5/conoha_midnight_results_pg.py`は`repair_month_all_pg`の`_fetch/parse_result/upsert_rows`を利用し`v2_results`へupsertする候補。**GitHub sourceはConoHa稼働コード実体の完全照合ではない**。実ファイルと全子ジョブ・writer宛先のruntime確認は継続課題。
- 旧writer継続、共有`boat_data`13個はVIEW、本番物理正本切替0/13。stage`boat_data_stage.venues`24件再COPY禁止。深夜補完timerはデータ補完であり物理切替予約ではない。

## 10/23 21:35 JST：ConoHa子処理の実ファイル照合・GitHub依存追跡
- Termius画面：`/opt/boat-ai-v5/v5/conoha_realtime_window_pg.py` 125行付近で`v21_realtime_collector_pg_safe.py`を起動、`/opt/boat-ai-v5/v5/conoha_midnight_results_pg.py` 90/107行付近で`repair_month_all_pg`からimportし`v2_results` UPSERTすることを確認。**GitHubの経路候補とConoHaのlive fileはこの接続点で一致**。起動成功や全write経路・子プロセス群の完全証明ではない。
- GitHubの`v21_realtime_collector_pg_safe.py`は`v21_realtime_collector_pg.py`をimportして子処理を再利用。`_ensure_realtime_tables`は旧表のDDL許可ガード付きで`v2_realtime_weather/exhibition/entry/odds/race_condition/racer_condition_snapshots`6系統のCREATE/ALTER/INDEX候補と`legacy_entry_alters()`を持ち、`_upsert`は`resolve_realtime_table`を経由。**ConoHa実ファイルの全内容と実行分岐は次にread-onlyで確認**。現行`boat_data`13VIEW、物理正本切替0/13、既存stage24件保全。旧収集とtimerは無変更。

## 10/23 21:39 JST：リアルタイムcollector現物の旧6系統・DDL経路read-only照合
- Termius実ファイル`/opt/boat-ai-v5/v21_realtime_collector_pg.py`から旧6テーブル：`v2_realtime_{weather,exhibition,entry,odds,race_condition,racer_condition}_snapshots`が全て確認できた。`_ensure_realtime_tables`（102行）、`legacy_entry_alters`、`CREATE TABLE IF NOT EXISTS`（113行）、`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`（123行）、6 UNIQUE index（128～133行）、`_upsert`（135～138行）から`resolve_realtime_table`を呼ぶ経路を確認。**コード存在の証拠でありDDL実行証拠ではない**。ConoHa収集・タイマーは変更していない。
- GitHub `v5_realtime_table_routes.py`は既定legacy、physicalは明示2ゲート。**GitHub `v5_legacy_ddl_guard.py`の`forbid_legacy_realtime_if_physical_exists`は`to_regclass`が任意の対象を返すとlegacy DDLを拒否するため、対象が非更新VIEWでも拒否される可能性がある**（relkind判定なし）。ConoHa現物コードの適用状態・対象6名のlive relkindは未確認。writer正常動作/不動作も未証明。移行に先立ちこの疑義をread-onlyで切り分ける。
- 既存stage `boat_data_stage.venues`24件保持。13 VIEW維持・物理正本切替0/13・BUY/自動同期なし。

## 10/23 21:46 JST：ConoHa旧DDLガード候補先6表のlive relkind検査
- ユーザーTermius画像：`railway`で`BEGIN READ ONLY`、`v5_data.raw_{weather,exhibition,entry,odds,race_condition,racer_condition}_snapshots`は全6件とも`absent`（`pg_class`上未作成）、`ROLLBACK`で終了。**現時点でこれら6対象に存在するVIEW/物理表による`forbid_legacy_realtime_if_physical_exists`の誤停止条件は確認されない**。ただし稼働collectorの実行成否は未証明、今後`v5_data.raw_*`名でstage作成するとDDLガードが拒否する設計。改変前に別隔離stage命名/切替計画を確定する。
- 旧`public.v2_realtime_*`が全て物理原本であるか、収集実動作・他writer・全reader/DDLの監査は引き続き未完了。**既存`boat_data_stage.venues`24行保持、二重COPY禁止、物理正本切替0/13**。

## 10/23 21:49 JST：ConoHaの旧リアルタイム原本6表確認
- Termius画像で`public.v2_realtime_{entry,exhibition,odds,race_condition,racer_condition,weather}_snapshots`が**すべてrelkind=r（物理表）**、読み取り専用クエリ`ROLLBACK`正常終了。21:46時点の`v5_data.raw_*_snapshots`6候補は全て`absent`。
- 現行collectorはlegacy物理原本を使う設計。**既存DDL guardは`v5_data.raw_*`名を作るとlegacy収集を遮断し得るためその名前で無断CREATEしない**。別名の隔離stageは構造・容量・バックアップ・writer監査後に個別承認する。
- 既存`boat_data_stage.venues`24件を再コピーしない。13種類本番物理正本切替0/13。差分同期/深夜自動切替/BUYは未実施。

## 10/23 21:52 JST：旧リアルタイム原本6表の推定サイズをConoHa read-only確認
- Termius`railway`、`BEGIN READ ONLY`/`ROLLBACK`正常終了。`pg_total_relation_size`（インデックス・TOAST込）でodds 653MB（`reltuples`推定2,467,404件）、weather 188MB（85,725件）、exhibition 135MB（485,387件）、racer_condition 66MB（161,169件）、race_condition 58MB（26,229件）、entry 33MB（124,631件）。**合計約1,133MB / 推定約3,350,545行**。正確な件数ではなく統計値、実COUNTではない。変化する稼働DBの一時点の推定値。
- 段階的移行の候補は最小容量の`public.v2_realtime_entry_snapshots` (33MB) だが、**まだコピー承認なし、隔離stage未作成、実作業NO-GO**。653MB oddsを他5種とまとめて強制COPYせずCPU/RAM/WAL・旧writer稼働保護を優先。物理先`v5_data.raw_*`6名は全`absent`（21:46）でlegacy DDL guardに影響する可能性があるため未承認の作成禁止。既存`boat_data_stage.venues`24行は維持・再コピーしない。

## 10/23 21:55 JST：entry snapshots metadata部分監査（ユーザーTermius画面）
- `public.v2_realtime_entry_snapshots`について**21列**、PRIMARY KEY `id`、別UNIQUE index `(race_id,snapshot_label,lane)`、ユーザーtrigger 0件、`ROLLBACK`正常終了を確認。PKは自動採番ID、差分キー候補は3列UNIQUE。NULL制約や付随列・比較方式の証明はさらに必要。
- 画面が途中から始まるため`public`原本/ `boat_data.entry_snapshots` VIEW / `boat_data_stage.entry_snapshots`の**存在とrelkind結果・所有権/権限は未確認**。実データCOPYや自動同期は未承認。venuesの作成済stage24件には触れない。

## 10/23 23:03 JST：entry snapshot 3関係のConoHa read-only検査（Termius画像）
- `public.v2_realtime_entry_snapshots`は **relkind=r** owner postgres（ACL NULLの表示）、`boat_data.entry_snapshots`は **relkind=v** owner postgres（ACL postgres表示）、`boat_data_stage.entry_snapshots`は **absent**。queryは`BEGIN READ ONLY`、`ROLLBACK`正常、書込なし。
- 21:55確認分：旧entry21列、PRIMARY KEYは`id`、UNIQUEは`(race_id,snapshot_label,lane)`、user trigger0。6旧snapshot表の最小33MB/推定124631行という一時点の推定。**これらのキー構造はvenuesと異なる**。 `LIKE INCLUDING ALL`でserial/identity/defaultが旧原本のシーケンスを参照すると副作用の可能性があるため、別stage設計前にid defaultとowned sequenceを確認する。
- 既存`boat_data_stage.venues`24行はCOMMIT済で保全・再複製禁止。`boat_data`13個のVIEW保持、切替0/13、収集稼働中、独立外部保全・writer/readers完全監査・rollback未完成。**新しいentry stageのCREATE/COPYは未承認**。

## 10/23 23:05 JST：entry採番元をConoHa read-only確認
- `public.v2_realtime_entry_snapshots.id`はidentity指定なし（`attidentity`空欄）、default=`nextval('v2_realtime_entry_snapshots_id_seq'::regclass)`、owned sequence=`public.v2_realtime_entry_snapshots_id_seq`。ユーザーTermius画像で確認、`ROLLBACK`正常終了。
- **新`boat_data_stage.entry_snapshots`への単純`LIKE ... INCLUDING ALL`は旧sequence defaultを共有し得るため禁止。** 採番defaultを分離/削除する設計、既存IDの明示コピー、複製後整合と将来の採番衝突防止は別検証が必要。現時点でentryのCREATE/COPY・DMLは一切未承認・未実施。
- 既存venues24行のstageは保全・再コピー禁止。現行収集と13VIEWそのまま。本番物理正本切替0/13、独立保全・全writer証明未完了、NO-GO。

## 10/23 23:08 JST：entry snapshots default/FK最終read-only照合
- ユーザーTermius画像で`public.v2_realtime_entry_snapshots`の列DEFAULTは**idの`nextval('v2_realtime_entry_snapshots_id_seq'::regclass)`1件のみ**、その他のdefaultなし。該当表の流入・流出FK制約**0件**。`BEGIN READ ONLY`/`ROLLBACK`正常終了。21列、PK id、UNIQUE (race_id,snapshot_label,lane)、user trigger0、原本r/共有VIEW v/新`boat_data_stage.entry_snapshots` absentという前段結果と整合。
- 新規entry stageは**未作成・未承認**。`LIKE ... INCLUDING ALL`無修正は旧採番シーケンスを共有し得るため禁止。仮に全行を明示IDで複製しても独立採番や唯一キーのNULL安全性を別途検証するまで実COPYは禁止。
- ConoHa liveのcollector/cron/旧原本/既存venues stage24件に変更なし。独立外部保全・全writer audit・rollback不足で全13表の本番切替0/13、NO-GO。

## 10/23 23:10 JST：entry差分用3列UNIQUEのNULL安全性（ConoHa read-only）
- Termius画像で`public.v2_realtime_entry_snapshots`の`race_id`, `snapshot_label`, `lane`は**全てattnotnull=t**。3列のUNIQUE btree index `uq_v2_rt_entry_race_label_lane`存在。`indnullsnotdistinct=false`だが3列ともNOT NULLのためNULL重複問題は起きない。原本の安定した自然キー候補を`(race_id,snapshot_label,lane)`と確定できる（source/stage行のUPDATE/DELETE追跡は別途実データ証明が必要）。`BEGIN READ ONLY`/`ROLLBACK`正常終了。
- 旧原本21列、PK=id、旧SERIAL型採番default=`nextval('v2_realtime_entry_snapshots_id_seq'::regclass)`のみ、流入/流出FK0、user trigger0。新`boat_data_stage.entry_snapshots`はabsent。**`LIKE INCLUDING ALL`無修正による旧sequence共有は禁止**。独立stageは別承認まで未作成、ConoHa収集は旧物理原本に継続。
- 既存`boat_data_stage.venues`24件は保護、再コピーなし。共有13VIEW、本番正本切替0/13。独立バックアップ復元・全writer証明・差分実適用/rollbackは未完了。

## 10/23 23:10以降：GitHubのみ entry独立stage設計完了
- 新規`docs/BOAT_ENTRY_SNAPSHOTS_ISOLATED_STAGE_DESIGN_20261023.md`：旧`public.v2_realtime_entry_snapshots`21列、serial`id`の旧seqを継承しない`INCLUDING ALL EXCLUDING DEFAULTS`候補（実装・実SQL検証未実施）、PK idと自然キー`(race_id,snapshot_label,lane)`、独立stageへの明示id全列複製、一貫MVCC snapshot、原本収集継続中の追い付き/INSERT UPDATE DELETE、安全負荷/WAL、全行双方向照合・例外ROLLBACK、外部独立新世代backup+隔離復元と個別承認のゲートを設計。
- **E01～E12のfail-closedオフライン合成テストは検査項目として記載のみ**。Pythonテスト実装・実行・ConoHa DB DDL/DML・物理COPYは一切未実施。GitHubファイル保存/readbackと静的10確認PASS。`boat_data_stage.entry_snapshots`はabsent、venues24行stageは再COPY禁止、本番切替0/13。独立外部保全/全writer監査は未完了でNO-GO。

## 10/23 23:10以降：entry独立stage合成安全テストをGitHubに実装
- 新規`deploy/conoha/boat_entry_stage_guard_offline_20261023.py`に設計書E01～E12の純粋なPython unittest **12件を定義**。旧serial default/sequence依存、21列・PK/id/3列UNIQUE、不完全/混合スナップショット、INSERT/UPDATE/DELETE（時刻不変更新）、ID自然キー衝突/大量DELETE、途中失敗の仮想ROLLBACK、外部backup・writer認証・承認の不足をfail-closedで検査する設計。**合成上すべての証拠がTrueでもproduction_decision=NO_GO**。
- GitHub保存・再取得、定義12件と危険なDB/CLI import不在等の静的8確認PASS。**Python unittest実行はまだ未確認、12/12 PASSとは記録しない**。marker `ENTRY_STAGE_FAIL_CLOSED_OFFLINE_12_PASS_NO_DB_NO_BUY`はPython実行で全件PASSした場合のみ出力。
- `docs/BOAT_ENTRY_SNAPSHOTS_ISOLATED_STAGE_DESIGN_20261023.md`も実装済み・実行未確認と更新。ConoHa stage`boat_data_stage.entry_snapshots`は未作成、venues stage24行は再コピー禁止。旧collector/VIEW/backup不変更、本番正本切替0/13。

## 10/23 23:22 JST：entry guard E11合成rollback判定の誤りを修正（GitHubのみ）
- ユーザーTermius画像：隔離`/tmp`で12 unittestを実行、`Ran 12 tests in 0.025s`、**FAILED (failures=3)**。失敗はE11の`fail_after=1/13/24`の3 subTest。`original_source_unchanged`のassertがFalse（**12/12 PASSではない**）。他の11テストはエラー表示なし。
- GitHub現行コードを確認：`original=deepcopy(source.rows)`はtupleだが、成功・例外経路とも`original == list(source.rows)`で型不一致になりFalse。**旧原本データ変更や実DB rollback障害を示すログではなく、合成テストの型比較ミス**。
- `deploy/conoha/boat_entry_stage_guard_offline_20261023.py`の2か所を`original == source.rows`へ修正してGitHub commit、readback済み。12テスト残存・両箇所置換・DB client/SQL不使用・NO_GO維持の静的確認PASS。**修正後のPython 12件はまだ未実行、PASSと記録しない**。
- ConoHa stage`entry_snapshots`は未作成、venues24行はそのまま、旧原本・VIEW・収集・BUY・cronは変更なし。本番切替0/13。

## 10/23 23:24 JST：entry E01〜E12オフライン再検査12/12 PASS
- ユーザーTermius画面：修正版を新規隔離`/tmp/entry-retest-*`に`git fetch`＋`FETCH_HEAD`から一時的に取得、`python3 -B guard.py --self-test`を実行。`Ran 12 tests in 0.025s`、`OK`、`ENTRY_STAGE_FAIL_CLOSED_OFFLINE_12_PASS_NO_DB_NO_BUY`、rootプロンプト復帰を確認。**12件全PASS**。
- 同じ画面上部には23:22旧テストの`FAILED (failures=3)`も残っているが、後続の修正後テストが明確にPASS。E11のtuple/list比較バグ修正後の合成rollback判定OK。**実DBのrollback・stageのCREATE/COPY・CDC・実同期の成功を示すものではない**。
- 過去の合成8+7+17+24=56件と今回の12件で、実行確認済み合成テスト計**68/68**（別検査群、実本番保証とはしない）。entry stageは未作成、venues初回stage24件は維持・再COPY禁止、13VIEWの物理正本切替0/13。旧収集・タイマー・DB・シーケンス変更なし。外部独立保全/全writer完全監査/切替承認は未完了。

## 10/23 23:26 JST：ConoHa rclone remote登録名の確認
- ユーザーTermius画面：`rclone listremotes`に`drive:`、`gdrive_a_backup:`、`v5_gdrive:`の**3名**が表示。rcloneコマンド利用可能、シェルへ正常復帰。**V5専用バックアップ候補は名前上`v5_gdrive:`だが、Googleアカウント・ルート/保存先の独立性・リモート接続・バックアップの有無・外部独立復元は未確認**。
- 転送/更新/Driveファイル削除・旧バックアップ上書きやDB/collector変更なし。先ほどのentry E01～E12合成12/12 PASSは維持、物理stage entry=absent、venues=24件保全、本番切替0/13。

## 10/24 00:09 JST：V5 Google Drive API rate-limit（ユーザーTermius画面）
- `rclone lsd v5_gdrive: --retries 1 --low-level-retries 1`を1回実行したところ、**Google Drive API 403 Quota exceeded / RATE_LIMIT_EXCEEDED / Requests per minute / defaultPerMinutePerProject**でroot folder IDの参照に失敗、シェルに復帰。フォルダ一覧は**取得できず**、接続先の健全性・フォルダ独立性・復元/バックアップ有無は未確認。
- これは**Drive保存容量不足やroot ID破損の証明ではない**。ユーザーのGoogle API projectの分単位rate limitに達した応答と扱い、**連続再試行、他remoteでの迂回API試行、retry増加、Drive設定変更・新世代バックアップ転送・旧backup上書きはしない**。
- 直近entry合成E01〜E12は23:24修正版12/12 PASS（実DB未操作）。本番13VIEW・legacy収集維持、stage venues初回24件、stage entry未作成。独立外部保全・隔離復元、writer全経路、差分同期、切替承認は未完了。正本切替0/13・NO-GO。

## 10/24 00:12 JST：v5_gdriveローカルrclone構成（機密値非表示）
- ユーザーTermius画像：`rclone config show v5_gdrive`出力をawkで許可された状態フラグのみに変換し、`type=drive`、`root_folder_id_configured=no`、`team_drive_configured=no`、`custom_client_id_configured=no`を確認。OAuth tokenやID値は表示していない。
- **専用root_folder_idがなく、マイドライブrootを基点とする設定だが、Googleアカウントが他remoteと異なるかは不明。名前だけではV5専用アカウント/保存先の分離証明にならない。** rclone既定API client利用であり00:09のDrive API 403 rate limitのリスクが残る。既存backup上書き・remote修正・Google API再試行なし。
- entryオフライン12/12、過去合成累計68件PASSは維持。V5用の独立バックアップと隔離復元は**未実施**。旧collector・VIEW13個・venues stage24件不変。本番切替0/13・NO-GO。

## 10/24 00:15 JST：ConoHaローカルrclone認証の同一性比較（機密値不表示）
- ユーザーTermius画像：`rclone config dump`をローカルPythonへ直接パイプし、`v5_token_present=yes`、`drive=UNKNOWN`、`gdrive_a_backup=DIFFERENT_REFRESH_TOKEN`。いずれもトークン実体・指紋表示なし、Drive API通信/転送なし。`drive=UNKNOWN`は比較に使えるrefresh tokenが少なくとも一方で取得できなかったことを示し、同一/別アカウントの判定は不可。
- `gdrive_a_backup`とV5は**refresh tokenが一致しない**が、違うGoogleアカウントの証明ではない。V5の専用root_folder_id/team_driveは未設定（00:12確認）、API 403 rate limit（00:09）でフォルダを確認できず、V5専用Drive・独立新世代バックアップ・復元試験は未証明。
- 旧remoteの設定変更/旧backup上書き/Google APIの連続再試行は禁止。entry合成12/12、旧合成56/56は維持、stage venues24件保全、entry未作成。本番正本切替0/13・NO-GO。

## 10/24 00:18 JST：rclone 3 remoteローカル設定の状態（Termius）
- 機密値を出さず`rclone config dump`→ローカルPython確認：`drive:`はtype=drive/root=no/team=no/refresh=no_or_unknown、`gdrive_a_backup:`と`v5_gdrive:`はそれぞれtype=drive/root=no/team=no/refresh=yes。前段の2つのrefresh tokenは不同一。**違うGoogleアカウント/バックアップ保存先の物理分離は未証明**。root IDなしは必ずしも専用フォルダを使用できないことを意味しない（後日リモート内の専用パスを明示できる）。
- 00:09 Drive API 403 rate limitのためリモート接続/転送なし。Google Driveの既存バックアップ上書き・認証変更禁止。V5専用バックアップ作成・隔離復元は未実施。
- 旧収集維持、stage venues24行保全、entry stage未作成。実正本切替0/13・NO-GO。

## 10/24 00:21 JST：ConoHaローカルbackup棚卸し（Termius）
- `find /var/backups -maxdepth 3`で`*.dump/*.backup/*.sql.gz/*.tar.gz`のみread-onlyメタデータ検査。結果は**1件**：`/var/backups/boat-railway-20261023-ORfLpY/railway.dump`、**393,138,215 bytes（約375MiB）**、2026-10-23 19:32更新。10/23のvenues限定隔離復元24件PASSは既確認だが、**railway DB全体/別DBの完全復元証明ではない**。
- 同検索範囲・形式では`boat_history_archive`のdumpは見つからず、**バックアップ無しと断定せず未確認扱い**。`pg_dump -d railway`は別データベース`boat_history_archive`の内容を含まない。履歴DBは以前`pg_database_size`約1069MBだったが最新容量ではない。
- Google Drive API 403 RATE_LIMIT_EXCEEDED継続リスク、外部独立保全/復元未実証。既存ファイルを削除・上書きしない。旧collector/timers維持、stage venues24件保全、entry stage未作成、本番切替0/13・NO-GO。

## 10/24 08:26 JST：archive DB保全の実行前チェック（Termius）
- `boat_history_archive`存在、datallowconn=t、sessions=0/active=0。/var/backups同一ディスク99G/使用28G/空き67G（30%）。読取のみ。OS critical updateの再起動要求あり、collector保護のため未実施。
- 旧`railway.dump`375MiBは維持。archiveの独立dumpは未実施、Google Drive独立保全/隔離復元は未証明。DB本体や旧collectorには変更なし、正本切替0/13 NO-GO。

## 10/24 08:28 JST：boat_history_archive独立ローカルdumpとTOC検査PASS（Termius）
- 2026-10-24 08:28、ConoHaで`boat_history_archive`単独の低優先度`pg_dump -Fc -Z 1 --lock-wait-timeout=5s`成功。`/var/backups/boat-history-20261024-U6CRtL/boat_history_archive.dump`、`ls -lh` **79M**、owner root/mode0600（umask077）。`pg_restore -l`のTOC読み取り成功、`ARCHIVE_LOCAL_BACKUP_CREATED_TOC_PASS_RESTORE_NOT_TESTED`マーカー/プロンプト復帰を画像で確認。
- 10/23 19:32の既存`railway.dump`（393,138,215bytes）を保護、別ファイルで作成。**TOC検査は復元成功とは異なり、実DBの隔離復元テストは未実施**。クラウド独立保全/隔離VPS外復元も未完了。外部rcloneはAPI 403制限、転送はしない。
- 既存collector/systemd timers、共有13VIEW、venues stage24行、旧表は無変更、entry stageはabsent、正本切替0/13・NO-GO。

## 10/24 08:31 JST：archiveローカルdump隔離復元検査 PASS
- ConoHa Termius結果：新規一時DBへの`boat_history_archive.dump`全体`pg_restore`後、`RESTORED_TABLES=3`、`ISOLATED_DB_REMOVED`、`ARCHIVE_ISOLATED_RESTORE_PASS_CLEANED`を確認。既存`boat_history_archive`・`railway`の変更なし。dumpファイル79MiB維持。
- **復元した3表の実行数・内容・インデックス動作や元DBとの全件一致までは未検証**。旧DBからの最新更新反映保証もない。単一ConoHa VPS上のローカル復元PASSであり、独立VPS外保全/復元は依然未実施。
- Google Drive API 403のため転送なし、旧backup上書きなし。13 VIEWを維持、venues stage24件、entry stage未作成、物理正本切替0/13・NO-GO。

## 10/24 08:34 JST：archive dump TOCと現行テーブル名 read-only照合 PASS
- ユーザーTermius画像：`pg_restore -l`の`TABLE`と`TABLE DATA`は3表：
  `archive.v2_realtime_race_condition_snapshots`、
  `archive.v2_realtime_racer_condition_snapshots`、
  `public.v2_recent_form_archive`。
  `boat_history_archive` live `pg_class`で同名3表を確認。TABLE DATAも3項目あり、**名前集合の一致のみ確認**。
- 08:31隔離DB復元成功・一時DB削除、08:28新規独立ローカルdump約79MiB/TOC PASS、10/23旧railway.dump約375MiB保持。**列型・索引・正確な行数・内容一致やVPS外保全は未証明**。Google Drive API rate limit検出済み、連続再試行/アップロード禁止。現行collector/timers変更なし、共有13VIEW、venues stage24行保持、entry stage absent、物理正本切替0/13 NO-GO。

## 10/24 08:37 JST：archive dump ハッシュ取得PASS（Termius）
- **実在するパス**：`/var/backups/boat-history-20261024-U6CRLt/boat_history_archive.dump`（ランダム名の末尾は`Lt`。旧案内の`U6CRtL`は誤記でFILE_NOT_FOUND）。自動検出による再試行は成功。
- `SIZE_BYTES=81865791`、SHA-256=`7301975821593cdab2fdcf30eedc8d78558537023ed7af30f03d679de19fd37e`、`ARCHIVE_SHA256_READ_ONLY_PASS`確認。読み取り専用の全バイトハッシュであり、**VPS外複製/復元成功ではない**。08:31同VPS一時DB全体復元・削除、08:34TOC/live3表一致は確認済み。実データ全件一致は未検証。
- Drive API 403でGoogle Drive転送なし。旧バックアップ上書き/現行収集停止なし。stage venues24行保護、entry stage未作成、物理正本切替0/13 NO-GO。

## 10/24 10:58 JST：railway local dumpハッシュ取得PASS
- Termius画像：`/var/backups/boat-railway-20261023-ORfLpY/railway.dump`は393138215 bytes、SHA-256=`4ee6a5d9c1ddf67c61b8bb82426961431c25f20f944f87b6cef5137bb294478d`、`RAILWAY_SHA256_READ_ONLY_PASS`で終了。archiveの81865791 bytes/SHA-256も08:37に確認済み。
- 詳細は新規`docs/CONOHA_LOCAL_BACKUPS_20261024_CHECKSUMS.md`（2件の完全SHA、パス、独立保全ゲート）。**ローカル同一VPS内のみ**で、V5専用Google Drive保存先・実転送・外部復元・railway全体復元は未完了。Google Drive API 403制限歴があり勝手な再試行・転送を行わない。
- collector/timer稼働維持、旧表保護、venues stage24行を再コピーしない、entry stage未作成、共有VIEW13、切替0/13・NO-GO。

## 10/24：GitHubのみ V5外部バックアップfail-closed設計完了
- 新規`docs/V5_EXTERNAL_BACKUP_FAIL_CLOSED_PLAN_20261024.md`：G0〜G5安全ゲート（V5本体・2 DB対象、専用remoteと新規不変世代、V3/V4上書き禁止、API403 STOP、外部から取得した実バイトSHA256照合、VPS外隔離復元、個別承認）を策定。`docs/CONOHA_LOCAL_BACKUPS_20261024_CHECKSUMS.md`からリンク済み。
- GitHub新規ファイルをreadbackし9静的項目PASS。**実転送・API再接続・ConoHa実操作・本番正本変更・V5本体ファイル保全・VPS外復元は一切未実施**。既存VPS内のrailway dump 393138215B/限定復元とarchive dump 81865791B/同VPS隔離復元が現在の検査上限。
- legacy collector/timers、共有VIEW13、venues stage24件保全、entry stage未作成。物理本番切替0/13、BUY無効、NO-GO継続。

## 10/24：GitHubのみ V5本体バックアップ棚卸しチェックリスト作成
- 新規`docs/V5_RUNTIME_BACKUP_INVENTORY_CHECKLIST_20261024.md`：R01〜R12の実稼働コード/HEAD・管理外差分、Python/PG/OS依存、systemd unit/timer/drop-in、cron/collector、秘密はキー名だけ、DB復旧要件、永続的ローカル状態、外部での実バイトSHA256と隔離起動/復元までを網羅。GitHub保存・readback、8静的確認PASS。
- **ConoHa現地監査・V5本体コピー・Drive接続・外部バックアップ・実復元は未実施**。existing railway/archiveローカルdumpのみ保全、collector/DB/VIEW/venues stage変更なし。本番正本切替0/13・NO-GO。

## 10/24 11:09 JST：Git管理外collectorと肥大化整理予約
- ConoHa Termius：`/opt/boat-ai-v5`存在/Git YES/HEAD `504b61138e3aaae547688194652e7022c196bfc4`、`/opt/boat-ai-collector`存在/Git NO。collectorはGitHubだけでは復元できず、先に本体とともに別保全する必要。checklist R01/R02を部分確認済みに更新。
- ユーザー要望のGitHub容量整理はIssue [#582](https://github.com/kenshoushouri-cloud/boat-ai-v2/issues/582)でread-only計測→稼働参照確認→保全後PR/別承認の順に追跡。**削除・履歴書換えは未実施**。旧DB/13VIEW/collector/timers/venues stage24行は未変更。entry stage absent、本番切替0/13 NO-GO。

## 10/24 11:15 JST：Git管理外collector直下のread-only棚卸し
- Termius：2ディレクトリ（`__pycache__`, `refund_evidence`）、9ファイル（`backfill_20261017.py`, `.bak_20261019`, `collect_refund_evidence.py`, `daily_v5_safe.sh`, `db_pg.py`, `refund_boats_parser.py`, `refund_pending_20250701_20261005.txt`, `refund_targets_20250701_20261005.txt`, `repair_month_all_pg.py`）。存在の確認のみ。内容や参照先・ファイルサイズは未確認。Git非管理につき保全・現行参照特定前の整理/削除禁止。
- GitHub肥大化整理Issue #582は登録済み、計測・削除未実施。旧DB/collector/13VIEW/venues stage24行維持、entry stage未作成、切替0/13 NO-GO。

## 10/24 11:19 collector直下メタデータ確認
- Termius：Git非管理`/opt/boat-ai-collector`直下9ファイル合計114031 B（約111KiB）、全root:root。shell`daily_v5_safe.sh`637 B/750、`collect_refund_evidence.py`1672 B/750、その他7ファイル644。`refund_evidence/`700、`__pycache__/`755、各dirエントリ4096 Bは**配下全容量ではない**。証拠フォルダ内容/容量は未確認・削除禁止。
- 旧収集、DB、VIEW13件、venues stage24行、entry stage未作成に変更なし。V5本体・collector全体のバックアップやDrive保全は未実施。GitHub整理Issue #582も計測・削除なし。切替0/13 NO-GO。

## 10/24 11:21 JST：Git管理外collector 2ディレクトリ実使用量検査
- ConoHa Termius画像：低優先度・15秒timeout付き`du -sh`で`/opt/boat-ai-collector/refund_evidence`=**2.2M**、`__pycache__`=**24K**。`COLLECTOR_DIR_SIZE_READ_ONLY_PASS`確認。直下9ファイル114031Bと合わせ全体は数MiB程度（`du`の丸めのため精密合計ではない）。
- `refund_evidence`はmode700/root:rootで、証拠や秘匿情報があり得るため**フォルダごと保持**。`__pycache__`も初回保全では除外しない。Git管理外、システム実稼働参照/保全ファイル作成は未実施。GitHub整理Issue #582は削除未実施。
- ローカルDB dump 2件保持、collector/timers/旧DB/13 VIEW/venues stage24行変更なし、entry stage absent、切替0/13 NO-GO。

## 10/24 11:28 JST：Git非管理collector ローカルTAR作成・TOC/ハッシュPASS
- ConoHa Termius：新規`/var/backups/boat-collector-20261024-7Tn5rg/collector.tar` 2,283,520bytes / mode600（umask077）。`tar -tf` PASS、SHA-256=`823a46ee4820e66373abaec7d6e099c3e1d99ae019488691e03d6fbd2a4d7d62`。`COLLECTOR_LOCAL_BACKUP_TOC_PASS_RESTORE_NOT_TESTED`表示。収集root`/opt/boat-ai-collector`を低優先度/最大60秒でTARコピー、既存ローカルDB dumpに触れず。
- **隔離展開・全内容の復元検査・VPS外独立保全・V5 Git管理本体/設定保全は未実施**。refund_evidenceは敏感な情報を含む可能性あり、秘密内容のGitHub/Google Drive転送は禁止。現行collector/timers、旧原本/VIEW13、venues stage24件維持、本番切替0/13 NO-GO。

## 10/24 12:49 JST：Git管理外collectorの同VPS隔離復元 PASS
- Termius画面で、SHA-256基準照合・安全なアーカイブパス検査・一時領域への展開・TAR対展開内容の差分なし・一時領域削除を確認。マーカー`ARCHIVE_PATH_GUARD_PASS`、`RESTORED_ARCHIVE_CONTENT_MATCH_PASS`、`ISOLATED_DIR_REMOVED`、`COLLECTOR_ISOLATED_RESTORE_PASS_CLEANED`。元`/opt/boat-ai-collector`は変更なし。
- 既存`collector.tar` 2283520 B/root-onlyは維持。**これは同ConoHa VPS上の検査であり、VPS外の独立保全・復元、実稼働ソースとの差分/最新性は未検証**。V5 Git管理本体と設定保全も未完了。本番切替0/13 NO-GO、GitHub整理Issue #582は未削除。

## 10/24 12:54 JST：V5実機容量・Git変更件数確認 PASS
- ユーザーTermius画面：`/opt/boat-ai-v5`の`du -sh`は**27M**。`GIT_OPTIONAL_LOCKS=0 git status --porcelain=v1 --untracked-files=normal`の件数が`CHANGED_ENTRIES=0`、`UNTRACKED_ENTRIES=0`、`V5_INVENTORY_READ_ONLY_PASS`。11:09の実機HEADは`504b61138e3aaae547688194652e7022c196bfc4`（その後のHEAD変化はこの検査で未確認）。
- **Git ignoredファイル、実行設定、systemd、秘密値の存在/保全は未確認**。27Mはディスク使用量でアーカイブ容量と同値とは限らない。collectorは同VPS隔離復元成功済み、DB2件はローカル保全/限定検証のみ。V5本体のTAR作成・外部バックアップ/復元は未実施。
- GitHub肥大化Issue #582は整理未着手/削除なし。現行収集/DB/VIEW13/venues stage24件変更なし、本番切替0/13 NO-GO。

## 10/24 12:57 JST：V5本体ローカルTAR保全確認
- ConoHa Termius: /opt/boat-ai-v5 全体のTARが /var/backups/boat-v5-20261024-Dip2iAH2/v5-runtime.tar に新規作成。25,200,640 bytes, mode600。TAR目録検査PASS、SHA256=4f1b2c6cd497e0300b34bad2e08aa570b5eeab09b472bf0be846f89d8c954968。マーカー V5_LOCAL_BACKUP_TOC_PASS_RESTORE_NOT_TESTED。
- V5本体の隔離復元、ディレクトリ外systemd設定等の保全、VPS外の独立保全/復元は未実施。現行収集/旧DB/13VIEW/venues stage維持、本番切替0/13 NO-GO。

## 10/24 13:01 JST：V5本体TAR同VPS隔離復元PASS
- ユーザーTermius画面：12:57作成の`/var/backups/boat-v5-20261024-Dip2iAH2/v5-runtime.tar` (25,200,640 bytes、0600、SHA256 `4f1b2c6cd497e0300b34bad2e08aa570b5eeab09b472bf0be846f89d8c954968`) からSHA照合、安全相対パス検査、0700一時領域への展開、TARと展開ファイル内容比較、一時領域削除が正常終了。マーカー`V5_ARCHIVE_PATH_GUARD_PASS`、`V5_RESTORED_ARCHIVE_CONTENT_MATCH_PASS`、`ISOLATED_DIR_REMOVED`、`V5_ISOLATED_RESTORE_PASS_CLEANED`確認。
- Git非管理collectorも12:49に同VPS隔離復元PASS。DB railway/archiveローカルdumpあり。ただしV5のsystemd service/timer/drop-in・外部秘密設定・OS依存の保全と起動/機能の復元試験、2DB完全復元と相互整合、VPS外独立保全/復元は未完成。元V5/collector/DB/timers/旧VIEWを変更していない。0/13 NO-GO、BUY無効。

## 10/24 13:17 JST：V5 systemd unit名とenabled状態 read-only確認PASS
- Termiusで7件：`boat-v5-daily@morning.timer` enabled、`boat-v5-daily@night.timer` enabled、`boat-v5-daily@.service` static、`boat-v5-forward-window.service` static、`boat-v5-forward-window.timer` enabled、`boat-v5-midnight-catchup.service` static、`boat-v5-midnight-catchup.timer` enabled。4 timer enabled、3 service static。`V5_SYSTEMD_UNIT_INVENTORY_PASS`確認。**enabledは実稼働・実際の実行成功・設定バックアップを証明しない**。
- GitHub code/collectorの同ConoHa隔離復元PASS。systemd定義/drop-in/秘密設定やVPS外独立保全は未実施。稼働変更/再起動/DB/VIEW/venues stageなし、切替0/13 NO-GO。

## 10/24 13:24：systemd実体パス監査PASS
- Termius：朝/夜のserviceは同一`boat-v5-daily@.service`、timer4＋service3で**実体7ファイルすべて`/etc/systemd/system/`**。両インスタンスの`DropInPaths`含め空、timer4 enabled/service3 static。`V5_SYSTEMD_PATH_AUDIT_PASS`。設定内容・EnvironmentFile実体やenabled symlinkの保全は未実施。
## 10/24 13:38 JST：V5 systemd unit実体7ファイルのローカル保全PASS／10月末判定
- Termius画像：新規root-only `units.tar` を作成。20,480 bytes、mode600、tar目録7件・元ファイルとの差分0で`V5_SYSTEMD_LOCAL_BACKUP_7_PASS_RESTORE_NOT_TESTED`表示、SHA256取得（表示値`dc2b54596477a6440f51596d76a84285ea3cf203522355cc1eb4393b224936fb`）。**systemd隔離復元未実施**、external EnvironmentFile・enabled symlink・OS/secretやVPS外独立保全は未完了。
- 10/31まで残り7日。V5/collector同VPSバックアップ＆隔離展開済みだが、共通13物理正本**本番切替0/13**（venuesの隔離stageのみ24行）、全writer差分同期/rollback未証明、V5実学習・事前as-of証拠・真正walk-forward ROI・実予測未検証。**自動購入を含む全面運用を10月末達成と約束しない**。最短目標は保全・取得/予測ゲート合格時に限る非購入限定canary、不可ならNO-GO継続。バックアップ後は物理移行・予測機能の検証へ優先順位を戻す。
## 10/24 13:43 JST：V5 systemd TAR同VPS隔離復元PASS
- Termius：`SYSTEMD_SHA_PASS`、`SYSTEMD_ARCHIVE_GUARD_PASS`、`SYSTEMD_RESTORED_CONTENT_MATCH_PASS`、`ISOLATED_DIR_REMOVED`、`V5_SYSTEMD_ISOLATED_RESTORE_PASS_CLEANED`。13:38作成の7 unit `units.tar`（20,480 B・mode600・SHA256 `dc2b54596477a6440f51596d76a84285ea3cf203522355cc1eb4393b224936fb`）について同VPS隔離展開・内容一致・掃除までPASS。
- V5本体・Git非管理collector・systemd7件のローカルTAR＆同ConoHa隔離復元はPASS。外部EnvironmentFile/有効化symlink/秘密値・VPS外独立保全・DB全復元・本番起動/予測検証は未実施。旧収集/DB/13VIEW/venues stageは維持。本番切替0/13 NO-GO。

## 10/24 13:48 JST：systemd外部認証参照の定義監査 PASS
- Termius：V5 unit実体7ファイルすべて`ENVFILE=0 INLINE_ENV=0 CREDENTIAL=0`、`V5_SYSTEMD_CONFIG_REFERENCE_AUDIT_PASS`。これはユニット本文で3種類の直接指定が無いという意味に限り、シェル/Python経由のenvやsecret依存を否定しない。
- V5本体・collector・unit定義は同ConoHaローカルTARと隔離展開PASS。VPS外独立保全/起動リンク・2DB全復元は未完了。期限優先につき、バックアップ棚卸しをいったん区切り、**次はvenues stageの現時点差分をREAD-ONLYで再測定**する。13本番物理切替は0/13のまま、独立保全やwriter確認前の差分適用/切替は禁止。
## 10/24 13:50 JST：venues差分read-only再監査
- Termius：`public.v2_venues`対`boat_data_stage.venues`、全24会場`TIME_ONLY=24`、`source_newer=24`、会場名/ID/is_active/created_at実データ差分0、追加/欠損0、`VENUES_DELTA_READ_ONLY_PASS`、read-only+ROLLBACK。旧原本の`updated_at`が全24件でstageより進む。自動同期は未実施；旧writerによる定期UPSERTでタイムスタンプのみ進んだ可能性があり、無条件に全件同期しない。
- GitHub変更とConoHaのDB変更は区別、ConoHaに新たな更新・COPYなし。13共有本番物理切替0/13、外部独立保全/全writer証明・実予測/ROI未完了、NO-GO。

## 10/24 13:52 JST：共有13VIEWと隔離stageの実体監査
- Termius read-only `pg_class`：`boat_data` VIEW13/13、`boat_data_stage.venues`だけが物理表、残り12件すべてABSENT。`SHARED_STAGE_INVENTORY_READ_ONLY_PASS`、ROLLBACK。venues stage初回コピーは1/13、本番物理切替は0/13。
- 最優先候補は中核`entries`（旧`public.v2_race_entries`）、既存のオフラインガードがある`entry_snapshots`（旧`public.v2_realtime_entry_snapshots`）も比較。どちらもstage absent。負荷/キーと初回取得証拠が未確認のまま実COPYはしない。10/31購入なしcanaryは検証合格時のみ。

## 10/24 13:55：entry系2元表の読み取り専用サイズ/キー検査PASS
- `public.v2_race_entries`: 121MB、統計推定438,299行、38列、PK(id)、UNIQUE(race_id,lane)。
- `public.v2_realtime_entry_snapshots`: 33MB、統計推定125,870行、21列、PK(id)、UNIQUE(race_id,snapshot_label,lane)。
- `ENTRY_STAGE_PREFLIGHT_READ_ONLY_PASS` / ROLLBACK。推定件数は実COUNTではない。前者はcore、後者はFIRST_CAPTURE_UNVERIFIEDなので予測as-of証拠に採用しない。stage次候補は**容量少・オフラインE01〜E12が整備済みのentry_snapshots（隔離研究/移行準備のみ）**。独立外部保全・実writer証明・ユーザー別承認までCOPY/DML/VIEW切替禁止。

## 10/24 14:06 JST：entry_snapshots DDL前カタログ安全監査PASS
- Termiusで`public.v2_realtime_entry_snapshots`: physical r、`boat_data.entry_snapshots`はVIEW v、`boat_data_stage.entry_snapshots` absent=true、21列、自然キー3/3 NOT NULL、UNIQUE index2、ユーザートリガー0、関係FK0、旧source idには`nextval` defaultあり。`ENTRY_SNAPSHOT_SCHEMA_READ_ONLY_PASS`、ROLLBACK。stage作成/実COPY=0、収集停止なし。
- stageを作るなら旧sourceのserial default/sequenceをstageに持ち込まない。少量33MBでも新外部独立バックアップ＋復元と全writer確認・別承認がまだなく、新規DDL/DMLはNO-GO。FIRST_CAPTURE_UNVERIFIEDのため予測用事前as-of証拠には使わない。

## 10/24 14:25 JST：V5 Drive読み取り接続probe PASS
- Termiusの`rclone about v5_gdrive:` はretry/通信量制限・30秒timeout下で`V5_DRIVE_READ_ONLY_PROBE_PASS`。00:08の403レート制限は今回の照会では再現せず。**書込権限・VPS外の実バックアップと復元・別Drive割当は未確認**。既存収集、DB、13VIEW/BUY無変更。切替0/13 NO-GO。
## 10/24 14:28 JST：V5 Drive極小書込probe FAIL（原因未取得）
- Termius画面：14:25 `rclone about v5_gdrive:` 読み取りPASS、14:28 `rclone copyto` --immutable・1回retry・低TPSの新規専用prefixへの極小テストは`V5_DRIVE_WRITE_TEST_FAILED`。stderr/stdout破棄したため根本原因・HTTP status不明。readback未到達。**Google DriveへのV5バックアップ成功と扱わない**。残存remote試験ファイル有無も未確認。
- 直近00:08 API 403 rate limit発生履歴あり。しかし今回のFAILをrate limit断定しない。旧backup/V3/V4/ConoHa/DB/timer/13 VIEWに変更なし。切替0/13 NO-GO。
## 10/24 14:31 JST：V5専用Google Drive書込probe 403 RATE_LIMITで停止
- Termius：`V5_DRIVE_WRITE_FAILED`, `RCLONE_EXIT_CODE=1`, `HTTP_STATUS=403`, `ERROR_CLASS=RATE_LIMIT`, `V5_DRIVE_DIAGNOSTIC_FINISHED`。同日14:25読取about PASSだが、書込は14:28/14:31連続失敗・readback未到達。HTTP 403/分類から**API書込レート制限が強く疑われる**。消費クォータや解除時刻は未確定。**本日このremoteへの追加書込probe/大容量転送/強制リトライ禁止**。旧V3/V4と本番データの削除・変更なし、外部バックアップ達成ではない。
- 外部新世代が保全できない間はConoHaでの事前保全/同VPS復元PASS済みを維持し、DB新stage COPYや本番切替は不可。代わりに収集writer/read routingをread-only監査して実切替の準備を進める。
## 10/24 14:35 JST：V5 writer経路read-only監査PASS（認証ではない）
- Termius: 4 timers=active/enabled。forward-window.service=activating、midnight-catchup.service=inactive。daily@morning/night.service=inactive、daily@.service=unknown（template判定）。root/postgres関連crontab=0、cron.d一致なし。
- STATIC検出: repair_month_all_pg.pyのhelper UPSERT候補にv2_race_entries等。v21_realtime_collector_pg.pyにはlegacy realtime6表参照・DDLあり（ヒントのみ）。forward-windowはv5.conoha_realtime_window_pg、midnightはv5.conoha_midnight_results_pg。dailyインスタンスtarget=UNRESOLVEDはshell/wrapper経由の可能性があり未証明。
- `NO_RUNTIME_WRITE_PATH_CERTIFICATION_YET`、`V5_ACTIVE_WRITER_ROUTES_READONLY_COMPLETE_NO_DB_WRITES`、`V5_WRITER_ROUTE_AUDIT_COMMAND_PASS`。forward-windowがactivatingで長時間滞留しているか不明。収集停止/DB操作・Drive書込は未実施。Stage1/13、本番0/13 NO-GO。
## 10/24 14:38 JST：forward-window.service 状態 read-only確認
- Termius: `boat-v5-forward-window.service` LoadState=loaded / ActiveState=inactive / SubState=dead / Result=success / ExecMainStatus=0 / MainPID=0 / ExecMainStartTimestamp=2026-10-24 14:35:01 JST / TimeoutStartUSec=4min20s。14:35のactivating後、14:38に処理完了・滞留なし。あくまでサービスの終了成否で、`--apply`の有無や実データ取得・書込は未検証。
- `v5/conoha_realtime_window_pg.py`をGitHubから確認：デフォルトはPREVIEW/NO_HTTP_NO_WRITES、`--apply`かつ`V5_ENABLE_LIVE_COLLECTOR=YES`で収集。実際の起動モードはjournalの限定マーカーで要確認。既存収集/DB/cron/timers/VIEW変更なし、Drive書込403で停止、13系統本番切替0/13 NO-GO。
## 10/24 14:45 JST：forward-window 実行モードログ監査
- Termiusの14:30–14:40 journal限定集計で `APPLY_RUNS=2`, `PREVIEW_RUNS=0`, `CANDIDATE_LOGS=2`, `LAST_CANDIDATES=3`, `NO_WRITE_RUNS=0`, `COLLECTOR_SUCCESS=5`, `COLLECTOR_FAILED=0`, `COLLECTOR_TIMEOUT=0`、`V5_FORWARD_LOG_AUDIT_READ_ONLY_FINISHED`。
- 実際にAPPLY・HTTP collector subprocessが5件code=0を返すことは確認。ただし5ユニークraceとは限らず、実際のDBスナップショットINSERT/品質、時間前証拠、BUY/ROIは未証明。GitHub `v5/conoha_realtime_window_pg.py`では `V5_FORWARD_COLLECTOR_RC=<rid>:<code>` 形式で、`SNAPSHOT_LABEL=conoha_forward_YYYYMMDD_HHMMSS`を各childへ渡す。
- Drive書込403 RATE_LIMITにつきリトライ停止。既存DB/cron/VIEW変更なし。Stage1/13、本番0/13 NO-GO。
## 10/24 14:49 JST：V5 forward実DB snapshot保存 read-only PASS
- Termius: 14:30〜14:40 collector RC=0ログ5件→ユニーク4レース。旧public.v2_realtime_{entry,exhibition,odds}_snapshotsでforwardラベル14:30〜14:40をread-only検索。`V5_FORWARD_DB_READ_ONLY_CHECK_PASS`、ROLLBACK。
- `20261024_05_10` 多摩川10R: entry12/exhibition6/odds240。`20261024_09_10` **津10R**: 6/0/120。`20261024_13_09` 尼崎9R: 6/6/120。`20261024_22_09` 福岡9R: 6/0/120。計30/12/600。5回ログと4ユニークレースで再取得あり。実INSERT実行の直接証明やas-of条件/品質/学習採用は未証明。
- Drive書込HTTP403 RATE_LIMITで追加試験禁止。共通stage1/13、本番cutover0/13 NO-GO。

## Next ONE task（次の一作業）
**ConoHa `railway`の上記4レースに限定し`public.v2_races.deadline_at`とforwardラベル当時の3系統`snapshot_at`を照合、締切前/以後/不明の件数のみREAD ONLY/10秒上限/ROLLBACKで確認**。展示0件を収集失敗と即断しない。DB DML/VIEW変更、Drive再試行、BUY、本番切替は禁止。