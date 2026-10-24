# V5本体バックアップ対象・証拠採取チェックリスト（2026-10-24）

**GitHub設計のみ／ConoHa未調査／外部転送未実施／NO-GO。** 本書は実機で確認する**候補と検査条件**であり、記載パスの存在・保全完了を保証しない。現行V5/旧collector/DB/cron/timers/VIEW/既存バックアップを変更しない。

基準資料：[V5外部バックアップのfail-closed計画](V5_EXTERNAL_BACKUP_FAIL_CLOSED_PLAN_20261024.md)、[2DBローカルdump/SHA256](CONOHA_LOCAL_BACKUPS_20261024_CHECKSUMS.md)。旧V3/V4用バックアップ保存先は新たなV5用世代から分離し、上書き・削除を禁止。

## 1. 実機read-onlyで採取するインベントリ（すべて未確認）

| ID | 対象・候補 | 調査して残す証拠 | 完了判定 |
|---|---|---|---|
| R01 | 実行ルート候補 `/opt/boat-ai-v5` と `/opt/boat-ai-collector`、その他 `systemd ExecStart` が参照する実パス | ディレクトリの存在、所有者、symlink実体、コードと実起動場所の対応 | **部分確認：2ルート実在（11:09）** |
| R02 | Gitリポジトリとデプロイ状態 | 各実行ルートの現在のcommit SHA、Git管理有無、作業ツリー差分/未追跡の**有無のみ**、ブランチ/タグ。GitHub `main` と同一とは決めつけない | **部分確認：V5 Git HEAD・collector非Git（11:09）** |
| R03 | 実際に稼働するV5本体/collector・ラッパー・起動モジュール | 対象ファイルの相対パス、サイズ、SHA-256、取得時刻、対応するGit commit、復元対象範囲。手作業修正・管理外スクリプトを漏らさない | **未調査** |
| R04 | 依存ランタイム | Python実行ファイル・版、virtualenv位置、`requirements/lock/pyproject`有無、必要ライブラリ/システムパッケージの**バージョン一覧（秘密値なし）**、PostgreSQL/OS版 | **未調査** |
| R05 | `systemd` のV5関連`.service/.timer`、drop-in、override、masked/enabled | **名前と稼働・有効化状態、実パス**。ExecStart・Environment・EnvironmentFileの実際の値は画面/GitHubへそのまま貼らない。定義の安全な赤塗り複製の保全手順を設計 | **未調査** |
| R06 | cron、collector shell wrapper、timer時刻、ロック・排他/連続実行制御 | 仕組みの有無・対象unit/ファイルの場所、日次処理・forward-window・midnightとの関係。動作中timerを停止・無効化しない | **未調査** |
| R07 | DB接続・設定・Secrets | 必須環境変数の**キー名のみ**、参照している設定ファイルの**有無とアクセス権だけ**、安全な復旧先/鍵保管先の手順を別の秘密管理場所に確保。トークン、URL内認証、パスワード、秘密鍵、`rclone.conf`、`.env`の値をGitHubやTermius画面に表示しない | **未調査** |
| R08 | PostgreSQLロール/拡張/SCHEMA/DB互換・起動後の依存 | 復元に要るPostgreSQL版、必要拡張名・ロール名・権限の再設定設計（秘密情報不要）、2 DBの相互依存・取得時点 | **未調査** |
| R09 | 永続化されるV5固有の非DB状態 | ローカルファイルDB、取得カーソル、チェックポイント、研究成果、モデル、辞書、結果、ジョブの再開に必要なファイルを**存在/サイズ/必要性から判別**。ログやcacheを機械的に除外しない | **未調査** |
| R10 | 旧原本との互換・復旧導線 | `public.v2_*`原本writer・`boat_data`13 VIEW・`boat_data_stage.venues`24行と既存バックアップを保護。復旧時のsingle-writer・読取ルート・rollback手順 | **未調査** |
| R11 | V5本体バックアップ実体（後工程） | R01〜R10で選別した**実稼働**ファイル・設定の新規保全世代、件数/相対パス/bytes/SHA256のマニフェスト、復元試験ログ。GitHubコードだけでは環境の復旧証明にならない | **未実施** |
| R12 | VPS外での復旧試験（後工程） | 新V5専用保存先から**再取得したバイト**のSHA256、隔離環境で起動定義/collector/DBへの接続まで検証、BUY無効、検証後隔離環境清掃を証明 | **未実施** |

