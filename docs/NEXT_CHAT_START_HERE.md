# Next Chat Start Here

新しいチャットに下記をそのまま貼り付ける。

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に repository `kenshoushouri-cloud/boat-ai-v2` の次の3点だけ確認してください。
1. `docs/HANDOFF_LATEST.md`
2. そこが指定する current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

【トーク容量・タイムアウト対策を最優先】
- 古いhandoff、PROJECT_HISTORY、長いworkflow、過去chatは読まない。
- 1回に1作業。tool callは必要最小限。
- Issue commentsは最新必要分だけ。Actions全run、全service、全logの大量取得は禁止。
- polling連打禁止。長時間runは起動と結果確認を別ターンにする。
- タイムアウト後に同じcommandを再実行しない。
- SHA/run/件数/容量は固定値扱いせず、その1作業に必要な値だけlive取得。
- 中間ログやtool discoveryを大量表示しない。
- コード追加＋runner追加＋1回の起動は、必要なら1ターンにまとめてよい。

Production=V4、V5/V5.1=research-only。
Railway Agent/AIは禁止。
Railway費用は月USD20以下、可能ならUSD15以下。CPU/RAM/Network最小化。
purchase / LINE / stake / Production model / plan / volume resize-deleteは明示承認なしで変更しない。

確認後、current compact handoffの **Next ONE taskだけ** 実施してください。
