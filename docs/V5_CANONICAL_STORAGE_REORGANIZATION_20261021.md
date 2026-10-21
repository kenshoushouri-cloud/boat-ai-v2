# V5 専用データ保存・参照先の再編成計画 — 2026-10-21

Status: **STAGE 1・2 ConoHa適用済み / VIEWのみ11件 / 原本移動・削除なし**  
User direction: V5本体・バックテスト・Forward稼働を進める前に、保存先の体系を整理する。費用・容量・既存データ保全を優先。

## 目的・重要な分離
- V5の **正本データ/現場で観測された締切前スナップショット/事後結果/モデル予測と仮想収支/古い研究・原本アーカイブ** を混同しない。
- バージョン差による収集元の食い違いを隠すのではなく、ソースの責任と更新予定を台帳化する。
- ConoHa 2GBでの容量・RAM/CPU負荷を抑える。不要な全表複製、新たなDB常駐サービス、新規課金、サービス停止はしない。
- 歴史原本は`boat_history_archive`と暗号化外部バックアップを保存し、V4復旧資産を保全。歴史データを締切前に取得済みだったかのように扱わない。

## 実測（ConoHaローカル `railway` DB、2026-10-21のread-only確認）
- 2026-10-07〜10-20：`v2_races`=1,860レース、`v2_results`結果1,570件。1,570件全部が`v2_race_entries`の6艇と結合可。
- 同期間`v2_result_entries`には0件。公式Kファイル由来の同テーブル結果は2026-10-06まで、422,544行。
- 2026-10-20 出走表864件中`recent_form`非空0件。原因候補は`repair_month_all_pg.py`（`v2_results`）と`save_k_day_results_pg.py`（`v2_result_entries`）が別収集経路で、ConoHa日次は前者のみを呼ぶこと。
- 2026-10-21 朝収集156レース/936艇で07:46に成功。締切前収集は共有ロックと競合。衝突時のExit75をsystemd正常扱いにする修正が導入されたが修正後の実再現は未検証。

## 目標アーキテクチャ（論理的な名前。物理CREATEは監査後）
| V5公開論理名 | 現行候補元 | 保存・検証規則 |
|---|---|---|
| `v5_data.races` | `public.v2_races` | race_id主キー、race_date、deadline_at、開催中止 |
| `v5_data.entries` | `public.v2_race_entries` | (race_id,lane)単位、racer_number/racer_class等 |
| `v5_data.racer_results` | `public.v2_result_entries` | 全6艇着順・事故・取得元。歴史K欠落は欠落として表示、偽補完しない |
| `v5_data.results` | `public.v2_results` | 正式3連単払戻・結果。選手6艇着順テーブルとは別 |
| `v5_data.exhibition_snapshots` | `public.v2_realtime_exhibition_snapshots` | 取得時刻、snapshot_label、完全性、締切前判定 |
| `v5_data.odds_snapshots` | `public.v2_realtime_odds_snapshots` | 120点・取得時刻・公式出所・締切前判定 |
| `v5_data.weather_snapshots` | 実表名要再確認 | 場/レース/取得時刻、締切前性を明示 |
| `v5_data.motor_stats` | 実表名要再確認 | モーター交換日・標本数・時系列を保持 |
| `v5_data.racer_history_asof` | 公式K全着順＋必要なら歴史保管庫 | レース日より前の成績のみ；利用可能時刻の証明とは区別 |
| `v5_research.predictions` | 新設候補 | V5 version、判断時刻、入力証拠ハッシュ、3連単120通り/選択、BUY不可がデフォルト |
| `v5_research.settlements` | 新設候補 | 成績/返還の公式証拠、PENDING/VOID/返還、試算と実購入を別集計 |

`v5_data` と `v5_research` はConoHaのローカルPostgreSQLに構築済み。 **VIEW/読み取り用アクセス層で、旧テーブルから大量COPYしない。** 既存V5 Pythonモジュール名とは別管理。

