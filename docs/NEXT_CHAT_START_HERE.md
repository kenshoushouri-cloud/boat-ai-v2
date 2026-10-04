# Next Chat Start Here

新しいチャットに下記をそのまま貼り付ける。

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に repository `kenshoushouri-cloud/boat-ai-v2` の次の3点だけを確認してください。

1. `docs/HANDOFF_LATEST.md`
2. そこが指定する current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoffは履歴扱いです。SHA・run・件数・容量は固定値にせず、次の1作業に必要なものだけlive再取得してください。

最重要:
- 2026年10月中旬の運用開始が目標
- critical path = 不足データ完了 → 最終整合性確認 → バックテスト → 結果確認 → 過去データ移行/保持範囲確定 → 運用開始
- Production data SoT = candidate-v4
- Railway Hobby / candidate-v4 RAM cap 1GB
- Railway月額コストはUSD 20以下を維持
- Railway Agent / Railway AIは禁止
- `list_variables`禁止
- purchase / plan / volume resize禁止
- TOTO staged patchに触れない
- 1回に1作業、出力は短く
- Issue #42全コメント取得は禁止
- destructive/config変更は明示承認が必要
- historical 14日batchはPASS / leakage / OOM / Disk-WALだけ確認し、安全ならすぐ次へ進む
- 不足データ完了後は寄り道せずバックテストへ進む

確認後、current compact handoffの「次の1作業」から続けてください。
