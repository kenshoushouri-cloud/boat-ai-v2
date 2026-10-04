# Next Chat Start Here

新しいチャットに下記をそのまま貼り付ける。

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に repository `kenshoushouri-cloud/boat-ai-v2` の次の3点だけを確認してください。

1. `docs/HANDOFF_LATEST.md`
2. そこが指定する current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

**古いhandoffは大量参照しないでください。**
SHA・run・件数・容量は固定値にせず、**次の1作業に必要なものだけ**live再取得してください。

最重要:
- 2026年10月中旬の運用開始が目標
- ProductionはV4、V5はresearch-only
- Historical Recent Formは2026-09-30まで補完済み
- 次回matched-contract backtestの研究主対象はV5 candidate core
- V4をbaselineとして same time split / no-leakage / same-contract で比較する
- **1回に1作業だけ**
- 出力は短く
- Railway Agent / Railway AI禁止
- `list_variables` / `railway variable list`禁止
- purchase / plan / volume resize禁止
- TOTO staged patchに触れない
- Issue #42全コメント取得禁止
- destructive/config変更は明示承認が必要

確認後、current compact handoffの **Next ONE task** だけ実施してください。