## 移行の5段階（各段階で独立承認・検証）
1. **棚卸し（READ ONLY）**：DB/schema/table/行数推定/実容量/索引/参照先/更新プログラム/日時・source項目/過去原本の有無、欠落日を記録。行数の完全性を`pg_class.reltuples`推定値で主張しない。
2. **参照層（最小DDL、別承認）**：`v5_data`を既存テーブルの限定VIEWから構築。既存スキーマと既存アプリに影響しない。実表名/型を確認したものだけ作る。UPDATE権限は与えない。
3. **収集経路の統一（別承認）**：ライブ毎日`v2_races`/`v2_results`、公式Kファイルの選手別詳細結果、5分前展示/オッズを業務別に監督。競合ロックの分離は独断でせず、タイマー実負荷と欠落時間帯を確認。重複取得・不必要なHTTP連打を避ける。
4. **V5入力統合と予想原本（別承認）**：使用時点の条件を満たすスナップショットのみ入力。欠落・事後の情報はHOLD。固定V5モデルの重みは不変。研究用予想記録は不可逆性/再現性を別確認、過去の再実行を事前予想実績に算入しない。
5. **旧保存データの縮退（別明示承認）**：件数と識別子・ハッシュ監査、DBリストア試験、Google Drive暗号化バックアップ照合、V5依存解消を完了してから。削除対象を列挙し最終承認。Railwayクラウド削除予約状態と混同しない。

## 禁止・成功条件
- 元`public.v2_*`の無断UPDATE/DELETE/DROP、V3/V4の消去、無断データ重複COPY、秘密値のチャット/GitHub流出、無断BUY/LINE/Telegram実送信、V5モデル重み変更禁止。
- 新設VIEWを作っても、未来情報漏洩対策・Forward一次取得証拠・真正の3連単ROIが完成したことにはならない。
- 移行成功は「**欠落と出所が分かり、V5が日時条件付きで参照でき、旧系を残したまま同じ結果を再現できる**」状態。ファイル名の統一だけで成功とはみなさない。

## Next ONE task
ConoHa Termiusで **選手の直近5走・選手級別の適用日・モーター数値の元データ列**をread-onlyで棚卸しし、過去K結果とスナップショットの利用時点判定を設計する。旧VIEWはそのまま維持。DB移動/本番入力切替はしない。

## 2026-10-21 実装済み（ユーザースクリーンショットで確認）
- `deploy/conoha/v5_data_views_v1.sql`：6つの`v5_data`非更新VIEWを作成、全`is_updatable=NO`。同時点ConoHa `railway` DB全体容量約3,414MB、主な6表計約1,161MB（インデックス含む）。
- `deploy/conoha/v5_data_views_v2.sql`：`v5_data.weather_snapshots` / `race_condition_snapshots` / `racer_condition_snapshots` / `racer_course_stats_snapshots` の4非更新VIEW、`v5_research.motor2_legacy_shadow` 1非更新VIEWを作成。合計 **v5_data=10, v5_research=1、11 VIEW**。実データCOPYなし、既存`public.v2_*`を更新・削除していない。
- モーター研究元 `public.v2_v24_motor2_forward_shadow` 263MB はV24シャドー履歴であり、V5本番予測入力として承認されていない。気象186MB、選手コース統計83MB、選手直前状態64MB、レース条件56MBもスナップショットと取得時点の監査前にはV5採用を保証しない。
- 次は上記`Next ONE task`をread-onlyで実行後、正規の選手直近5走生成と、V5用モーター元データを設計。過去K（10/07〜20の全6艇着順欠落）の修復を優先する。

