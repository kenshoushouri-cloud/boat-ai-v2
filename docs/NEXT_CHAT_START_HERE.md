# 新チャット貼り付け案内（2026-10-23 17:47 JST）

@GitHub

新競艇AI開発プロジェクトNo.2の続きです。
Repository: kenshoushouri-cloud/boat-ai-v2

最初に以下だけを確認してください。
1. docs/HANDOFF_LATEST.md
2. そこが指定する current compact handoff の全文（現時点 docs/LIVE_HANDOFF_20261023_0651_COMPACT.md）
3. 必要があれば docs/NEXT_CHAT_START_HERE.md

10月23日17:47、ConoHa Termiusで共有13表の隔離オフラインstage＋全PK差分判定のテスト **8件/8件PASS**（OFFLINE_STAGE_AND_COMPLETE_KEY_DELTA_TESTS_PASS_NO_DB_NO_BUY）。これは実DB複製・差分適用・深夜切替の完了ではありません。**実データ移行はまだ未着手**です。

目標はV5/V6共通の物理正本への安全な移行です。現在 boat_data.* は13個の非更新VIEW、原本は public.v2_* 物理表です。稼働中の朝夜/forward/深夜の収集は止めないでください。旧研究shadowや隔離データは無条件に混ぜないでください。

current compact handoff末尾の「Next ONE task」から進めてください。次はGitHubで**venues 1表のstaging安全実装設計とオフライン検査**を1作業のみ。ConoHaの最初のDB変更より前にローカル新世代バックアップと限定復元試験を必須とし、本番切替前は外部独立保全も必要です。既存Google Drive8ファイル保護、移行完了後にV5本体・共通データだけをV3/V4とは別のV5専用Driveへ定期暗号化バックアップする方針。現時点で自動予約なし。

古い長いhandoffやPROJECT_HISTORYを大量参照せず、1回1作業・ツール最小・短い日本語報告。SHA・容量・実行結果は固定値扱いせず都度必要な分だけ再確認。Railway Agent/AI、無断課金、Git pull、無条件bulk COPY、VIEW置換、旧表削除、writer変更、本番予測/BUYは禁止。タイムアウトを避け、ConoHaへの実行指示は1コマンドずつお願いします。
