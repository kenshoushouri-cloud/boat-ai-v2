# V5・実DB読み取りプリフライト（手動専用／未実行）

## 目的と制約
2025-07-01以降の全期間研究バックテスト前に、DBの**4テーブル・必要20列・索引prefix・SELECT権限**だけを確認する。GitHub Actions／Railway Agent／新サービスを起動しない。**実DB照会は現時点で0回**。V4/candidate-v4 DBへ接続しない。

既存の`ops/v5_seven_day_archive_db_preflight_readonly.sql`を、`ops/v5_archive_preflight_manual.py`がローカルの`psql`から呼ぶ。SQLのGitHub blob SHA `fa930650488d3dee2ac501f7d19fb605e9a5b3ae`が一致しない限り接続前に拒否する。スクリプトはデフォルト**DISABLED_BY_DEFAULT**。対象DBの本人申告は独立認証ではない。

## 実行条件（別作業で安全性を確認してから）
- 自身の信頼できるPC/管理端末で`psql`とPostgreSQLの**読み取り専用アカウント**を用意し、`PGSERVICE`（.pg_service.conf + chmod 600の.pgpass等）又は`PGHOST/PGDATABASE/PGUSER`で接続。公開接続ならTLS・接続先証明書を確認。**接続文字列・パスワードをコマンド引数、Issue、Actionsログ、チャットに貼らない**。
- 実際の接続先が研究用history-archiveであること、V4本番・他のPostgresでないことを別途確認。Railwayで任意SQLを直接実行できる接続は現状未提供。
- 明示的に実行を承認した場合だけ、`V5_PREFLIGHT_OPT_IN=YES_METADATA_ONLY`、`V5_PREFLIGHT_DB_TARGET=HISTORY_ARCHIVE_CONFIRMED`を指定し、`python ops/v5_archive_preflight_manual.py`を手元で実行。環境変数の対象文字列だけでは接続先を証明できない。
- 接続timeout=3秒、statement_timeout=2秒、lock_timeout=250ms、max_parallel_workers=0、session+transaction READ ONLY、単発・最大12秒。接続失敗時の詳細stderrは出さず、秘密情報を表示しない。

## 合格ではなく「検査完了待ち」
`CATALOG_RESULTS_REQUIRE_MANUAL_REVIEW`はSQL完走の意味だけ。20列の型、4表の左端索引（ready/valid/nonpartial/B-tree）、4表SELECT権限、`transaction_read_only=on`を確認し、**すべて揃うまで1日分SELECTも実行しない**。NULL返還は未確認扱い。取得時刻の原本・公式6艇出走・実ROI・Forward/BUYはHARD HOLD。

**検証済み範囲**：ローカル単体テスト7/7 PASS・構文PASS、GitHub実装 blob`aac2533e`/テスト`07814d04`一致。実psql/実DBでの動作は未確認。

**Next ONE task**：カタログ検査結果を受け取る際の合否判定・1日分read-only smoke上限（対象レース、行数・通信量・予測/結果の厳密分離）を最小設計。外部接続は別途安全確認後に実施。


## 2026-10-11 更新：推奨経路は Railway Data > Query（ローカルpsql不要）

Railwayの公式2026-03-20更新でPostgreSQLのData画面のRaw SQL Queryが一般提供済み。
1. Railwayの`boat-v2-postgres`プロジェクト、`production`、**postgres-history-archive**サービスを開き、**Data > Query**を選ぶ。**candidate-v4 / Postgres-EKp2 / v3 は選ばない**。
2. `ops/v5_archive_catalog_railway_data_query_readonly_20261011.sql`をGitHubで開き、その**SQL本文だけ**をRailway Queryへコピーして1回実行。これは単一SELECT、information_schema/pg_catalogのみ、レース表の行スキャンなし、書込なし。元の複数ステートメントpsql SQLではなく専用SQLを使う。
3. 出力は**1行**。 `check_result`, `checked_columns`(20), `checked_indexes`(4), `problem_columns`, `problem_indexes`, `problem_select_access`, `permission_to_run_smoke` のみを確認する。パスワード、接続URL、Variables、tokenは共有しない。

`SHAPE_OK_SOURCE_NOT_AUTHENTICATED`でも選択サービスの独立証明、read-onlyセッション、元データの事前真正性を意味せず、**まだ実データ取得の許可ではない**。1日smokeは次の判断までHOLD。Data > Queryが見当たらない場合はアカウント feature flagsの`Raw SQL Query Tab`を確認するが、無理な追加デプロイは行わない。

旧ローカル`psql`方法は代替策として維持するが、簡便性・低コストのため今回はRailway Data UIを優先。
