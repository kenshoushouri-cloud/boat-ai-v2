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
- GitHub `deploy/conoha/boat_shared_staging_delta_plan_offline.py`新規。13旧物理表/現行13非更新VIEWの厳密マッピングを読み、VIEWに衝突しない**`boat_data_stage.*`の複製先計画**を生成（このschemaは**未作成**）。`v5_data.venues`の既存24行ステージは変更なし。
- 全件PK昇順・全列digestの2入力からINSERT/UPDATE/DELETEの**差分計画候補**をストリーム検出する関数を実装。日時watermarkだけで削除を見落とさないための仕様であり、**CDCも実SQL同期も実装・実行していない**。13の現行コード候補とGO/NO-GOを分離、証拠がない限りNO-GO。
- `tests/test_boat_shared_staging_delta_plan_offline.py`に8件の単体試験を新規追加。さらに`deploy/conoha/boat_shared_staging_offline_test_once_20261023.sh`で`origin/main`から必要4ファイルだけを隔離`/tmp`へ取得し、**ConoHaの現行worktreeを変更しない**単体試験を1回実施できるよう用意。GitHub作成とreadbackは確認済、**ConoHa/Actions上のテスト実行PASSは未確認**。現行収集・DB/Drive・BUY・timerは変更していない。

## 10/23 17:47 JST オフラインステージ検査（実証済み）
- ユーザーTermiusスクリーンショット：`deploy/conoha/boat_shared_staging_offline_test_once_20261023.sh`実行、`ISOLATED_OFFLINE_STAGE_TESTS_BEGIN`、**8 tests / 0.002s / OK**、`OFFLINE_STAGE_AND_COMPLETE_KEY_DELTA_TESTS_PASS_NO_DB_NO_BUY`、rootシェル復帰。GitHubから必要ファイルのみisolated取込のオフライン試験。13のVIEWと衝突しないstaging計画、PK完全キーのINSERT/UPDATE/DELETE差分計画、未検証時のNO-GOが**合成ケースでPASS**。
- **未実施**：ConoHa DBに`boat_data_stage` schema/実表の作成、venues一表でも物理複製、差分適用/CDC、最新バックアップ復元試験、夜間切替予約、V5実予想・BUY。旧`public.v2_*` writer収集継続。合成試験を実DBの正確さや準備完了とは扱わない。
- バックアップ合意：初の物理DB変更前はConoHaローカルの新世代＋復元試験。深夜本番切替前はVPS障害にも耐える独立保全が必須。整理後の自動Drive保存はV5本体・共通原本・必要な履歴/設定/モデルのみに限定し、V3/V4は別アカウント側に旧世代を保持。未設定。

## Next ONE task（次の一作業）
**最小venues 1表のstaging準備をGitHubのみで実装・オフライン検査**。現行`boat_data.venues`は非更新VIEW、旧`public.v2_venues`実表、既存`v5_data.venues`24件staging。上書き/二重コピーしない。候補`boat_data_stage.venues`への安全な段階移行のDDL/PK/制約/権限・ビュー依存・差分整合・切り戻しのゲートを明示し、**初回DB変更前のConoHaローカルbackup＋限定復元PASSなしでは絶対適用しない**。無条件のbulk stage、旧表DELETE/rename、cron/collector変更、Git pull、BUY、Drive上書き/定期予約は禁止。ツールは少なく短い作業1つずつ。実行結果や容量・SHAは次回liveで再取得。
