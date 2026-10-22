# 共通データ基盤と V5/V6 予想エンジンの分離 — 2026-10-22

## 採用する設計と現状
ユーザーの正式方向性：V5が複製先データから安全に稼働できるようにし、移行後は重複する旧物理表を**条件を満たしたものから削除**。将来V6ができてもデータを二重に複製せず利用できるようにしたい。採用方式は**共通データ基盤**。単一ConoHa PostgreSQL `railway` 内にバージョン中立の物理データ領域 `boat_data` を作り、V5/V6はプログラム/モデル固有部分のみ分離する。既存 `boat_history_archive` DBは引き続き履歴・研究原本用（read-only接続、時間制約付き結合）として使う。新規DBサービス・Railway容量/課金追加はしない。

**2026-10-22 21:15の実証済み作業**：`public.v2_venues` 24行 → `v5_data.venues`24行を局所的にコピー、EXCEPT ALL差分0、6列・2インデックス。元表は無変更。現行収集および予測のread/write routeは依然legacy、`v5_data.venues`は**staging-only**。そのほかは既存 `v5_data` の11個のVIEW、`v5_research`1個の研究VIEWのみ。既存12ソースの実コピー未実施。**V5共通データ運転も、旧表削除もまだ完了していない。**

## 適切な「データ専用フォルダ」と「テーブル」の区別
- PostgreSQL実表をOSのフォルダへ手で移動してはいけない。DB正規データは`railway.boat_data`スキーマのテーブルが正本。データ保管用ディレクトリは公式ファイル/K・暗号化バックアップ・手動検査用インポート原本などのDB外ファイルだけに使用する。たとえば`/srv/boat-data/raw`（案、未作成）を新設する場合もパーミッション/容量/自動削除/復旧を決めてから。
- 共通API/DAO（Python）を一か所に設けて`boat_data`のスキーマ付き名称を使用し、V5読み込み側は同APIか互換的な`v5_data`VIEWを使う。**書込処理の`INSERT ON CONFLICT`は非更新VIEWでは代用できない**。書き込みは実表に経路を統一し、バージョンごとに二重書込しない。V6も共有の実データを読む。
- `v5_research`や将来`v6_research`にはバージョン別の予想/学習結果とモデル識別子、入力出所ハッシュ、締切前の収集証拠と予測時刻を格納。公式結果（事後の正本）と分離する。未採用特徴量も元データとして保持するがライブ予測投入は検証後だけ。

## 実テーブル配置と過渡期
| 概念 | 現在 | 最終的な正本 |
|---|---|---|
| 競艇場マスター | `public.v2_venues` ＋ staging `v5_data.venues`24行 | `boat_data.venues`（**既存stagingを将来SET SCHEMAで移動**、再複製しない） |
| 出走表/レース/選手情報/モーター・ボート・当地成績 | `public.v2_races`, `v2_race_entries`, `v2_racer_course_stats_snapshots` | `boat_data.races`, `entries`, `racer_course_stats_snapshots` |
| 展示/オッズ/水面/天候/進入状況 | `public.v2_realtime_*`, `v2_odds_trifecta` | `boat_data.*` の原本及び`snapshot_at`を保持する同系統表 |
| 公式結果・艇ごと着順 | `public.v2_results`, `v2_result_entries` | `boat_data.results`, `racer_results`（PENDING/VOID等保持） |
| 過去の直近成績/レース・選手コンディション履歴 | `boat_history_archive` の実表3件、合計1,069MB | **そのまま同DBの正本として維持**、V5/V6は独立のread-only adapterで参照 |
| V24 motor2研究shadow | `public.v2_v24_motor2_forward_shadow` | 検証用アーカイブ、ライブ特徴には混ぜない |
| V5予測・試算・精度評価 | まだ構築・検証途上 | `v5_research`、V6のモデル出力は別領域 |

上記の最終テーブル名は設計案で、**現時点のDBに存在することを意味しない**。既存の`v5_data.raw_*`設計案・コードをいきなり削除・改名しない。既存ステージ表`v5_data.venues`は切替前にコアAPI/識別子と索引・所有者・権限の準備を確保したうえで`ALTER TABLE ... SET SCHEMA`（メタデータ移動、全行再コピー不要）の是非を判断する。重複する旧物理表は段階的に減らす。

