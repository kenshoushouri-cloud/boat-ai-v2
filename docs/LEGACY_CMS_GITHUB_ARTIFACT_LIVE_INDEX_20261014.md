# 旧CMS GitHub Actions成果物の実棚卸し（2026-10-14 JST / read-only）

**重要訂正：従来compactの「旧CMS成果物3件」は不完全。10/14にGitHub Actions実行IDから未失効の暗号化成果物を**計4件**確認。Google Drive Aにはうち1件だけが存在（同サイズのZIP）。残り3件は未保全。**同名のv2が異なる実行で2件**ある。GitHub metadataのSHA-256は**artifact ZIPコンテナ**のdigestで、`.dump.cms`ファイル自体のSHAやDriveでの実コピーの検証を代替しない。

## GitHub Actionsのlive確認値

|Run ID|Artifact ID / 名|ZIPサイズ(bytes)|GitHub ZIP SHA-256 (digest)|失効予定UTC|Drive A|
|---|---|---:|---|---|---|
|36796803697|11133689245 / `boat-ai-pre-hobby-20261001`|301949989|`04ed2d614ac5808a555a84a55547a87e5984dbf68423ae5d70df48dbbc0113e4`|2026-12-30 00:33:55|未確認/専用V3フォルダには無し|
|36810769041|11138584090 / `boat-ai-pre-hobby-restorable-20261001-v2`|302572594|`a2676ca0beb24853b7076088140641ca099c1adc92982c3dcf5f176f3003ea3a`|2026-12-30 03:29:50|未確認/専用V3フォルダには無し|
|36811231115|11138759678 / `boat-ai-pre-hobby-restorable-20261001-v2`|302612349|`4f9f007e0e6ed6dce77a456c2741242f8aa5574c2616383717c622bb5fae834f`|2026-12-30 03:35:45|未確認/専用V3フォルダには無し|
|36812386066|11139857666 / `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066`|302656753|`e9e2f99e8503529430d0e9f9e58604d2b4abee2db2185ffd190c8de88a4ba42c`|2026-12-30 03:50:55|**ZIP1件が存在、サイズ一致**、バイトSHA/独立復元未検証|

全4件ともGitHubの`expired=false`をlive確認（2026-10-14）。すべて2026-10-01 UTC作成の過去実行。失効はGitHub提供の予定値であり、永久保存を保証しない。**計4件 / Drive Aで存在確認1件 / 未保全候補3件**。約907,134,932 bytesの追加ZIP保管容量が必要。ただしDrive Aの残量/接続経路/転送費は未実測。Drive Aの**専用V3フォルダ内だけを列挙**した結果なので、他フォルダに複製が全くないと断定しない。

## 鍵と復元性の取り違え防止

- `.github/workflows/railway-postgres-pre-hobby-backup.yml`はOpenSSL CMS/AES-256で暗号化したダンプとmanifestをArtifact保存する設計。過去のZIP存在だけでは現在の鍵復号や全復元を証明しない。
- `.github/workflows/railway-postgres-isolated-restore-drill-v2.yml`は**各実行時に新しいRSA鍵ペアを生成し、同じRailway鍵サービス内の変数 `ARCHIVE_CMS_PRIVATE_KEY_B64` へ書き込む設計**。2つのv2 ZIPは名前が同じでもSHA-256とサイズが異なる。後の実行が前の復元鍵を上書きした可能性があり、**両方restorableと断言禁止**。現時点の原本鍵がどれに一致するかは未確認。元Railway鍵サービス・旧CMS鍵は保護し、無断の削除/変数変更/鍵内容表示なし。
- `.github/workflows/railway-postgres-restored-parity-expansion.yml`のv3-parity鍵は`ARCHIVE_CMS_PRIVATE_KEY_B64_PARITY_<RUN_ID>`の**run専用変数**を鍵サービスに設定する設計。ただし実際の保存・復号可能性・現在の鍵の有無は確認していない。ZIPに入った公開証明書だけで復号はできない。
- **旧CMS artifactは現行V3/V4/V5/archive DBのバックアップではない**。4DB実暗号化退避0/4、独立PG18フル復元0/4のまま。V4本番・Railwayの4DB原本の停止削除は禁止。

## 実転送前のゲート

1. 既存Google A V3フォルダのZIPは上書き/改名/移動しない。本人のDrive A残量、保存先非共有、同名v2衝突防止（**run IDをファイル名に付ける**）を確認。
2. **未保全3件（約907MB）を一括ではなく1件ずつ**GitHubから保存し、Drive Aへ本人が承認した経路で転送する。GitHub downloadとDrive uploadの制限・帯域/通信費・保存容量を確認してから実行。所有者の認証/復元鍵をチャットやGitHubに送らない。
3. 転送済みZIPを再取得してZIP全体SHA-256（上記GitHub digest）を照合し、`.cms`を正しい本人鍵で全体復号、隔離PG18への復元/同時点比較を別途検証。復元不可だったv2も、鍵の追跡が終わる前に勝手に削除しない。
4. 2026-12-30 UTCの失効より前に保全判断が必要。V5のConoHa未復旧問題や`age`認証、4DBの転送は**別作業**。本ターンは**GitHub/Drive read-onlyメタデータ確認のみ**で転送・Railway・Secrets・cron・課金・BUYなし。

## Next ONE task
ConoHaサポート返信/既存2GB到達を最優先確認。未復旧なら**GitHub Artifact→Google Drive Aの1件転送について、使用可能な連携アクションの容量制限とDrive残量をread-onlyで照合**し、本人の明示承認と費用確認後にだけ小さく1件ずつ保全。公開handoffにはDrive実ID、Googleアカウント情報、秘密鍵を書かない。
