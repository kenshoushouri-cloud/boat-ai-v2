# V5データ保存先・集約進捗ボード（2026-10-24 17:39 JST）
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

### Next ONE task
**全13系統を個別探索し直さない**。上記固定表を採用し、既存GitHub preflightを用いた「複数表一括のstage readiness gate」と移行バッチ優先順を確定。早期開発のため並行して、V5既存研究の実ソース結合アダプタを**read-only／no-buy**で優先設計。新データの無断物理コピー/VIEW切替/BUY/Drive retryは禁止。
