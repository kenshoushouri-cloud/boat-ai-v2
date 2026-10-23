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

## 収集・移行の安全条件
- 現行ConoHaのmorning07:00/night23:00、forward毎5分（期限9〜24分）、midnight catchup01:20等のtimer/子processを停止しない。oneshot inactiveやflockコード75だけでは故障とは限らない。旧writerを片方だけ切替するとsplit-brain・差分漏れの危険。固定時刻になっただけで停止しない。
- ユーザー申告ではGoogleドライブに以前のバックアップあり（**内容・復元可能性は未検証**）。**整理途中の全量バックアップを何度も上書きせず、古い世代は保持**。整理・共通化を終えた段階で新しい世代を保存する。ただし10/19以降の展示・オッズ等は旧世代だけでは守れないため、**物理切替の直前までに、当日変更分を含む整合した別世代バックアップと限定復元試験を必須**とする。バックアップが未準備なら深夜切替はNO-GO/延期。新世代の復元・照合までは古いGoogle Drive世代を上書き/削除しない。全writer/reader・最終delta・ロールバックも必須。旧表削除は別承認。
- 移行は13ソースの書込責任者/読み込み依存を洗い出し、まずvenues24件pilotでroute/read/rollback検証、大きなオッズ/展示は容量/WALとlive追記を見積もって表単位で段階切替。データ欠損を補完したことと当時のforward証拠を再現したことを混同しない。
- `v5_daily_table_routes.py`や`v5_realtime_table_routes.py`にopt-in案があっても、**現行共通VIEWへINSERTできず、全子ジョブ対応の保証もない**。既存flagsはlegacyから変更禁止。

## Next ONE task（次の一作業）
GitHub側で`docs/BOAT_SHARED_UNATTENDED_CUTOVER_PLAN_20261023.md`を根拠に、13共通元表の書込責任者/朝・夜・forward・catchup・backfill・DDL・readerの**機械可読manifest案**を1工程だけ作成する。改名/複製/切替/自動予約/サービス停止/BUYは行わない。ConoHa最新バックアップと別媒体復元検査、実writerの完全列挙、全差分追従・GO/NO-GOが揃った時点で、対象と日時をユーザーに明示して別承認する。収集を旧表のまま継続。
