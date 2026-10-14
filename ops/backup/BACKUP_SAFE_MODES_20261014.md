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

## 2026-10-14：バックアップ本体との結合テスト
- `ops/backup/test_backup_preflight_integration_offline.py`：GitHub blobと隔離Linuxテスト済ファイルのSHA一致、Python `unittest` **32/32 PASS**。本体スクリプト＋宛先固定プログラム＋公開鍵を一時ディレクトリへ複製し、Driveフォルダhash**だけ**を合成IDのhashへ置換。実パスワード、実Drive ID、本人秘密鍵は使用しない。
- `pg_dump`/`psql`/`age`/`rclone`は外部処理拒否モック。V3/archive/V4/V5それぞれに対し、サービスID誤り・他DBのID・他DBフォルダ・費用/対象承認不足は**外部ツール起動前に拒否**。正しい模擬`preflight`は宛先固定を通過後、`rclone listremotes`のモックで停止し、**DB接続・Google認証は行わない**。
- `execute`も本人承認がない経路を拒否。archive/V4/V5は復元鍵ピン未登録のため、対象別承認の文字列を入力しても停止。V3の実フルバックアップ、暗号化、ストレージアップロード、独立復元は**未実施**。有効な模擬設定が通ったことは**実所有者・Railwayサーバーの真正性の証明ではない**。
- **実施済み**：途中中断・転送失敗の受入れ拒否試験は下記11件の結果を参照。実通信・実DB・CIジョブ無し。

## 2026-10-14：転送途中失敗・完了マーカー対策
- `ops/backup/railway_pg_to_drive_stream.sh`は既存`.dump.age.uploading`→暗号化済み本体のMD5照合→`.sha256`出力→本体の最終名昇格/一覧確認**後に限り**、新たに`.ready.uploading`を作り、最後に`.ready`へ昇格する。どの段階でも失敗すれば`BACKUP_UPLOAD_DONE`を出さず終了。失敗ファイルは自動削除しない。
- `ops/backup/test_backup_upload_failures_offline.py`を追加。模擬`pg_dump`/`age`/`rclone`で、実バックアップ処理の**転送段階を取り出し**、1成功＋10異常の**11/11ローカルテストPASS**（pg_dump/age失敗、転送中断、遠隔MD5不可/不一致、sidecar失敗、本体昇格/一覧失敗、`.ready`作成/昇格失敗）。外部通信・実DB・実age・本物のDriveを一切使用していない。**本体の前段認可から最後までの実データEnd-to-End試験ではない**。
- 本体の最終名`.dump.age`と`.sha256`が存在しても、`.ready`無しなら**未完了**として取り込まない。復元手順 `ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md` で3ファイルとSHA一致が必須。`.ready`は「転送完了」目印であって**復号・全件復元・ROIの証明ではない**。
- **実施済み**：3ファイルのオフライン受入れ検査を作成・21件PASS（次節）。今後の順序はcurrent compact handoffの「Next ONE task」を優先。

## 2026-10-14：暗号化バックアップ3ファイルのローカル受入れ検査
- `ops/backup/verify_backup_bundle_offline.py` は**ローカル読取専用**、Python標準ライブラリ。 `.dump.age`／`.sha256`／`.ready`の3点セット、指定対象（V3/archive/V4/V5）、SHA256全体照合、sidecarとmarkerの同一性、最終名/日付、一時`.uploading`残存・シンボリックリンクを確認。不合格なら終了コード2で拒否。暗号化ファイルはチャンク読込でメモリ使用量を抑える。実DB/Drive/通信/鍵なし。
- `ops/backup/test_verify_backup_bundle_offline.py` を隔離Linuxで**21/21 PASS**。GitHub blob SHAはテスト済みローカル`git hash-object`と2ファイルとも一致。**実`age`復号、Googleアカウント所有者、実ファイルの独立再取得、隔離PostgreSQL18フル復元は未検証**。SHAおよびマーカーを一斉に偽造された場合の真正性確認にはならない。
- 詳しい使い方・復元条件は `ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`。**最新4DBバックアップ・復元の実績は引き続き0/4**。

## V3専用の鍵
- 旧V3はユーザーがiSHで作った**別用途Ed25519復元秘密鍵**に対応する公開鍵を `keys/v3_recovery_recipient_20261013.pub` に固定。
- SHA-256固定値は `da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234`（公開鍵1行・末尾改行除去）。SSH fingerprintとは別。
- 鍵・復号パスフレーズはユーザー端末から出さず、GitHubやChatGPTへ投稿禁止。**iSHでは`age`未導入、所有秘密鍵を使った実復号は未検証**。SSH鍵の暗号化対応も実`age`で確認するまで決めつけない。

## 移行停止条件
- ストリーム暗号化・SHA記録・Drive側MD5照合だけでは復元成功とみなさない。**再取得した暗号化ファイルのSHA-256照合・全体復号・隔離PG18へのフル復元・同時点データ/制約照合**が必要。
- 4 DBの移行と必要な独立バックアップが検証され、個別に本人承認されるまで、Railway本番/研究DB・cron・秘密鍵サービスは停止/削除禁止。
- ConoHaはまず2GB。必要な場合のみRailway費用解消後に追加承認して4GBを検討。V5 BUY HARD HOLD。

**2026-10-14 追記**：`ops/backup/test_age_ssh_tempkey_roundtrip.sh`を追加（持主鍵を扱わず、使い捨てEd25519鍵でage往復/改変検知する設計）。隔離Linuxで`bash -n`PASS、デフォルトは`age`が未導入のため**exit69＝実age未実行**。ssh-keygenも未導入。Python cryptographyでは使い捨てOpenSSH鍵形式/署名検証のみPASS（age互換性未確認）。ツール取得用外部ネットワークにも到達できず**成功とみなさない**。ConoHa復旧後に必要コマンドを正規手段で用意し、本人秘密鍵を持ち出さず使い捨て鍵→所有鍵往復→実DB退避/復元の順に確認。最新のNext ONE taskはcurrent compact handoffを優先。
