# ConoHa移行前 4DB暗号化バックアップ — 安全ゲート（2026-10-14）

**対象**: `ops/backup/railway_pg_to_drive_stream.sh`。対象ラベルは旧V3=`v3`、履歴=`archive`、V4本番=`v4`、V5研究=`v5`。**最新DBのバックアップ0・外部SHA/フル復元0**。旧2026-10-01 CMS ZIPは別物であり、現在の4DBの保護は代替しない。

## 操作モードと接続の有無
- 引数・秘密情報なしで実行すると**`plan`（既定）**：`BACKUP_STATUS=NOT_EXECUTED`、DB/Drive/ConoHa通信ゼロ。
- **`validate`**：指定DB名・ホスト・ポート・TLS、復元用公開鍵、SHA256ピン、PG18クライアント等の**ローカル静的確認のみ**。DB・Drive APIへアクセスしない。ダミー資格情報を使う回帰テストは `test_railway_pg_to_drive_stream_offline.sh`。このファイルは2026-10-14に隔離Linuxで**14/14 PASS**、ただし実DB/実age/Drive通信は未試験。
- **`preflight`**：Railway DBのSELECTによる読取接続とDriveのアクセス確認が発生する。**`BACKUP_CONNECT_APPROVED=YES` と `BACKUP_NETWORK_COST_APPROVED=YES` が必要**。休止V3のwakeやRailway通信/稼働費の可能性がある。事前承認無しに実行しない。
- **`execute`**：上記に加えて `BACKUP_EXECUTE_APPROVED=YES` と `BACKUP_RESTORE_KEY_VERIFIED=YES` が必要。後者は**本人秘密鍵での実`age`暗号化・復号ラウンドトリップ成功時のみ**。未検証でYESと偽らない。実際のPG18/age/rclone環境準備、Google OAuth本人認証、費用・DB正体・復元先確認と個別の本人許可が前提。

## 2026-10-14：4DB宛先固定・取り違え防止（非通信）
- `ops/backup/backup_target_binding.py`は`v3/archive/v4/v5`のRailway service UUID・rclone remote名・独立のDrive folder ID SHA-256を固定。Driveフォルダの**生IDはGitHubに記録しない**。V3は別途復元用公開鍵SHAも固定。
- `preflight/execute`のみ、DB/Driveの実接続**前**に`SOURCE_EXPECTED_SERVICE_ID`と`DRIVE_EXPECTED_FOLDER_ID`を固定値と照合する。`validate`は従来通り無通信・ダミーIDも使えるため**宛先固定照合は保留**と明示。`execute`ではさらに`BACKUP_EXECUTE_TARGET_APPROVED=YES_SINGLE_<TARGET>_ENCRYPTED_SNAPSHOT`（TARGET=V3/ARCHIVE/V4/V5）が必要。**archive/V4/V5は所有者復元鍵の固定ピン未登録なので、承認値を入れても実行拒否**する。実行可能にする前に本人鍵・独立復号の検証とピン登録が必要。
- モック`ops/backup/test_backup_target_binding_offline.py`を**29/29 PASS**、4ターゲットの既知フォルダIDのハッシュ一致と誤サービス拒否を隔離Linuxで確認。**本検査は宣言されたサービスIDとフォルダIDを照合するだけ**で、Railway現DBの実体・Google Driveの認証者/所有権・復号可能性・本番書込み可否は**未検証**。オンライン検証と実バックアップは別承認。
- 従来の14件バックアップモックは前回実行済。**2026-10-14更新**：4DB固定処理を結線したGitHub blob SHA一致ソースで、隔離Linuxにて旧14件を再実行**14/14 PASS**。同じ配置で新29件も再実行**29/29 PASS**（合計43/43）。実オンラインpreflight/execute、実`age`、Google認証、復元は**未実施**。本番導入前には双方のスイートを同一ソースで再実行する。

## V3専用の鍵
- 旧V3はユーザーがiSHで作った**別用途Ed25519復元秘密鍵**に対応する公開鍵を `keys/v3_recovery_recipient_20261013.pub` に固定。
- SHA-256固定値は `da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234`（公開鍵1行・末尾改行除去）。SSH fingerprintとは別。
- 鍵・復号パスフレーズはユーザー端末から出さず、GitHubやChatGPTへ投稿禁止。**iSHでは`age`未導入、所有秘密鍵を使った実復号は未検証**。SSH鍵の暗号化対応も実`age`で確認するまで決めつけない。

## 移行停止条件
- ストリーム暗号化・SHA記録・Drive側MD5照合だけでは復元成功とみなさない。**再取得した暗号化ファイルのSHA-256照合・全体復号・隔離PG18へのフル復元・同時点データ/制約照合**が必要。
- 4 DBの移行と必要な独立バックアップが検証され、個別に本人承認されるまで、Railway本番/研究DB・cron・秘密鍵サービスは停止/削除禁止。
- ConoHaはまず2GB。必要な場合のみRailway費用解消後に追加承認して4GBを検討。V5 BUY HARD HOLD。

**2026-10-14 追記**：`ops/backup/test_age_ssh_tempkey_roundtrip.sh`を追加（持主鍵を扱わず、使い捨てEd25519鍵でage往復/改変検知する設計）。隔離Linuxで`bash -n`PASS、デフォルトは`age`が未導入のため**exit69＝実age未実行**。ssh-keygenも未導入。Python cryptographyでは使い捨てOpenSSH鍵形式/署名検証のみPASS（age互換性未確認）。ツール取得用外部ネットワークにも到達できず**成功とみなさない**。ConoHa復旧後に必要コマンドを正規手段で用意し、本人秘密鍵を持ち出さず使い捨て鍵→所有鍵往復→実DB退避/復元の順に確認。最新のNext ONE taskはcurrent compact handoffを優先。
