# 新競艇AI No.2 — current compact handoff（2026-10-13 夜）

最初は`docs/HANDOFF_LATEST.md`→その指定current compact→`docs/NEXT_CHAT_START_HERE.md`だけを読む。古いhandoff、PROJECT_HISTORY、長いworkflow/ログは通常参照禁止。**1回に1作業、ツール最小、短い結果と所要時間、SHA/run/容量はその作業でlive再取得**。止まった作業を重複実行しない。ユーザーは**iPhone（Safari・iSH Shell）のみ**。1手順ずつ／コピーボタン推奨。

## Next ONE task
2026-10-14ユーザー承認方針：**ConoHa 2GBで構築・実測→V5移行/独立復元確認→Railwayの稼働費解消後、必要なら4GBへ変更を別承認**。ConoHaログインはサポート返答待ちで再購入禁止。GitHubはコード/履歴を残し、長時間ActionsをConoHaへ段階移管する。2026-10-01と10-04の個人Github Free UsageはActions Linux **1,858min / 1,850min**、storage **31.36 / 46.43 GB-hr**、請求は両日**$0**（ユーザー画面）。main read-only監査：`exhibition-st-forward-scheduled-collector.yml`が日中5分cron＋最大90分ループ（timeout100）、`racer-course-top3-forward-scheduled-collector.yml`が毎日cron＋120分ループ（timeout130）、実時間コストの**候補だが因果未確定**。詳細`docs/GITHUB_ACTIONS_LONG_RUN_AUDIT_20261014.md`。**Next ONE taskは10/1／10/4のGitHub Actions実run/job durationを調査し候補を実証。** 収集停止でForward証拠が欠けるため、代替収集/移管と検証前にcron停止・削除禁止。GitHub Actions実バックアップ・Railway起動・DB接続・Secrets登録・ConoHa増額・BUYは引き続きHARD HOLD。


- **2026-10-14 Workflow実行時間の調査制約**: GitHub接続では既知`run_id`のjobs/stepsは取得できるが時刻/所要分を返さず、日付別のrun一覧もツール対象外。原因は**仮説段階**。ConoHa移行方針は2GB→検証後4GB(必要時・別承認)、現Railway保護。次ONE taskはiPhoneで `https://github.com/kenshoushouri-cloud/boat-ai-v2/actions/workflows/exhibition-st-forward-scheduled-collector.yml?query=created%3A2026-10-01` を表示し10/1の実行一覧を確認。停止・削除/有料実行しない。

- **2026-10-14 07:13 JST 失敗原因確定に近づく**: #190 `collect`は23秒で失敗、`Load public database URL without publishing it`の7秒ステップで`DATABASE_PUBLIC_URL not found`、本体収集ループはskipped。main workflowの`--service postgres`はRailway production live一覧に無いサービス名。V4本番DBは`Postgres-EKp2`、live TCP proxy 0、変数名`DATABASE_URL`はあり`DATABASE_PUBLIC_URL`無し（秘密値の取得なし）。原因は旧接続設定と現在構成の不一致と判断。展示ST実欠測・別経路取得は未確認。**Next ONE task: Railway側の展示ST取得代替ジョブ/サービスをread-onlyで確認**。cron停止・公開proxy新設・V4本番への設定変更・run再実行禁止。詳細`docs/GITHUB_ACTIONS_LONG_RUN_AUDIT_20261014.md`。
- **2026-10-14 07:09 JST GitHub Actions 10/1 実画面**: `exhibition-st-forward-scheduled-collector.yml` の `created:2026-10-01` は **3 runのみ**: #188 09:53 JST 13秒 失敗、#189 15:37 JST 28秒 失敗、#190 22:50 JST 25秒 失敗。合計66秒で、10/1 GitHub Actions Linux 1,858minの主因ではない。**ただし収集失敗の理由と実欠測の有無は未確認**。次ONE task: GitHub Actions #190 のrun詳細で失敗箇所確認（ログに秘密があれば送らない）、Railwayは変更/起動せず、cron停止禁止。詳細 `docs/GITHUB_ACTIONS_LONG_RUN_AUDIT_20261014.md`。

- 2026-10-14 Railway展示情報の代替経路read-only調査: cron-final-check → run_final_pg.py → v25_final_realtime_pipeline_pg.py → v21_realtime_collector_pg_safe.py → save_exhibition_and_entries で通常展示を保存する実装あり。10/13 Railwayログ saved_exhibition_rows は6〜30等の正数が複数、直近Cron succeeded。10/1の同ログ検索は0件のため当日データ保存は未確認。展示STの締切前Forward専用表 v2_exhibition_st_forward_shadow とは別。専用collector collect_exhibition_st_forward_shadow_pg.py がRailway他サービスから実行されていたか・表にデータがあるかは不明。Next ONE taskは専用collector呼出し経路のmain静的調査。DB接続・停止・削除・公開proxy追加は禁止。詳細 docs/GITHUB_ACTIONS_LONG_RUN_AUDIT_20261014.md。


- **2026-10-14 方針転換（ユーザー提案・推奨）— ConoHa新システム完成優先（Railway修理は原則停止）**: 移行予定のRailwayに対する展示ST Forward個別不具合の深追い・旧GitHub Actionsの修理を優先しない。Railwayは**V4本番維持、4 DBの暗号化バックアップ、独立復元検証、移行完了までのデータ保全、費用把握**の必要最小限read-only確認に限定（停止・削除は別承認）。ConoHa 2GB管理画面のサポート回答待ち、再購入禁止。復旧後、旧V3・履歴archive優先に全4DB退避→復元検証→ConoHaでV5データ取得/品質監視/不具合修正/2025年7月以降バックテスト→運用検証→Railway段階停止。過去の締切前に記録されなかった展示/オッズ等は後から真の当時証拠にできず、missing/PENDINGとして扱う。2GB負荷計測、Railway費用解消後に必要かつ本人承認があれば4GB。**BUY HARD HOLD、自動購入は最終、V4を無断変更しない**。Next ONE task: ConoHa回答が届くまで移行設計・暗号化復元テストの非課金準備、回答後は既存VPSへの安全なログイン確認。

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
