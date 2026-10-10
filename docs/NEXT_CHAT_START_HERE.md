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
- pending commandを重複実行しない。タイムアウト後も、run不存在を確認するまで再実行しない。
- SHA/run/件数/容量は固定値扱いせず、その1作業に必要な値だけlive取得。
- 中間ログやtool discoveryを大量表示しない。
- 実行を開始する時は、対象件数/日数/直近実績から**推定所要時間**を表示する。

**V5は主力システム（開発中・本番未切替）**、Productionは現行V4。旧V5は比較対象。旧コードの research/ 名称は参照互換性のため残す。
システム本体完成を優先し、自動購入は最後に構築する。
Railway Agent/AIは禁止。
Railway費用は月USD20以下、可能ならUSD15以下。CPU/RAM/Network最小化。
purchase / LINE / stake / Production model / plan / volume resize-deleteは明示承認なしで変更しない。

重要: 2026-10-10 江戸川1Rの公式READ-ONLY 2 GETとpositive-start証拠判定24/24 PASSは既に完了。**同じ検証を再実行しない。** 出走確定の肯定的証拠は未確認なので、beforeinfo初回保存・Forwardの安全停止を維持する。

確認後、current compact handoffの **Next ONE taskだけ** 実施してください。
