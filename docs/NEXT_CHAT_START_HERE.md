# 新チャット開始文（2026-10-23 06:51 JST・短縮）

以下をそのまま新チャットに貼り付ける：

@GitHub

新競艇AI開発プロジェクトNo.2の続きです。
Repository: kenshoushouri-cloud/boat-ai-v2

まず `docs/HANDOFF_LATEST.md` と、そこが示す **current compact handoffのみ** 読んでください。過去の長いhandoff・PROJECT_HISTORY・過去会話の大量参照は禁止。実行済み作業の再実行禁止。最新compactの **Next ONE task** から1回1作業、最小tool call・短い出力で進めてください。

2026-10-23 06:45：ConoHaの`boat_data`にある非更新VIEW13件が13/13 PASS。ただしデータの物理移動・V5本番予想切替は未了。06:51：実入力の限定read-only SQLは**0 rows・SQL正常終了**、朝7時の収集前なので収集失敗とは断定不可。まず07時morning/forward収集ログをread-only確認し、実データの時点根拠を調べてV5の**非購入予想試験**を優先。古い共有bulk stage実行・旧DB/backup削除・本番切替・自動購入・有料契約・LINE送信は禁止（独立した明示承認が必要）。ConoHaを優先、Railway Hobbyは解約済み、コスト最小。

V5運用の目標は実3連単予想・2025年7月以降の時点厳守バックテスト・非購入試験、その後に自動購入可否を検討する。遅延しているため設計や調査を増やしすぎず、実稼働へ直接必要な作業を優先。
