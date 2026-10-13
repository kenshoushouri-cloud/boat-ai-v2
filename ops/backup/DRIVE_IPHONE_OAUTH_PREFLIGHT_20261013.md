# Railway → Google Drive 一時バックアップ：iPhoneのみのOAuth事前計画
更新: 2026-10-13 / 実行状態: **設計のみ**（認証トークン未取得、バックアップ未取得）

## 目的と保存先
- Google Drive A: 非共有 `boat-ai-v4-temp-202610`（V4本番）、`boat-ai-v3-temp-202610`（旧V3）、`boat-ai-history-archive-temp-202610`（履歴アーカイブ）。**同じGoogle Aでも3つの独立フォルダ**。
- Google Drive B: 非共有 `boat-ai-v5-temp-202610`（V5研究）。A・Bの4フォルダは2026-10-13に各明示アカウントのconnectorで**実在・非共有・空0件**を確認済み（rcloneによる書込確認とは別）。
- 2つの個人Googleアカウントは独立。ChatGPTのDrive連携の認証は`rclone`転送ジョブに再利用**できない**。connectorのアカウントを明示して上記の4フォルダを検証済み。
- 既存のV3 DBはsleep維持。ConoHa未復旧、V4本番と必要なcronを維持。過去データの削除禁止。

## 確認した公式制約
1. Google Driveに`rclone`で接続する際はOAuth認可が必要。2026年中にrcloneの**共有client_idが提供終了予定**なので、それには依存せず、**利用者が所有するGoogle OAuth client_id**を用意する。
2. rclone標準のheadless OAuth方法は、認証ブラウザに加え`rclone authorize`が実行可能な端末、または`localhost:53682`へのSSHポート転送が必要。Safariで外部から直接`127.0.0.1`を開く方式は不可。
3. Google Cloud OAuth「External / Testing」でDriveのスコープを使う場合、更新用トークンは通常**7日で失効**。短期移行では運用日に合わせて認可し、期間超過は再認可が必要。Google Cloudの新たな支払い登録はユーザー承認なしにしない。
4. サービスアカウントによる個人用「マイドライブ」への直接保存は採用しない。既存フォルダに`drive.file`権限のみで書けると仮定しない。実際のOAuthスコープ・許可画面は本人が確認。
公式: https://rclone.org/drive/ , https://rclone.org/remote_setup/ , https://rclone.org/commands/rclone_authorize/

## iPhoneのみの安全な実装候補と決定ゲート
- **候補A（ConoHa復旧後・第一候補）**: VPS上でrcloneを準備し、iPhoneのSSHクライアントで**ローカルポート転送**を実行、同じiPhoneのSafariでGoogle OAuthを認証。iPhone SSHアプリのポート転送対応を実機で確認してから採用。VPS初期セキュリティ設定前には操作しない。
- **候補B（ConoHa復旧前）**: iPhoneのローカルLinuxターミナル（例: iSH）でrcloneの**現行版が動作するか**を少量の非機密テストで確認し、ローカルSafariと同端末でOAuthする案。2026年の実機動作は未確認。古いバイナリ、怪しいOAuthサービス・認証代行は使わない。
- **候補C（上記が使えない時のみ）**: 自前の一時的HTTPS OAuth callbackサービスを設計。公開URL・Google Cloud設定・秘密鍵保管・費用が増えるため**別途明示承認**を受ける。Railwayで無断作成しない。
- どの方式でもチャット、GitHub、スクリーンショットにclient_secret / refresh_token / rclone.conf / DB URL / age秘密鍵を送らない。
- OAuthを取得しただけではバックアップは完了しない。Google A/BそれぞれのフォルダIDとrclone remote名を利用者が照合すること。

## 2026-10-13：旧V3・履歴アーカイブ先行、ConoHa待ちのiPhone別案
- **優先対象**: 旧V3 `postgres-hobby-fullhistory-candidate-v3`（live latestDeployment=SLEEPING、DBボリューム約4.553GB、**Railway公開TCP proxyあり**）→履歴archive `postgres-history-archive`（SUCCESS、約2.340GB、**公開TCP proxyなし／内部接続のみ**）の順。V4本番・V5主力は別々のDriveへ確保する計画を維持。
- **接続経路**: V3の公開proxyは他サービスとホスト名が共用され得る。送信元`SOURCE_DATABASE_URL`はホスト**とポート**双方を当日のlive Railway設定と照合する。追加した`SOURCE_EXPECTED_PORT`必須ガードを使用する。archiveでは公開proxyを新設せず、内部ネットワークに接続できる一時実行場所が必要。旧V3のSLEEP解除やRailway新規ジョブ、network送信は有料になる可能性があるため**実行前の個別承認**。
- **ConoHaを待たずに試せる認証準備**: iPhone専用の無料アプリ`iSH Shell`（https://ish.app/ ; App Store https://apps.apple.com/app/id1436902243）を使用する候補。iSHはAlpine系ユーザー空間で、Alpine公式の`apk add rclone`が利用可能。まずアプリ導入後、iSH内の`apk update && apk add rclone`と`rclone version`**のみ**を試し、現行パッケージが実際に起動するか確認する。2022年にはrclone forumでiPhone+iSHからブラウザOAuth成功例があるが、**2026年現在のこのiPhoneでの動作・ブラウザ復帰は未検証**。失敗時は無理にOAuthに進まずConoHa SSHトンネル待ち。
- **次段の本人承認**: rcloneの共有client_idは2026年に廃止予定なので、本人のGoogle CloudプロジェクトにDesktop型OAuthクライアントを安全に用意する。Google Cloudに新規課金設定は入れない。既存のGoogle A/Bそれぞれにログインして本人だけが承認する。OAuth token・client_secret・rclone.conf・DB URL・age秘密鍵をChatGPT/GitHub/共有リンクに貼らない。認証前の`apk add`だけでは外部保存は進まない。
- **実際のバックアップの条件**: バックアップスクリプトの`BACKUP_TARGET`ごとに送信元のhost/port/DB名、年齢暗号鍵指紋、A/B保存先フォルダID、rclone OAuth対象を独立照合する。フルダンプ前に非機密小容量送信を確認する。正式保存後は再取得SHA-256、独立PG18復元、行数/固有データ照合まで終えてから、**削除について別承認**。
- 2026-10-13現状: **バックアップ0件、実転送0件、復元0件**。既存Railway/Drive/ConoHaへの変更なし。

## 実転送前の技術的チェック（必須）
- バックアップ処理は`ops/backup/railway_pg_to_drive_stream.sh`を**そのまま本番投入せず**、静的・小規模テストしてから修正する。
- V4 と V5 で取り違え防止の接続先照合が必要。`SOURCE_DATABASE_URL`のホストとDBの実体をユーザーが秘密を開示せず確認し、`BACKUP_TARGET`のラベルだけで判断しない。
- `age`受信先公開鍵だけを転送ジョブに置き、復号用の**秘密鍵をRailway外で安全に保管**。復元時に秘密鍵が必要。
- RAID/DB volume上にdumpを作らない。中断時のGoogle Drive部分ファイル、ネットワーク転送料金、同期中のWAL増加を考慮。バックアップのSHA-256は転送後に再取得照合が必要。スクリプトの完了表示だけで完全性・復元可能性を証明しない。
- 実行の順序: A/B OAuthの安全確認 → 非機密小容量転送 → source/destination照合 → V4/V5別々の`pg_dump -Fc` → 暗号化ファイル完全性検証 → **別環境完全復元試験** → ConoHa移行判断。
- Railwayのサービス追加・課金・バックアップ・DB/cron変更はその都度ユーザー明示承認。
