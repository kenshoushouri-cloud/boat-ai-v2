# 新競艇AI No.2 — current compact handoff（2026-10-13 夜）

最初は`docs/HANDOFF_LATEST.md`→その指定current compact→`docs/NEXT_CHAT_START_HERE.md`だけを読む。古いhandoff、PROJECT_HISTORY、長いworkflow/ログは通常参照禁止。**1回に1作業、ツール最小、短い結果と所要時間、SHA/run/容量はその作業でlive再取得**。止まった作業を重複実行しない。ユーザーは**iPhone（Safari・iSH Shell）のみ**。1手順ずつ／コピーボタン推奨。

## Next ONE task
**本人のiSHでRailway SSH鍵とは別のpassphrase付きEd25519鍵を復元専用に作成→iSH外2箇所に安全に保管→実`age`暗号化/復号自己テストを準備。** iSH は Alpine 3.14 x86、公式`apk add age`対象はv3.15以降のため、古いOSへ新しいrepositoryを混ぜない。公式ageはSSH Ed25519公開鍵にも対応し、`ops/backup/v3_to_artifact_encrypt.sh`も受け入れ可能なよう更新済み（未接続・実テスト未完）。既に登録した**Railway SSH鍵をage鍵として使い回さない**。秘密鍵・パスフレーズ・DB URL・Google OAuth JSON/tokenをチャット/GitHubへ投稿させない。必要ならConoHaサポート回答待ち。
その次に、承認を得て旧V3のみGitHub Runner側で**事前接続検証**→暗号化バックアップ→Google A外部保管→独立復元。履歴archiveは公開TCPなしで別経路が必要。**現DB dump・独立復元は未実施**。

## Source /目的と最重要ガード
- Repo `kenshoushouri-cloud/boat-ai-v2`、作業ブランチ `feature/v5-prior-day-counter-test-20261011`。**main・V4本番を無断変更/マージしない**。V5強化型を主力として構築（旧V4買い目の安易な流用禁止）、将来は自動購入。しかし**BUY HARD HOLD**: Forward/ROI実績未検証、購入操作は最後・別承認。LINE仮候補通知不要。
- 2025-07-01から全保有期間のデータを可能な限り保持。精度悪化でモデルに不採用でもデータ自体は保管。締切前に観測・凍結されていない過去展示/オッズを当時の証拠として偽装しない。返還不明・PENDING・NO_BUY・欠測は勝手に補完/母数除外しない。
- V5 2025-07-01〜2026-10-10の67週間窓は計画済み**実バックテスト0/67**、買付ROI/実収益は未検証。7/2は180レースに対しオッズ238券不足でPENDING。目標+5万円/月は未証明。
- ChatGPT＋Railway費用計月6,000円以内（理想5,000円）。Railway月$10–12目標、$15警戒、$20上限目標（なるべくさらに安く）。VPS/外部保管/移行重複期間も総額で評価。Railway Agent/AI禁止、無用なCPU/RAM/Network/WAL/高コストCI禁止。**V4/V5/DB/サービス/課金/バックアップ実行は都度承認**。

- **2026-10-14 00時時点の復元鍵進捗**: iSHでRailway接続用とは別のpassphrase付きEd25519鍵を作成、`ssh-keygen -y`で解除成功。秘密鍵は本人端末iSH原本・iPhoneローカルコピー・iCloud Driveコピーが保存でき、利用者がiCloud.comから表示確認。**外部復号テスト未実施**、iCloudの同一アカウント・秘密鍵パスフレーズの独立保管を継続。公開鍵だけを`ops/backup/keys/v3_recovery_recipient_20261013.pub`へ作業ブランチに保存。SSH鍵fingerprint `SHA256:uTpac9KfROoNEOQoHxeT6IIXchtD/PqJUbRhRXEmPY8`（本人端末表示と公開鍵から照合）、**recipient行全体**のSHA-256は `da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234`。両者はハッシュ対象が異なる。秘密鍵/パスフレーズをGitHubに絶対保存しない。次は「公開鍵固定と独立暗号化/復号テストの準備」。

