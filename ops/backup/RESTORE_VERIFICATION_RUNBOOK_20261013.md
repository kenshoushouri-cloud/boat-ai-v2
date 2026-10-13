# V4/V5 Google Driveバックアップ — 独立復元検証手順（2026-10-13）

**状態: 手順書作成のみ。バックアップ、復元、Google Drive実通信、Railway変更は未実施。**
目的は**完全復元を実測するまでRailwayの元データを残す**こと。ChatGPTのGoogle Driveプラグイン連携はrcloneのOAuth認証には使えない。iPhoneのみ、ConoHa VPS管理画面は未復旧。

## 0. 対応関係・保護条件（取り違え禁止）

|対象|Railway原本サービス|個人Google Drive保存先|復元テスト先|
|---|---|---|---|
|旧V3|postgres-hobby-fullhistory-candidate-v3|Google① / boat-ai-v3-temp-202610|独立テストDB `boat_ai_drill_v3_*`|
|履歴アーカイブ|postgres-history-archive|Google① / boat-ai-history-archive-temp-202610|独立テストDB `boat_ai_drill_archive_*`|
|V4本番|Postgres-EKp2|Google① / boat-ai-v4-temp-202610|独立テストDB `boat_ai_drill_v4_*`|
|V5主力研究|postgres-hobby-fullhistory-candidate-v4|Google② / boat-ai-v5-temp-202610|独立テストDB `boat_ai_drill_v5_*`|

- **一度に1DBだけ**。先に旧V3と履歴アーカイブの小規模復元ドリルを行い、続けてV4本番・V5主力の保護を進める。休止旧V3を無断起動しない。V4本番・必要cronは停止/削除しない。
- 復元先は**本番/研究用のRailway DBでも、運用開始予定の本番VPS DBでもない**。安全な隔離PG18インスタンスと、名前を決めた**空のテストDB**が必須。
- 追加のVPS容量、メモリ、DBサービス、外部転送、書込・費用が発生する作業は**その直前にユーザー承認**。ConoHaのVPS復旧とOS/SSH保護を先に済ませる。
- 2026-10-13時点、バックアップスクリプト `ops/backup/railway_pg_to_drive_stream.sh` は**モック検証のみ**。実DBバックアップを勝手に始めない。

## 0.1 別途保全が必要な過去の暗号化スナップショット鍵（2026-10-13 read-only監査）

- live Railway `archive-restore-key-20261001` サービスの**環境変数名のみ**に `ARCHIVE_CMS_PRIVATE_KEY_B64` と `ARCHIVE_CMS_PRIVATE_KEY_B64_PARITY_*` を確認。値・秘密鍵は表示も出力もしていない。
- GitHub `.github/workflows/railway-hobby-fullhistory-v3-parity-readonly.yml` と `railway-hobby-v4-final-sync-safe.yml` 等が、この鍵を利用して**過去のGitHub Actions保管 `.dump.cms` アーティファクト**を復号・復元する設計であることをコードで確認。これらは今回新設の`pg_dump | age | Google Drive`方式とは**別の旧世代のバックアップ**。Google DriveへPostgreSQL DBをコピーしてもCMS秘密鍵やActions上の過去アーティファクトが自動保全されるわけではない。
- **現時点でarchive PostgreSQL DBのデータ自体がこの鍵で暗号化されていると確認できたわけではない。** 鍵サービスと`postgres-history-archive`は別サービス。名前から同一用途と決めつけない。
- 旧CMSアーティファクトについては、実在・有効な保持期限・`manifest`・公開証明書・秘密鍵との対応・独立復元可能性を**別途**確認。GitHub Actions artifactsの保持期限切れもあり得るため、記録されたrun番号や成功ログだけで存在/復元可能と判断しない。
- **削除禁止**: `archive-restore-key-20261001`サービス、復元に関係する鍵変数、対応する旧CMSアーティファクト、V3/履歴archiveのDBは、用途・独立コピー・復元検証が終わり、ユーザーが個別に承認するまで削除しない。鍵やOAuth秘密をGitHubドキュメント/チャット/公開Driveへ載せない。
- 主要8サービス（historical-recent-form-runner、historical-backfill、cron-data-prepare、cron-learning-all、candidate-v4 DB、archive-restore-key、backtest-analysis、cron-final-check）の環境変数**名**を調査。通常cronの7件に明示的な`ARCHIVE_DATABASE_URL`名は見当たらなかったが、共通`DATABASE_URL`の実値は非開示であり、GitHubの手動アーカイブworkflowもあるため、**これをもって依存なしと判断しない**。元DBの停止判断前に別途依存調査が必要。
- 今回はread-onlyのAPI・GitHubコード調査のみ。Railwayサービス変更/再起動/起動・dump・Drive転送・復元・削除なし。

## 1. アーカイブ候補の受入れ（まだ本番実行しない）