## 2026-10-22 方針更新：コピーではなくV5物理管理へ段階的移管
- ユーザーの再確認：データを全件複製するのでなく、V5専用の保存先へ「移す」形で今後の運用を単純化する。上記の**論理VIEWのみを最終状態とする計画を見直す**。既存原本の全面COPYはしない。
- PostgreSQLでは同一DB内でテーブルを`ALTER TABLE ... SET SCHEMA`によりデータ再複製せず移管できる余地があるが、**このコマンドはまだ実行しない**。既設`v5_data`の同名VIEW、`public.v2_*`への書込/集計プログラム、テーブル参照依存、FK・索引・シーケンス・権限、バックアップ/復元手順を事前に整合させる必要がある。
- 旧参照名の互換VIEW化だけでは、`INSERT ... ON CONFLICT`やテーブル依存のバッチが従来どおり動く保証はない。旧writerを新しい保存先へ対応させ、収集継続/過去バックテスト再現性/サイズ/重複/タイムスタンプ等を検証してから切替える。
- **Stage 0（実施中）**：GitHub `deploy/conoha/v5_physical_migration_readonly_audit_20261022.sql` はスキーマ実態、DB容量、インデックス、FK、トリガ、シーケンス、VIEW依存を読み取り専用で一覧化。推定件数を完全件数として扱わず、実際の収集プロセスとコード依存も別途監査。既存データ・サービス・OS・Railwayを変更しない。研究用`motor2_legacy_shadow`は本番データに混ぜない。
- 本番の物理移管・旧テーブル破棄・サービス切替は、事前検証と外部バックアップ/復元確認後の**別途明示承認**が必要。移管後も費用を増やさずデータ二重保存しない。

## 2026-10-22 06:22 稼働収集経路検査と旧テーブル再生成リスク
- ConoHa Termiusで`v5_active_writer_routes_readonly_20261022.py`が`V5_ACTIVE_WRITER_ROUTES_READONLY_COMPLETE_NO_DB_WRITES`。インストール済み3 services、active+enabled timers 4件（morning/night、forward-window、midnight-catchup）。2 oneshotの`inactive`はタイマー式なら正常。cron対象0。
- 朝・夜`boat-v5-daily@.service`はテンプレートとして`target=UNRESOLVED`、**運用中の実呼び出し先は未認定**。forward-windowはPython側で`v21_realtime_collector_pg_safe.py`→`v21_realtime_collector_pg.py`を呼ぶ。旧collectorは`_ensure_realtime_tables`で旧`v2_realtime_*`表に`CREATE TABLE IF NOT EXISTS`や`ALTER TABLE`を実施する実装を持つ。移管後に旧public表が再生成されてデータ分離が再発する危険があり、**移管前にスキーマ作成処理の無害化・旧writerの参照先切替が必要**。
- `db_pg.py`の`sql.Identifier(table)`は現在一部分のみ指定されたテーブル名（例`v2_results`）を使うため、安易に`v5_data.results`を文字列渡しすると引用識別子として誤解釈される。`ON CONFLICT`・`replace_rows_atomic`はVIEWに単純切替できない。これらも移行ガード対象。
- GitHub`deploy/conoha/v5_active_writer_routes_readonly_20261022.py`改訂（commit `10b93eab`）：朝/夜のテンプレート具体化 + 旧collectorのDDL警告を表示する。読取専用、データ本体/DB/稼働サービス未変更。次の安全検査で朝夜`DAILY_INSTANCE`出力を確認する。

## 2026-10-22 06:34 朝夜収集の実経路・V5物理移管の不足ソース
- Termius `V5_DAILY_ENTRYPOINTS_READONLY_COMPLETE`。morning/nightの両方はConoHaの`/opt/boat-ai-collector/daily_v5_safe.sh`へ解決。同wrapperの静的検査では`repair_month_all_pg.py`のみ直接参照、`save_k_day_results_pg.py`の直接参照なし（呼出しの静的な検査であり実稼働実績の証明ではない）。
- GitHub `repair_month_all_pg.py`の書込を点検：`v2_venues`,`v2_races`,`v2_race_entries`,`v2_results`,`v2_odds_trifecta`を`db_pg.py`の`upsert_rows`へ渡す。別プログラム`save_k_day_results_pg.py`は`v2_result_entries`に選手別全6艇結果を保持。朝夜wrapper経路と別であり「結果完備」≠「全6艇結果完備」。
- 既決の`v5_data` VIEW構成に`v2_venues`と`v2_odds_trifecta`の専用参照がない。この2つを見落として移管を進めると収集先が分散。**現行11VIEWを即破棄しない**。候補名`v5_data.venues`,`v5_data.trifecta_odds`は検討用で未本番作成。
- Stage 1 SQL `deploy/conoha/v5_daily_missing_sources_readonly_20261022.sql` で必要6ソースの元実テーブル・既存V5 VIEW/表の有無と容量を読取専用で確認。次工程は表示を確認し、テーブル名衝突、旧writer/upsert/DDLのスキーマ参照更新と既存データ原本移管のアトミックな手順を設計。DB物理移動、service停止・改造、Railway削除等は未実施。

