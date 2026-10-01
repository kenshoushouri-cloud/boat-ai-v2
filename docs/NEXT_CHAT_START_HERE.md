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

古いhandoffは履歴扱いです。handoff内のSHA・run・件数・容量は固定値にせず、必要なものだけlive再取得してください。

固定:
- GitHub `main` = code SoT
- Railway `postgres-recovery` = current data SoT
- V4/V5/backtest/historical collectionを保護
- 必要な過去データは、バックテスト＋一定期間の運用テストで保存方針が決まるまで保持
- 不要と確認できた移行残骸・重複資源は削除可
- Railway plaintext Variablesを列挙しない / `list_variables`禁止
- Railway Agentは通常MCPで実行不能な場合だけ
- `purchase_action=false`
- 1回に1作業、結果は短く

現在:
- 旧Hobby candidate / migration worker類の整理はApply済み。pending staged changesは空
- `postgres-recovery`、candidate-v3/v4、historical/backfill/backtest/cron系は保護されSUCCESS
- candidate-v4は固定artifactから再復旧済み
- unsafeなv4 `current-refresh` は停止済み
- latest v4 read-only: DB約3.282 GB / WAL約0.537 GB / public index約0.613 GB
- 約303 MBの `ux_v2_odds_trifecta_race_ticket` は現在未作成
- このindexは `(race_id,ticket)` 一意性とexact parityに必要なので、容量節約だけを理由に恒久削除しない
- source `postgres-recovery` は直近4249 MB。収集継続中
- `Postgres` / `Postgres-AbWo` は内容未確認のため削除していない
- **次の1作業 = candidate-v4のread-only index-layout diagnosticを実行/確認し、真に重複・不要なindex候補だけを特定**
- その後、必要index再構築 -> exact parity -> writer freeze/final sync -> zero-delta parity -> 明示承認後cutover
- 10月2日中のPro -> Hobby完了が目標、10月3日がbilling renewal boundary

タイムアウト対策:
- Actions全件・Issue全コメント・巨大logを取らない
- specific run/page/resourceだけ
- 一度に1作業

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / PROTECT_HISTORY / 5GB_V4 / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`

---