1. 各Googleアカウントの本人認可がrclone側で完了し、対象remotesの`root_folder_id`がそれぞれの非共有フォルダと一致することを確認。**OAuth秘密、DB URL、復号秘密鍵はGitHub/チャットに貼らない**。
2. ファイル名が `boat-ai-v3-...dump.age`、`boat-ai-archive-...dump.age`、`boat-ai-v4-...dump.age` または `boat-ai-v5-...dump.age` で、`.uploading`ではないこと。対応する `.sha256` が存在すること。
3. テスト環境の**DB専用ボリューム外**に暗号化アーカイブを一時取得し、対応するSHA-256をファイル全体に対して再計算・比較。Google Drive内のMD5一致やファイル一覧掲載だけでは代替不可。
4. 受信側で `age` による**ファイル全体の認証付き復号**がエラーなしに終了すること。秘密鍵はRailwayから独立した安全な場所で保持。復号ファイルは極力作らずパイプで処理する。
5. `pg_restore -l`でPostgreSQLカスタム形式のTOCを確認（**TOC読取だけでは全データの健全性は証明できない**）。
6. PostgreSQL18の`pg_dump`は1 DBの論理バックアップ。ロール/パスワード、テーブルスペース等の**クラスタグローバル情報は含まれない**。独立した権限・拡張機能・設定/秘密変数・cron/通知の保全台帳が必要。`--no-owner --no-acl`を指定しているため原所有者/ACLの再現は別途評価する。

## 2. 別環境でのフル復元（承認後のみ）

事前条件を**すべて確認できない時はSTOP**:
- 独立したPG18が実際に起動し、接続先がそのインスタンスの**専用localhostポート**であることを確認（Railway/既存の本番VPS DBではない）。ネットワーク経路と`inet_server_addr()`、`inet_server_port()`、`current_database()`を照合。
- `RESTORE_TEST_DATABASE_URL`はユーザー承認済みの `boat_ai_drill_v3_*`、`boat_ai_drill_archive_*`、`boat_ai_drill_v4_*` または `boat_ai_drill_v5_*` の**空DBだけ**を指す。テスト用所有者以外の権限を与えない。接続文字列/パスワードをログ・チャットに出さない。
- `PG18`対応`pg_restore`と`age`、暗号化アーカイブ、復号秘密鍵が利用可能。容量・空きディスク/メモリ/時間/費用を予測してから実施。V5はRailway DB実測約4.9GBだが、論理dump・復元サイズは未測定。
- 別途本人が**今回の復元実行を承認**。不明な拡張やロール依存で失敗すれば、成功扱いにしない。

**実行例（事前条件を人手で満たした隔離環境のみ・実行済みではない）**:
```bash
set -euo pipefail
# AGE_IDENTITY_FILE, ENC_BACKUP_FILE, RESTORE_TEST_DATABASE_URL は安全な環境でのみ設定
# 外部から取得した暗号化ファイルに対し、別途SHA-256照合と全体復号チェック済み
age -d -i "$AGE_IDENTITY_FILE" "$ENC_BACKUP_FILE" \
  | pg_restore --exit-on-error --no-owner --no-acl \
      --dbname="$RESTORE_TEST_DATABASE_URL"
```
- `--clean`、`--create`、`--if-exists`、復元先削除や本番DBへの接続を**使用しない**。並列`--jobs`もストリーミング復元時に使用しない。
- `pg_restore`が終了コード0となり、`pipefail`により`age`側の失敗も検知した場合だけ、次の照合へ。
- エラー時は**当該テストDBのみ**調査対象にし、自動再試行・再転送・本番切替をしない。

## 3. データ/機能の一致（判定必須）

- 復元先でテーブル、行数、主要日付範囲、インデックス、主キー/外部キー制約、拡張機能、関数/ビューの存在、DB利用者の必要権限を確認。
- 対照元は**同じバックアップ時点のスナップショット/記録**。更新され続けるRailway原本の「現在値」と単純比較しない。事前に対象テーブルの行数等の基準値を保存する仕組みが未実装なら**完全一致未検証**のままにする。
- 特に`v2_odds_trifecta`、`v2_race_entries`、`v2_realtime_odds_snapshots`、2025-07以降の履歴/推定に必要な表を検証。V5の欠損/PENDING/0券は削ったり補完していないことを確認。
- V4は本番参照が正しくできることを、V5は**読み取り専用の代表的な推論/バックテスト再現**ができることを別途確認。購入処理は**HARD HOLD**。
- 少なくとも`pg_restore`エラー0、総テーブル件数・主要表/日付範囲一致、代表照合、cron/環境依存リスト確認、暗号化ファイルの独立保管・秘密鍵取出し可能性まで証跡化。結果にレースデータ/秘密情報を含めない。

## 4. 判定表

|段階|PASS条件|現状|
|---|---|---|
|S0 保存先・DB対応|A/V3・archive・V4、B/V5の本人認可とID一致|未完|
|S1 暗号化コピー|完全な実バックアップがGoogle Driveに存在|未実施|
|S2 遠隔全体照合|再取得した暗号化ファイルのSHA-256一致|未実施|
|S3 独立復号|全体復号、TOC可読、改変時エラー|未実施|
|S4 独立フル復元|隔離PG18の空DBにエラーなしで復元|未実施|
|S5 データ/機能一致|原本の同時点基準値、制約、代表機能を照合|未実施|
|S6 切替/縮退判断|V4本番保護・V5検証、費用見積り、ユーザー再承認|保留|

**S0〜S5全PASSまでは、バックアップ「完了」や復元「検証済み」とは報告しない。Railway原本削除・cron停止・VPS本番切替は禁止。**

## 5. 直近のONE task

ConoHaの既存VPSはサポート返答待ち。iPhoneの無料iSHにAlpine版rcloneを導入し`rclone version`だけ確認する案を先行。本人OAuth同意はその後。実PG18の復元先は未確保で、VPS未復旧ならRailwayに復元用サービスを無断追加しない。