## 2026-10-22 06:37 実測：朝夜収集に必要な6表と欠損V5管理先
- Termius`V5_DAILY_MISSING_SOURCES_READONLY_COMPLETE_NO_DB_WRITES`成功。DB=railway, transaction_read_only=on。
- 既存6表（索引込み、実測時点）: `v2_odds_trifecta`=1443MB、`v2_result_entries`=247MB、`v2_race_entries`=120MB、`v2_results`=30MB、`v2_races`=17MB、`v2_venues`=80KB。既存V5 4表はVIEW、候補`v5_data.trifecta_odds`と`v5_data.venues`はMISSING。行数はcatalog推定で完全件数ではない。
- 3連単の`v2_odds_trifecta`とタイムスタンプ付き`v2_realtime_odds_snapshots`は別系列。物理的なスキーマ移動だけではDB総サイズ削減にはならないが、全行COPYによる二重増加は回避可能。
- V5構成候補にマスターと3連単オッズ原本を追加しても、writerの`INSERT ON CONFLICT`、VIEW同名衝突、旧collectorのCREATE/ALTER自動再作成、schema指定文字列処理の解消前に移管禁止。
- GitHub`deploy/conoha/v5_venues_odds_cutover_gates_readonly_20261022.sql` (commit `840c1ce5`)を作成。2表の既存名の衝突、PK/一意INDEX、FK、トリガ、依存VIEW、書込キーの存在をcatalogのみread-only確認。差分書き込み・コピーなし。

## 2026-10-22 06:41 V5物理切替ゲートPASS・コードのみ段階準備
- Termiusで`V5_VENUES_ODDS_CUTOVER_GATES_READONLY_COMPLETE_NO_DB_WRITES`。 `v2_odds_trifecta`1,443MBと`v2_venues`80KBは実TABLE、`v5_data.trifecta_odds`/`venues`は未作成。双方でFK/ユーザートリガ/依存VIEW=0。オッズPK `id`＋UNIQUE(`race_id`,`ticket`)、venues PK `venue_code`＋UNIQUE(`venue_id`)、競合処理用の列と一意索引あり。現状は`PENDING_OTHER_GATES`で、完全な移管可否判定ではない。
- GitHubのみ変更、ConoHa DB/収集タイマー/原表は無変更。`v5_daily_table_routes.py`：既定`legacy`無変更、`V5_DAILY_WRITE_ROUTE_PROFILE` を venues/odds/venues_odds ＋`CONFIRM_V5_PHYSICAL_WRITER_ROUTE=YES`の両方を明示した場合のみV5候補へのwriter routing。`repair_month_all_pg.py` daily upsertにのみ適用。`db_pg.py`に明示的な`v5_data.venues`/`v5_data.trifecta_odds`の引用識別子サポート追加。その他のDML/DDL/読取経路はまだ未統一であり、環境変数を設定しての本番有効化・実移動は**禁止**。
- オフライン試験`tests/test_v5_daily_table_routes.py`を追加。旧writer/直前収集のCREATE/ALTERの修正、他の読み書き/バックアップ復元と当日データの確認、切替手順と戻し方・明示承認が終わるまで物理移管なし。