## 4 DB・バックアップ優先順位
1. **旧V3** `postgres-hobby-fullhistory-candidate-v3`：10/13時点SLEEPING、既存公開TCP proxyは1件。Railway起動・ネットワーク負担の可能性。**優先退避先：私有Google A`boat-ai-v3-temp-202610`**。
2. **履歴archive** `postgres-history-archive`：10/13 SUCCESS、Postgres SSL18イメージ、公開TCP proxy**0**。Web ConsoleはiPhone SafariでConnectedと表示するが**文字入力不可**。同じ操作を再要求しない。私有Google A`boat-ai-history-archive-temp-202610`に独立保存。公開TCPを安易に追加しない。
3. **V4本番 source** `Postgres-EKp2`→私有Google A`boat-ai-v4-temp-202610`。
4. **V5研究用** `postgres-hobby-fullhistory-candidate-v4`（名前にv4でも旧V4本番ではない）→私有Google B`boat-ai-v5-temp-202610`。
容量は変動しRAW volume占有とpg_dump圧縮サイズは異なる。**Railway元DBを消すのは外部複数コピー・暗号鍵・SHA照合・独立PG18フル復元・同一データ照合を終え、別途個別承認を得てから**。
- 10/1の旧CMS暗号化バックアップはGitHub Actions artifact 3件（runs`36812386066`,`36867010147`,`36934788763`、API上期限2026-12-30、当時隔離復元job成功）。**現在の旧V3/history DBのバックアップではない**。復元秘密鍵用Railwayサービス`archive-restore-key-20261001`の`ARCHIVE_CMS_PRIVATE_KEY_B64*`変数が必要な旧スナップショットがある。鍵を消さない/投稿しない。
- **外部保存実績1件**: 10/1旧V3関連CMS ZIPのGitHub artifact`11139857666`（302,656,753 bytes）を利用者がiPhoneからGoogle A旧V3専用の非共有フォルダへアップロード。Drive file`1lnMh-PefAfLObPnc14pbbDNRWZ3dZT8n`、サイズ一致、**Drive側SHA-256と独立復元は未完**。Google Drive connectorの大容量再取得は256MiB上限で不可。
- Google AのV4/旧V3/archive、BのV5に非共有専用フォルダを用意済み。秘密フォルダIDはGitHubに書かず、必要時にlive確認。

## 現状：iPhone・ConoHa・スクリプト
- 2026-10-13 ConoHa VPS 2GBをPayPalで支払い、申込完了/初期設定完了メール受信。**Safariログイン成功後に新規申込画面へ戻る**ため管理画面の既存VPS・OS/SSH稼働は未確認。サポート連絡済、回答待ち（10/13 19時頃のGmail調査では未着）。**再購入・追加チャージ・アカウント作り直し禁止**。OS推奨Ubuntu24.04LTS、実設定未確認。
- iSHにOpenSSH8.6+鍵gen・rclone v1.75.2 linux/386導入済（rclone起動要`GOMAXPROCS=1 GODEBUG=asyncpreemptoff=1`）。Railway専用Ed25519 SSH鍵をiSH内にパスフレーズ付き作成し公開鍵をRailway accountに**本人が登録済**。秘密鍵は非共有。SSH実疎通は未実施。Railway CLI未導入・非公開サービスのService Instance ID未取得。Web Console短縮IDからコピーできるのは`railway ssh --project=...`であり**Service Instance IDではない**。この操作の再指示禁止。
- Google Cloud Aに本人Desktop OAuth client作成・JSONはiPhone内保管。iSH rclone OAuthは`Waiting for code`まで進んだがSafari`127.0.0.1:53682`接続失敗で**認証未完**。ChatGPT Google Drive連携のtokenをrcloneに流用不可。ConoHa SSHトンネルなど別経路待ち。
- `ops/backup/railway_pg_to_drive_stream.sh`: PostgreSQL18→age→Google A/B rcloneの一回限り暗号化バックアップ設計、モック確認のみで**実転送0・復元0**。対応runbook `ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`。
- **NEW** `ops/backup/v3_to_artifact_encrypt.sh`: **旧V3専用・未配線**（自動 workflow登録なし）のGitHub Actions Runner用pg_dump18→ageストリーム→encrypted artifactファイル＋SHA sidecar。デフォルト`plan`でno-op。サービスID、host/port/DB/TLS、age公開鍵fingerprint、PG18、GitHub Runner、実行・起動/Network費用・復号鍵自己テストの**独立承認ゲート**あり。 `ops/backup/test_v3_to_artifact_guard.sh`とともにfeature branchに作成済、ローカル`bash -n`＋モック停止条件**11/11 PASS**。**実PG18/age/CI/転送/復元未試験**。GitHub Secrets登録やworkflow連結なし。詳細`ops/backup/GITHUB_ACTIONS_ENCRYPTED_ARCHIVE_FALLBACK_20261013.md`。
