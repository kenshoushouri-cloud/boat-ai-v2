# 新競艇AI No.2 — 最新コンパクト引き継ぎ（2026-10-14 JST）

## 読み方・運用ルール
- 入口 `docs/HANDOFF_LATEST.md` → **本ファイルのみ全文**。新チャット開始文は `docs/NEXT_CHAT_START_HERE.md`。古いhandoff/PROJECT_HISTORY/長いworkflow/ログは必要な個別箇所のみ。詳細は末尾の参照先で追える。**本ファイルを肥大化させず更新時は古い経過を要約・置換**。
- Repo `kenshoushouri-cloud/boat-ai-v2`、作業branch `feature/v5-prior-day-counter-test-20261011`。**main・V4本番を無断変更しない**。1回に1作業、短時間・最小tool call、時間目安を示す。SHA/run/件数/容量は固定値にせず必要時だけlive再取得。利用者は**iPhone Safari/iSHのみ**（PC前提禁止）。

## 目的・採用方針
- **強化型V5を主力**に、競艇の公式出走表・選手/級別/調子/コース/モーター・交換直後の母数・展示/ST/気象/オッズを取得し、検証で精度が上がる特徴量のみ予測に採用。不採用の元データも保存。V4の購入判断を無検証で移植しない。
- V5の正しい予測・回収率をバックテストと実Forwardで検証し、安定運用後に自動購入を**最後に別承認**。目標月利益+5万円は未実証、**BUY HARD HOLD**、LINE仮候補通知は不要。
- 最終構成は**ConoHa VPS 2GB内にDB・収集・V5・cron・監視・バックテストを原則一元化**（バックテストは低負荷・直列）。GitHubはソース/履歴、VPS外には暗号化バックアップ。Railwayの旧収集/Actions障害の修理を深追いせず、移行まで元データと現V4稼働を維持。

## 現在の実績・未完了（2026-10-14）
- **ConoHa**：10/13のVPS 2GB申込完了/支払確認メール受信済。**10/14 Gmail再確認でサポート返信なし**。Safariログイン後に申込/支払画面へ戻る問題は未解決、既存VPSのOS/IP/SSH未確認。**再購入・追加チャージ禁止**。推奨Ubuntu24.04LTSは実機未検証。
- **V5**：2025-07-01〜2026-10-10の計画67週OOS窓は**実行0/67、実ROI未検証**。2026-07-02は180レースでオッズ238券不足のPENDING。締切後の展示/オッズや日付のみ一致の履歴を当時の凍結証拠にしない。欠測/返還不明/NO_BUY/PENDINGを勝手に補完・母数除外しない。
- **GitHubオフライン準備**：V5論理DAG20/20、直列ガード既存9/9＋所有者/リンク検査11/11が隔離LinuxでPASS（実機未導入）。**今回GitHub featureブランチで11ファイル・28個のコード根拠を静的照合PASS**、`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`に既存収集/結果writer・PRE/LINE経路と未配線V5の区別を記録。**現行Railway cronの実稼働やV5 readinessを確認したものではない**。
- **バックアップ**：4DB既定無通信、service/Drive/鍵/別承認ゲートの既存テスト75件PASS、途中失敗11/11 PASS。**今回、`.dump.age`＋`.sha256`＋`.ready`をローカルで照合する読取専用プログラム・21/21テストPASS**。GitHub SHA＝ローカルテスト済ファイル一致。**これは3ファイルの整合性のみ**。archive/V4/V5復元鍵ピン未確定で実行HOLD。**実age/本人鍵復号・現行4DB外部バックアップ0/4・独立復元0/4**。iPhone iSH固定Alpine 3.14の`apk.ish.app`に`age`がなく`apk add age`失敗（本人画像で確認）。OS/リポジトリ変更禁止。詳細`ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`。
- **過去の別資産**：10/1旧CMS暗号化Actions artifact3件は2026-12-30失効予定（当時の隔離復元job成功）。うち約302.7MB ZIP 1件は私有Drive AへiPhoneでコピー済だが**Drive側SHA/独立復元未検証**。現在の4DBバックアップを代替しない。Railway `archive-restore-key-20261001` の復元鍵変数を保護。