## 切替手順：COPY→検証→単一正本化
1. **共通データ契約を先にコード化**：旧→新の出所、書込責任者、取得時刻、履歴as-of条件、欠損の扱いを列挙。旧timer/morning/night/forward/midnight-catchupおよび単発補完のread/write/DDLパスを完全把握。今夜23:00は自動停止の時刻ではない。
2. **小規模な先行表**：venuesの既存ステージ24行の現時点での一致を再検証。新物理`boat_data`スキーマ/アクセス層を別承認で準備し、staging venuesをメタデータ移動する際には現行ルートフラグ・VIEW・依存を同時更新。原本をまだ消さない。
3. **大きな表は必要部分から**：明示的なコピー/追従方針で、追加入力・UPDATE・DELETE・競合・索引・制約も同期。大容量オッズ~1.4GB、各種snapshot計1GB超についてはバッチ・WAL・索引再作成でディスク使用量が**一時的に増える**ため余裕監視。将来は正本を移す方式にし、収集時刻や6艇/120オッズ完備は別に検証。
4. **安全な停止窓で書込先/読取先切替**：最終レースの締切前展示/オッズ取得完了の証拠を確認。必要なsystemd timer/service/子processを短時間停止、差分同期、PK/全件数・重要列・タイムスタンプ検査、全経路を共有物理表へ切替、1件ずつ非購入canary検証。結果は翌日取得でもよいが、それまでcatchupが旧テーブルへ書くことを禁止。条件不達なら現行側で収集継続し延期。
5. **旧原本を削除可能にする条件**：V5の書込・読取・backtest・履歴参照・復旧切り戻しが一定期間再現し、V6も共有データ参照できる設計、旧テーブル参照0、遅延ジョブ0、データパリティ、直前証拠の欠損0または明確な欠損表示が確認できること。**整理後の新共通データバックアップ・復元確認**を削除前に行い、表ごとに削除対象/容量/影響を明示し個別承認。10/19バックアップのみを根拠に10/22以降の原本は消さない。
6. **二重保管解消**：原本が削除されれば平常時のデータ二重増加は避けられるが、Postgres WAL・一時領域・テーブル/索引のコピー中増加があるため「理論上データは増えない」は**切替後に限る**。旧DB/クラウド削除や過去資料の処分は上記と別承認。

## 目下のONE task
**read-only**で、`v5_data.venues`24行の旧原本との一致と、共通`boat_data`スキーマの有無・旧依存を確認する。SQL：`deploy/conoha/boat_shared_storage_preflight_readonly_20261022.sql`。現収集を止めない。次工程で共通スキーマDDL・route APIとテストを追加し、非予測中の小規模データだけを移管。今夜のレース収集やモデルを壊してまで一括切替しない。

## 初期実装（GitHubコードのみ・本番経路未変更）
- `boat_shared_storage_contract.py`: PostgreSQL `railway` の13個の主要ソースをバージョン中立な`boat_data.*`候補に一意対応、時刻根拠ルールを保持。旧 `v5_data.venues` はSTAGED_PILOTSと区別し、選手履歴用別DBとV24研究shadowを誤ってライブ入力に採用しないフェイルクローズ関数を追加。**V5日次や直前収集へまだ配線していない**。
- `tests/test_boat_shared_storage_contract.py`: 7個のオフライン単体テスト（既存Collector/DBへの副作用なし）。
- `deploy/conoha/boat_shared_storage_preflight_readonly_20261022.sql`: `public.v2_venues` とステージ `v5_data.venues` を現在時点で再照合し、`boat_data` スキーマ存在、現行VIEW依存を確認するread-only検査。**現行収集を停止・変更しない**。これが次のONE task。
- 後工程で同一DB内の`boat_data`スキーマを作り、ステージ実表を安全な短時間ロックで`SET SCHEMA`するコードと、既存の`v5_core_read_routes.py`/`v5_daily_table_routes.py`/`v5_realtime_table_routes.py`/`v5_k_result_routes.py`/DB upsert/DDL互換を統一してから、物理共通テーブルを実運用にする。名称の置換だけでは未完成。

## 2026-10-22 22:42 — 共通schema作成と読書きの静的互換
- ConoHa `railway.boat_data` の空schemaはユーザーのSQL結果で作成成功。venue stage 24行は`v5_data.venues`のまま、`boat_data.venues`はまだ未作成。旧view/write/timerは変更なし。
- 旧core/daily/read/writeが`v5_data.venues`というステージ名をopt-inで参照することが判明。安全に共有先へ移管するため、`v5_daily_table_routes.py`へ`shared_venues_v1` profile（既存確認+追加確認を共に要する3ゲート）、`db_pg.py`に引用識別子、`v5_core_read_routes.py`にvenues専用の読取許可を追加。新`tests/test_v5_shared_venues_route.py`は7つのオフラインテスト。**どのフラグもONにしておらず、現行稼働は旧データのまま**。
- 次に夜間収集稼働や実環境のroute flagsを検査してから、ステージ表のメタデータ移動を別途承認する。`v5_data.venues`を消してしまうと未確認のopt-in経路が壊れ得るため、テスト前の即時`SET SCHEMA`は行わない。
