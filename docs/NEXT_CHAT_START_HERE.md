# Next Chat Start Here

Paste the block below into a new chat.

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読むのは次の3点だけです。
1. `docs/HANDOFF_LATEST.md`
2. そこから指定された current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古い handoff は履歴扱いです。その後、handoff内のSHA・run・件数を固定値とせず、一度に1作業だけlive再取得してください。

固定:
- GitHub `main` = code SoT
- Railway `postgres-recovery` = Production data SoT
- FULL_HISTORY_PINNED
- V4/V5/backtest/historical collectionを保護
- Railway plaintext Variablesを列挙しない / `list_variables`禁止
- Railway Agentは通常MCPで取得不能な場合だけ
- Production behavior/cutover/delete/resize/plan changeは明示承認が必要
- `purchase_action=false`

現在:
- 10月2日中のPro -> Hobby移行完了が目標。10月3日はbilling renewal boundary
- candidate-v4は5 GB上でcurrent snapshotをコンパクト復元済み
- latest direct footprint: DB約3.597 GB / WAL約0.537 GB / Railway disk約4.34 GB
- odds unique indexは存在
- latest current parity差はschemaではなく、Production継続書込みによる8テーブル合計572行
- refresh workflowのpsql meta-command誤判定はmainで修正済み
- `postgres-recovery` 20 GBは縮小せず、verified cutoverまで保持
- cleanupはstagedのみ。2FA Applyはまだしない
- **次の1作業 = final cutover preflightとして、最終同期時に止めるwriter serviceをread-onlyで確定**
- その後、明示承認を得て短時間freeze -> v4 final refresh -> zero-delta parity -> cutover

タイムアウト対策:
- Actions全件、Issue全コメント、巨大logを取得しない
- specific run/page/resourceだけ
- 1作業ごとに短く結果報告

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / FULL_HISTORY_PINNED / PROTECT_BACKTEST / 5GB_V4 / FINAL_SYNC_BEFORE_CUTOVER / PURCHASE_FALSE`

---