## 2. 機密値/負荷のガード
- 最初の調査は**存在・メタデータのみ**。実行中スクリプト、DB、原本データ、設定の内容は読み書きせず、転送もしない。`systemctl cat`、`env`、`printenv`、`rclone config dump`、`git remote -v`、`.env`全文、`ps e`を無加工で端末出力しない（認証情報漏えい防止）。
- GitHubに保存するのは**キー名/必要性/機密値を安全に再設定する手順への参照**だけ。認証値やファイル内容・秘密のパスをそのままコミットしない。鍵/認証値は別の安全な秘密管理先に保管し、復元演習で取得できることを後日確認。
- 候補ディレクトリの下を最初から再帰的に全走査しない。`systemd`の起動経路・対象ルートを絞ってから、1回1コマンドで省資源監査。新規バックアップは独立世代・no-overwrite・権限最小化・転送後再取得SHA256確認を必須とする。
- 本体保全とDB保全は**同じ一貫復旧点のセット**として設計する。現在の`railway.dump`と`boat_history_archive.dump`は別時刻のローカルコピーであり、そのまま本番切替保証に使わない。
- ConoHaのOSに再起動要求があるが、稼働collectorへの影響を避け、メンテナンス計画・別承認まで再起動しない。
- Google Drive `v5_gdrive`は2026-10-24 00:09にAPI 403レート制限。接続先の独立性未確認。無断API再試行・アップロード・V3/V4上書きは禁止。

## 3. 調査後の保全完了条件
1. R01〜R10の**実機結果**が揃い、対象／除外理由／秘密の復旧経路をレビュー。GitHubの現行コードと実稼働物の差分が説明できる。
2. 新世代にV5本体・必要なDB/履歴・設定定義・復元マニュアルを**元の構造が再現できる状態**で保全し、ファイルマニフェストのバイト数とSHA256を取得。
3. V5専用の**独立したVPS外保存先**に既存世代と衝突しない名前で保存。再取得した全バイトを照合し、VPS外隔離でV5起動・DB整合・collectorの安全な復旧を検査。
4. 稼働中の収集/正本/VIEWには切替操作をしていないことを証明。独立保全が成功しても、差分同期・全writer確認・本番切替とBUYは別の承認が必要。

**状態：CHECKLIST_CREATED_ONLY / R01〜R10 NOT_AUDITED / R11〜R12 NOT_EXECUTED / EXTERNAL_BACKUP_NOT_VERIFIED / CUTOVER_0_OF_13_NO_GO**

**10/24 11:09 Termius確認**：`/opt/boat-ai-v5`は存在・Git YES・HEAD `504b61138e3aaae547688194652e7022c196bfc4`。`/opt/boat-ai-collector`は存在・Git NO。後者はGitHubのコピーでは復元できない。実際のファイル・設定の保全は未実施。

**GitHubリポジトリ肥大化の安全整理**：[Issue #582](https://github.com/kenshoushouri-cloud/boat-ai-v2/issues/582)で追跡。read-only容量/重複の計測→現行collector/systemdの参照照合→独立バックアップ/復元後に分割PR・別承認。現時点でコード削除・履歴改変なし。

**10/24 11:15 確認**：Git管理外collector直下は2ディレクトリ（`__pycache__`、`refund_evidence`）＋9ファイル（`backfill_20261017.py`、`backfill_20261017.py.bak_20261019`、`collect_refund_evidence.py`、`daily_v5_safe.sh`、`db_pg.py`、`refund_boats_parser.py`、`refund_pending_20250701_20261005.txt`、`refund_targets_20250701_20261005.txt`、`repair_month_all_pg.py`）。存在のみ確認。Git管理外のファイルが実稼働に必須の可能性があるため削除厳禁。

**10/24 11:19 read-onlyメタデータ**：直下9ファイル計114031 B（約111KiB）、全root:root。`daily_v5_safe.sh`637B/750、`collect_refund_evidence.py`1672B/750、その他7ファイル644。`refund_evidence` 700、`__pycache__` 755。dir自身の4096Bは配下容量ではない。実内容・稼働参照・バックアップ未確認。

**10/24 11:21 Termius**：`refund_evidence/`=2.2M、`__pycache__/`=24Kを低優先度・15秒のread-only `du`で確認。成功マーカー`COLLECTOR_DIR_SIZE_READ_ONLY_PASS`。dirの内容は未確認。9ファイル114031Bを加えた全体は数MiB、初回保全ではどちらのdirも保持。

**Next ONE task：** Git管理外collector全体をConoHa内の新規root-only tarに保全し、TOC・SHA256を確認。実復元とVPS外保全は別工程。
