# 新競艇AI No.2 — current compact handoff（2026-10-13 夜）

最初は`docs/HANDOFF_LATEST.md`→その指定current compact→`docs/NEXT_CHAT_START_HERE.md`だけを読む。古いhandoff、PROJECT_HISTORY、長いworkflow/ログは通常参照禁止。**1回に1作業、ツール最小、短い結果と所要時間、SHA/run/容量はその作業でlive再取得**。止まった作業を重複実行しない。ユーザーは**iPhone（Safari・iSH Shell）のみ**。1手順ずつ／コピーボタン推奨。

## Next ONE task
**ConoHa VPS 2GBを主軸にV5を完成させる。** ユーザー合意: GitHubはコード/履歴保管、ConoHaで予想AI・DB・収集・バックテスト・定期処理を段階的に一元管理。Railwayは移行前の4DB暗号化バックアップ/独立復元、本番維持、料金抑制だけ優先し、旧GitHub収集の個別修理を深追いしない。ConoHa管理画面はサポート回答待ち（10/14時点未確認）、**再購入・追加PayPalチャージ禁止**。
- **今回完了 2026-10-14**: `ops/conoha/v5_host_preflight_readonly.sh` を作業ブランチに作成。VPSログイン復旧後に実行する、OS/アーキテクチャ/CPU/総・空きRAM/swap/ルート空き容量だけを読む**無通信・無書込の診断**。手元の隔離Linuxで実Bash `bash -n`PASS／通常実行PASS／危険コマンド静的スキャン該当なし、ローカル`git hash-object`とGitHub blob SHA一致。**これはConoHa実機の試験ではない**。実機で未実行、2GB運用性能も未実証。
- **次の1作業**: ConoHaアクセスが戻るまで、V5の**2GB RAM向けジョブ直列化・実行前後の監視/過負荷防止**をGitHub feature branch内で未接続の設計・オフラインテスト。サポート返答時は既存VPSへのログイン確認→本診断→順に設定する。実デプロイ・実DB転送・有料CI・サービス停止・Railway変更は別承認。
- ConoHaは**2GBから始め、Railway費用解消後に必要なら4GBへ増額**（別承認）。過去の締切前未取得情報は遡及して作れずmissingとして扱う。**BUY HARD HOLD**、自動購入最後。

## Source /目的と最重要ガード
- Repo `kenshoushouri-cloud/boat-ai-v2`、作業ブランチ `feature/v5-prior-day-counter-test-20261011`。**main・V4本番を無断変更/マージしない**。V5強化型を主力として構築（旧V4買い目の安易な流用禁止）、将来は自動購入。しかし**BUY HARD HOLD**: Forward/ROI実績未検証、購入操作は最後・別承認。LINE仮候補通知不要。
- 2025-07-01から全保有期間のデータを可能な限り保持。精度悪化でモデルに不採用でもデータ自体は保管。締切前に観測・凍結されていない過去展示/オッズを当時の証拠として偽装しない。返還不明・PENDING・NO_BUY・欠測は勝手に補完/母数除外しない。
- V5 2025-07-01〜2026-10-10の67週間窓は計画済み**実バックテスト0/67**、買付ROI/実収益は未検証。7/2は180レースに対しオッズ238券不足でPENDING。目標+5万円/月は未証明。
- ChatGPT＋Railway費用計月6,000円以内（理想5,000円）。Railway月$10–12目標、$15警戒、$20上限目標（なるべくさらに安く）。VPS/外部保管/移行重複期間も総額で評価。**ConoHaはまず契約済み2GBで構築・実測し、Railway依存サービスが安全に縮退し費用が実際に解消された時点で、必要なら4GBへの変更を選択肢にする（本人の追加費用承認必須）**。メモリ不足時に無理に2GB稼働を続けない。同時実行制御を優先。Railway Agent/AI禁止、無用なCPU/RAM/Network/WAL/高コストCI禁止。**V4/V5/DB/サービス/課金/バックアップ実行は都度承認**。

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
