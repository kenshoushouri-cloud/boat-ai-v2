# V5 ConoHa移行前 — 4DB暗号化バックアップ・独立復元の実行前提 静的監査（2026-10-14 JST）

**判定：実バックアップ/実復元は0/4、オンライン実行HOLD。** ConoHaサポート未返信のため既存VPSへはアクセスしない。GitHub feature branchの既存2手順書・バックアップ本体・対象固定Python・iSH age手順の**計5ファイルをread-only確認した結果**。テスト再実行、DB/Drive/ConoHa/Railway接続、GitHub Actions、鍵取得、デプロイ、BUYなし。

## 対象・宛先と現状

|対象|Railway原本|外部宛先|実暗号化コピー/独立PG18フル復元|
|---|---|---|---|
|旧V3 `v3`|`postgres-hobby-fullhistory-candidate-v3`|Google A / V3専用|0/0|
|履歴 `archive`|`postgres-history-archive`|Google A / archive専用|0/0|
|V4本番 `v4`|`Postgres-EKp2`|Google A / V4専用|0/0|
|V5研究 `v5`|`postgres-hobby-fullhistory-candidate-v4`|Google B / V5専用|0/0|

いずれもRailway原本・旧CMS復元鍵サービスは削除/停止禁止。2026-10-01旧CMS artifact3件（12/30失効予定）は現在の4DBバックアップの代用不可。既存の1件のGoogle Aコピーも独立SHA・全復元は未確認。

## 既存実装のゲート（設計確認のみ）

- `ops/backup/railway_pg_to_drive_stream.sh`：引数なし既定`plan`は非通信。`validate`はローカル静的検査。`preflight`は**実Railway SELECT/Drive参照**を伴い、`BACKUP_CONNECT_APPROVED=YES`と`BACKUP_NETWORK_COST_APPROVED=YES`が必須。`execute`はさらに`BACKUP_EXECUTE_APPROVED=YES`、`BACKUP_RESTORE_KEY_VERIFIED=YES`、対象別承認が必要。実際に確認できていない同意・鍵を「YES」と偽らない。
- `ops/backup/backup_target_binding.py`：4DBの事前固定サービスUUID・専用Drive folder SHA256とrclone remoteを`preflight/execute`前に照合。ただし**宣言IDの一致は生DBの実体やGoogle所有権の証明ではない**。`validate`では宛先実照合は先送り。
- V3の復元**公開**鍵ハッシュはピン済み。ただし本人秘密鍵による実`age`復号は未検証。archive/V4/V5の復元公開鍵ピンは**未登録**で`execute`は拒否される設計。
- `pg_dump` PostgreSQL18、`age`、`rclone`、認証済みDrive A/B、TLS・ホスト・DB名の本人照合が必要。`.dump.age`/`.sha256`/`.ready`の3点が揃い、外部から再取得した全体SHAが一致しなければ受入れない。`.ready`だけでは復元証明不可。
- **独立PG18の空の隔離DB**への全体復号＋`pg_restore --exit-on-error`、元データの**同時点基準値**による行数/制約/関数/代表データの照合が必要。pg_dump論理バックアップにロール/権限/クラスタグローバル設定は含まれず、別台帳が必要。V5の約4.9GBは過去観測値で、復元必要ディスク・RAMは**現在未実測**。2GB VPSの余裕を推測せず、本番VPSへの隔離復元も禁止。
- iPhone iSHの標準apkソースでは`age`未導入。OS/repoを無承認で切り替えない。ConoHa復旧後に使い捨て鍵で実`age`往復/改変拒否→本人鍵の安全なローカル復号方法→4DB個別バックアップ/独立復元を検証する。

## 実行前の不足条件（順序付き）

1. **T0（ConoHa復旧）**：契約済み2GBのOS/IP/SSH、ディスク/RAM・課金条件をread-only実測。再購入・チャージ不可。
2. **所有者鍵・暗号化方式の実証**：使い捨て鍵で`age`往復を実測し、本人秘密鍵を外部/チャット/GitHubへ渡さず本人鍵による**全体復号可能性**を実証。archive/V4/V5の公開鍵ピンはこの後に固定。
3. **本人Drive OAuth・原本・宛先の照合**：Google A/Bの非共有フォルダ所有権、rclone remoteと固定folder hash、Railwayサービス/接続先を個別確認。休止V3 wakeやNetwork費を事前承認。
4. **1DBずつの本人承認**：暗号化dump→Drive転送→再取得SHA→本人鍵で全体復号→隔離PG18全復元→同時点データ/制約照合→個別承認。S0〜S5の全てがPASSするまで旧DB/cron/鍵は保持。

**判定範囲の限界**：本書はGitHubコードと手順の読取だけ。過去のオフラインPASSは既存文書の報告であり、本ターンはテスト未実施。実認証・保存先・DB実体・バックアップ成功の証明に流用不可。コストを事前に承認してもらうまでオンラインpreflightすら実施しない。

## Next ONE task

ConoHaサポート返信を先に確認し、復旧なら既存VPS read-only診断。未復旧なら**V3復元用公開鍵と所有者`age`復号実証の非通信・非秘密共有手順**を既存`ops/backup/test_age_ssh_tempkey_roundtrip.sh`とiSH制約から1作業だけレビュー。本人秘密鍵・環境設定変更・パッケージ導入・接続・購入なし。
