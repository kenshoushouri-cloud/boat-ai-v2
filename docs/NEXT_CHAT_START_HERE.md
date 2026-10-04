# Next Chat Start Here

新しいチャットに下記をそのまま貼り付ける。

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に repository `kenshoushouri-cloud/boat-ai-v2` の次の3点だけ確認してください。
1. `docs/HANDOFF_LATEST.md`
2. そこが指定する current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoff・PROJECT_HISTORY・長いworkflowは読まないでください。
SHA・run・件数・容量は固定値扱いせず、次の1作業に必要な値だけlive再取得してください。

【タイムアウト・トーク容量対策を最優先】
- 1回に1作業だけ。
- 原則1〜3 tool call。
- describe_environment全量、Actions /runs全量、全service/全log/古いissue comments大量取得は禁止。
- exact service / exact workflow / exact file / 最新結果だけ取得。
- 長時間処理はそのターンで待たない。起動確認で終了し、結果確認は次ターン。
- polling/sleepは原則禁止。タイムアウト後の同ターン再実行もしない。
- 中間ログやtool discovery結果を大量表示しない。

Production=V4、V5/V5.1=research-only。
Railway費用は月USD20以下、可能ならUSD15以下。CPU/RAM/Networkを最小化。
Railway Agent/AI、`list_variables` / `railway variable list`は禁止。
purchase / LINE / stake / plan / volume resize / TOTO staged patchは変更しないでください。

確認後、current compact handoffの **Next ONE taskだけ** 実施してください。
