# ConoHa／rclone OAuth待ちの代替案：Railway → GitHub Actions → 私有Google Drive
更新日: 2026-10-13 / 状態: **設計のみ、実接続・データ取得・課金操作なし**

## 目的
iPhoneだけで旧V3、履歴archive、後続V4/V5の**現時点DB**を独立した暗号化スナップショットとして保存できる手段を用意する。ConoHa VPSログイン問題やGoogle Cloud desktop OAuthのSafari loopback失敗を回避。GitHub Actions artifactは最終保管先ではなく、本人がSafariから各Google Drive専用フォルダに保存するための一時中継。

## 根拠（公式）
- Railway CLI `railway connect SERVICE --tunnel-only` は公開TCP proxyの無いPostgresをSSHでトンネル可能。ただし接続先詳細に機密情報が出るため、そのままCIログに出さない。
  https://docs.railway.com/cli/connect
- Railway CLI `railway ssh [options] -- COMMAND` はスクリプト/CIで標準出力を非PTYにできる。ただし**登録済みRailway SSH鍵が必要**。GitHub Actions上の利用可否は未検証。
  https://docs.railway.com/cli/ssh
- PG18の`pg_dump -Fc`をRailway DBから読み取り専用取得すること自体は公式の方式。dump/restore版・配布環境は別途固定する。
  https://docs.railway.com/guides/postgres-backups-restores

## 実装候補と必須ゲート
1. **現在の対象の同定**: live Railway service ID、deployment状態、DB identity、PG major、DB UUID/host-portをread-onlyで別照合。旧V3は SLEEPING であり、実際の接続では起動/CPU/network課金が発生する可能性がある。archiveは外向けTCP無し。単なるサービス名でV4/V5や旧V3を決めつけない。
2. **経路確認（実行前承認）**: Railway SSH鍵登録状態およびGitHub Runnerから対象DBへの非対話接続可否。GitHub secretにSSH private keyを預けるかは本人の明示同意と最小権限を必要とする。接続テストは`SELECT current_database(),current_setting('server_version_num'),pg_is_in_recovery()`など小量・read-onlyのみ。Railway Agent/AIは禁止。新規サービス・proxy・DBは作らない。
3. **暗号鍵の独立性**: 新規の`age`受信先公開鍵を本人が管理。復号秘密鍵はRailway・GitHub・一時成果物に置かず、少なくとも二つの安全な場所にバックアップ。既存の`ARCHIVE_CMS_PRIVATE_KEY_B64*`は旧CMS復号用で別体系。公開鍵の指紋を事前承認。**秘密鍵がRailwayにしか無い旧方式だけに依存しない**。
4. **暗号化した一時成果物**: 外部CI runner上で`pg_dump -Fc`→`age -r`→`sha256sum`→GitHub Actions artifact。平文dump、DB URL、OAuth、secret、SSH鍵をリポジトリ・ログ・公開artifactに絶対に書かない。対象別artifact名は新規／一意、再実行は手動1回のみ、artifact短期保持期限を明示。転送失敗時に完了表示を出さない。
5. **独立保存と検証**: GitHub Actions artifactを本人がiPhone Safariからダウンロード→Google AのV3専用/履歴archive専用、Google BのV5専用へ**手動アップロード**。Drive上のファイル存在・容量だけでは不十分。元ハッシュと再取得した暗号化ファイルのSHA-256照合、age認証復号、独立PG18完全復元、テーブル・行数・業務IDの照合を全対象ごとに記録。
6. **費用・操作保護**: 実ダンプ・Railway起動・GitHub Actions実行は明示承認まで行わない。DB/cron/サービス停止・削除禁止、GitHub自動CIを発火させない。大容量データのRailway通信費・WAL/CPU影響、Actions artifact容量・保存期限を事前評価。GitHub repoがpublicであっても、artifactは**暗号化済み**のみ。

## 現在の実績と非実績
- GitHubの2026-10-01の**過去CMS**旧V3関連ZIP（302656753 bytes）1件だけはGoogle Aの非共有V3フォルダへ手動保存済み。これは**現在DBのdumpではない**。
- Google Drive connector経由の303MB再取得SHA照合は256MiB制限で不可。
- この代替案によるSSH接続、現DBのdump、age鍵生成、GitHub Actions実行、Google Drive新規ファイル保存、独立復元は**0件**。
- ConoHaの2026-10-13契約・支払・設定完了の通知をGmailで再確認。サポートの新回答は確認できず、パネルアクセスはまだ未確認。

## Next ONE task
**低コスト・read-onlyでSSHが既存設定のみで利用可能か事前確認する**（先にユーザー承認が必要な実接続は保留）。証明できなければConoHaのサポート回答待ちに戻す。SSH鍵/DB秘密情報をチャットに送らせない。
