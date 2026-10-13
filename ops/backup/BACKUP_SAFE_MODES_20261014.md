# ConoHa移行前 4DB暗号化バックアップ — 安全ゲート（2026-10-14）

**対象**: `ops/backup/railway_pg_to_drive_stream.sh`。対象ラベルは旧V3=`v3`、履歴=`archive`、V4本番=`v4`、V5研究=`v5`。**最新DBのバックアップ0・外部SHA/フル復元0**。旧2026-10-01 CMS ZIPは別物であり、現在の4DBの保護は代替しない。

## 操作モードと接続の有無
- 引数・秘密情報なしで実行すると**`plan`（既定）**：`BACKUP_STATUS=NOT_EXECUTED`、DB/Drive/ConoHa通信ゼロ。
- **`validate`**：指定DB名・ホスト・ポート・TLS、復元用公開鍵、SHA256ピン、PG18クライアント等の**ローカル静的確認のみ**。DB・Drive APIへアクセスしない。ダミー資格情報を使う回帰テストは `test_railway_pg_to_drive_stream_offline.sh`。このファイルはテスト作成済み、**実行済みとは記録しない**。
- **`preflight`**：Railway DBのSELECTによる読取接続とDriveのアクセス確認が発生する。**`BACKUP_CONNECT_APPROVED=YES` と `BACKUP_NETWORK_COST_APPROVED=YES` が必要**。休止V3のwakeやRailway通信/稼働費の可能性がある。事前承認無しに実行しない。
- **`execute`**：上記に加えて `BACKUP_EXECUTE_APPROVED=YES` と `BACKUP_RESTORE_KEY_VERIFIED=YES` が必要。後者は**本人秘密鍵での実`age`暗号化・復号ラウンドトリップ成功時のみ**。未検証でYESと偽らない。実際のPG18/age/rclone環境準備、Google OAuth本人認証、費用・DB正体・復元先確認と個別の本人許可が前提。

## V3専用の鍵
- 旧V3はユーザーがiSHで作った**別用途Ed25519復元秘密鍵**に対応する公開鍵を `keys/v3_recovery_recipient_20261013.pub` に固定。
- SHA-256固定値は `da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234`（公開鍵1行・末尾改行除去）。SSH fingerprintとは別。
- 鍵・復号パスフレーズはユーザー端末から出さず、GitHubやChatGPTへ投稿禁止。**iSHでは`age`未導入、所有秘密鍵を使った実復号は未検証**。SSH鍵の暗号化対応も実`age`で確認するまで決めつけない。

## 移行停止条件
- ストリーム暗号化・SHA記録・Drive側MD5照合だけでは復元成功とみなさない。**再取得した暗号化ファイルのSHA-256照合・全体復号・隔離PG18へのフル復元・同時点データ/制約照合**が必要。
- 4 DBの移行と必要な独立バックアップが検証され、個別に本人承認されるまで、Railway本番/研究DB・cron・秘密鍵サービスは停止/削除禁止。
- ConoHaはまず2GB。必要な場合のみRailway費用解消後に追加承認して4GBを検討。V5 BUY HARD HOLD。

**Next**: テスト用スクリプトを非課金のローカルLinuxで実行してガードを確認。その後ConoHa管理画面復旧→所有復元鍵での実`age`ラウンドトリップ→小容量の暗号化DBバックアップ＋独立復元へ進む。勝手に実DBへ接続しない。
