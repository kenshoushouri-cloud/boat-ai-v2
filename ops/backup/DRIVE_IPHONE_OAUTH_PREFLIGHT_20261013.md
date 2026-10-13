# Railway → Google Drive 一時バックアップ：iPhoneのみのOAuth事前計画
更新: 2026-10-13 / 実行状態: **設計のみ**（認証トークン未取得、バックアップ未取得）

## 目的と保存先
- Google Drive A: 非共有 `boat-ai-v4-temp-202610`（V4本番DB `Postgres-EKp2`）。
- Google Drive B: 非共有 `boat-ai-v5-temp-202610`（V5研究用DB `postgres-hobby-fullhistory-candidate-v4`）。
- 2つの個人Googleアカウントは独立。ChatGPTのDrive連携の認証は`rclone`転送ジョブに再利用**できない**。連携画面ではA/Bの接続済み表示を確認したが、コネクタAPIは複数アカウントの識別エラーで未検証。
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

## 実転送前の技術的チェック（必須）
- バックアップ処理は`ops/backup/railway_pg_to_drive_stream.sh`を**そのまま本番投入せず**、静的・小規模テストしてから修正する。
- V4 と V5 で取り違え防止の接続先照合が必要。`SOURCE_DATABASE_URL`のホストとDBの実体をユーザーが秘密を開示せず確認し、`BACKUP_TARGET`のラベルだけで判断しない。
- `age`受信先公開鍵だけを転送ジョブに置き、復号用の**秘密鍵をRailway外で安全に保管**。復元時に秘密鍵が必要。
- RAID/DB volume上にdumpを作らない。中断時のGoogle Drive部分ファイル、ネットワーク転送料金、同期中のWAL増加を考慮。バックアップのSHA-256は転送後に再取得照合が必要。スクリプトの完了表示だけで完全性・復元可能性を証明しない。
- 実行の順序: A/B OAuthの安全確認 → 非機密小容量転送 → source/destination照合 → V4/V5別々の`pg_dump -Fc` → 暗号化ファイル完全性検証 → **別環境完全復元試験** → ConoHa移行判断。
- Railwayのサービス追加・課金・バックアップ・DB/cron変更はその都度ユーザー明示承認。
