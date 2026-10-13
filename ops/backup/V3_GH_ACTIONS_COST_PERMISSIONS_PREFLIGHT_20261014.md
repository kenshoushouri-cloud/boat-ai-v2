# 旧V3 GitHub Actions：権限・費用・公開範囲の事前点検（2026-10-14）

状態：**read-only調査＋設計のみ**。workflow未登録／Runner未実行／Railway DB未接続／秘密情報未登録／転送0件。

## live確認
- リポジトリ `kenshoushouri-cloud/boat-ai-v2` は **public**、default branchはmain、作業は `feature/v5-prior-day-counter-test-20261011` のみ。main無変更。
- `ops/backup/GITHUB_ACTIONS_V3_MANUAL_DRAFT_20261014.yml.txt`は `.github/workflows/`の外にあり、実際のworkflowではない。実行jobは `if: false`相当の恒久停止条件を持ち、依存パッケージ準備も `exit 70`で停止。自動実行も手動実行も不可。
- draftのGITHUB_TOKEN権限は `permissions: contents: read`のみ、checkoutの認証情報は保持しない `persist-credentials: false`、手動workflow_dispatchのみ・デフォルトplan、操作者／Railway起動・通信費／本物の復号テストの別承認ゲートあり。
- 実際の Actions許可ポリシー、本人のbilling plan、使用済みartifact容量、支払方法、GitHub Budget の状態は連携から取得できていない。

## 料金と安全（2026-10-14時点 GitHub公式）
- **publicリポジトリの標準 GitHub-hosted runnerの実行時間は無料**。現draftは標準ubuntu-24.04想定。**larger runnerは有料**。https://docs.github.com/en/actions/concepts/billing-and-usage
- **artifactとGitHub Packagesのストレージは共有枠**で、GitHub Freeには500MBの枠（本人plan未確認）。超過時のartifact保存は概ね$0.25/GB-month、またはquotaにより停止しうる。課金は容量×保管時間。https://docs.github.com/en/billing/concepts/product-billing/github-actions
- **公開リポジトリのActions artifactは第三者から参照され得る**。暗号化済みの `*.dump.age` と `*.sha256` 以外はアップロード禁止。DB URI・パスワード・トークン・SSH鍵・age秘密鍵/パスフレーズ・平文dumpをログやartifactに絶対含めない。暗号文であってもファイル名/サイズ/日時などのメタデータは外部に見える。https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts
- GITHUB_TOKENは最小読取権限。GitHub書込み権限者はrepository secretsにアクセスし得るため、配備前にcollaborator/branch/secret scopeを確認。参照する`actions/checkout`と`actions/upload-artifact`は本番前に**GitHub公式repoで検証した完全commit SHA**に固定（draftはタグ指定のまま）。https://docs.github.com/en/actions/reference/security/secure-use

## 実行前のHARD HOLD
1. 本人GitHub UI `Settings → Billing and licensing → Usage`でartifact使用量、Actions Budget、課金停止設定を閲覧確認。ここが未確認のまま実行しない。過去CMSの必要なartifactや旧復号鍵を勝手に削除しない。
2. 実V3 dumpの圧縮サイズは未知。10/1旧CMS 303MBやV3 DB volume 4.55GBから**推定確定しない**。3日間保管の上限と想定使用量を先に判断し、上限に近ければActions artifact経由を採用しない。
3. iSH本人保管の別Ed25519復号鍵を使い、実際のage暗号化→復号→少量ファイルhash一致を確認するまでバックアップしない。GitHubへ秘密鍵を送らない。
4. Actionsへの本登録、GitHub Secret登録、Railway DB起動、実dump、Driveへの保存は**それぞれ別の本人承認後**。実行前に最新版のpostgresql18/age出所固定、timeout/retention 3日、暗号化成果物のみ、RUN_ID固定を再確認。
5. 実行は**一度・旧V3のみ**、暗号文hash・復号・独立PG18復元・データ照合まではRailway元DBもarchiveも削除しない。V4本番とBUY HARD HOLDを保護。

## Next ONE task
本人のGitHub Billing画面でartifactの現在使用量とActions Budgetを**読み取りのみ**確認する。ConoHaサポートは返答待ち、再購入・追加チャージしない。
