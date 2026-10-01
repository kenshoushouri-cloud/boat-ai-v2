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

古いhandoffは履歴扱いです。handoff内のSHA・run・件数・容量は固定値にせず、次の作業に必要なものだけlive再取得してください。

固定:
- GitHub `main` = code SoT
- Railway `postgres-recovery` = current Production data SoT until explicit cutover
- V4/V5 prospective evidence / historical collection / backtestを保護
- TOTO `toto-ai-v1` は別プロジェクト。変更しない
- Keirin projectはユーザーが削除済み
- Railway内で完結する履歴/バックテスト分離を優先
- Railway plaintext Variablesを列挙しない / `list_variables`禁止
- `purchase_action=false`
- 1回に1作業、結果は短く

現在:
- candidate-v4の必須odds unique indexは再構築済み、VALID/READY。再構築しない
- candidate-v4観測: DB約3.585GB / WAL約0.537GB / actual disk約4.331GB
- `postgres-history-archive`: PostgreSQL 18 + 5GB Volume、SUCCESS、空
- 最新retention audit = **FULL_HISTORY_PINNED**
- source DB約4.460GB、compact full restore約3.616GB、+14日予測約4.053GB、5GBまで計画余裕約947MB
- historical matched-readiness / matched-contract backtest完了までは履歴データを移動・削除しない
- `Postgres` / `Postgres-AbWo` は未確認・大容量。削除/resize禁止
- `postgres-recovery` は20GB Volume。Hobby化前にcutover/rollback確認後の扱いを決める
- 10月2日中のPro→Hobby完了が目標、10月3日がbilling renewal boundary

**次の1作業:**
live `postgres-recovery` と `postgres-hobby-fullhistory-candidate-v4` の read-only current parity / delta baseline を確認する。

sourceは収集中なので差分が出てもmigration failureとは扱わない。
同じターンで writer freeze / final sync / cutover / delete / resize / plan change はしない。

その後:
current parity -> writer freeze -> final sync -> zero-delta parity -> writer retarget -> explicit cutover -> smoke -> rollback確認 -> oversized legacy resource整理 -> Pro→Hobby

タイムアウト対策:
- Actions全件・Issue全コメント・巨大logを取らない
- specific run/comment/resourceだけ
- 一度に1作業

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / FULL_HISTORY_PINNED / RAILWAY_ONLY_ARCHIVE / PARITY_NEXT / PROTECT_TOTO / PURCHASE_FALSE`

---