## 保全対象4DB（移行時の混同禁止）
|順|Railway原本（実データを必ず現状確認）|一時保存先|
|---|---|---|
|1|`postgres-hobby-fullhistory-candidate-v3`（旧V3・休止、起動費注意）|私有Google A / V3専用フォルダ|
|2|`postgres-history-archive`（履歴アーカイブ・公開TCP無し）|私有Google A / archive専用フォルダ|
|3|`Postgres-EKp2`（**V4本番**・公開TCP無し）|私有Google A / V4専用フォルダ|
|4|`postgres-hobby-fullhistory-candidate-v4`（**名称v4だがV5研究用**）|私有Google B / V5専用フォルダ|
- **2025-07-01以降の全保有履歴を保全**。保存容量は現在値ではないので都度計測。別GoogleアカウントのDrive認証/rclone OAuthは未完（iSHでSafari localhost callback失敗）。公開DBポート増設を安易にしない。
- 復元専用Ed25519秘密鍵は本人のiPhone/iSH・本人管理iCloud側で保全、GitHubには**公開鍵のみ** `ops/backup/keys/v3_recovery_recipient_20261013.pub`。秘密鍵・パスフレーズ・OAuth token・DB URLをチャット/リポジトリに載せない。公開鍵固定SHAの詳細は `ops/backup/BACKUP_SAFE_MODES_20261014.md`。

## 工程・タイムスケジュール（希望と現実を分離）
- **当初目標は2026年10月中旬に稼働開始**だったが、10/14時点でConoHaログイン・実4DBバックアップ・復元・67週バックテストが未完のため**達成日を約束できない**。安全性・実測優先。以下はConoHaアクセス復旧日を **T0** とした暫定目安で、承認・容量・通信・サポート対応により延長あり。
- **T0前（現在）**：追加費用なしでGitHub feature branchのガード/復元鍵互換性/直列運用設計をオフラインで検証。ConoHaサポート回答を待つ。
- **T0〜1日目の目安**：既存ConoHa VPSの契約/画面/OS/SSHを確認、診断スクリプトでCPU/RAM/空き容量を測定、安全な初期設定を本人承認のもと実施。本人復元鍵で実age往復確認。
- **T0以降・数日〜（容量次第）**：Drive A/B本人認証、少量の暗号化テスト→旧V3・archive・V4・V5を**各1DBずつ**暗号化退避→遠隔SHA→独立PG18全件復元/同時点照合。取得/ネットワーク費用と起動は都度承認。**復元完了まではRailway削除/停止しない**。
- **バックアップ検証後・数日〜数週間**：ConoHa 2GBで収集→締切前品質検査→V5 shadow予想→競走後結果→監査→2025-07以降67週OOSバックテスト。RAM/ディスク/WALを実測し直列化・欠測再試行。Forward検証、費用/障害復旧、V4との比較を経て運用判断。自動購入は最後の別承認。
- **全コピー・独立復元・機能照合がPASSした後**：ユーザー個別承認でRailway/古いActionsを段階縮退。元DB削除はさらに別承認。ConoHa 4GB化は2GB実負荷とRailway費用解消後に必要なら追加承認。

## 費用・絶対保護条件
- ChatGPT＋Railway予算は理想月5,000円以下/上限目安6,000円。ConoHa/外部保存/二重稼働費も**総額**で評価。Railway費は可能なら$10〜12、$15警戒/$20超回避。CPU/RAM/Network/WAL/CIを節約。**Railway Agent/AI使用禁止**。
- **禁止**：無承認のV4本番変更、mainマージ、4DB/サービス/cron/旧CMS資産/復元鍵の停止・削除、DB wake/接続・dump/復元・大容量転送/購入・課金、バックテスト未検証のBUY。復元前の元データ削除禁止。既に走った作業は再実行前に現状確認。

## Next ONE task
**Next ONE task**：ConoHaサポート回答を優先確認。管理画面復旧時は再購入せず既存2GB VPSのread-only OS/SSH/RAM/容量診断。未復旧なら`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`を元に、V5の新規writerが共通ロックを迂回しないかを検査する**読取専用・オフライン静的チェッカー**を作る。iSH固定Alpine3.14へage強行導入禁止。本人鍵持出し、DB実接続/cron起動、Railway停止/削除、BUYは禁止。

## 詳細は必要時だけ個別参照
- `docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`（既存writer・通知入口・V5未配線・ロック対象）
- `docs/V5_CONOHA_SERIAL_DAG_CONTRACT_20261014.md`（V5順序/品質/再試行）
- `docs/V5_CONOHA_2GB_RAILWAY_MOVE_PREFLIGHT_20261013.md`（OS/DB移行設計）
- `ops/backup/BACKUP_SAFE_MODES_20261014.md`、`ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`（暗号化/復元）
- `docs/GITHUB_ACTIONS_LONG_RUN_AUDIT_20261014.md`（旧Actionsの調査・GitHub実請求$0時点情報）
