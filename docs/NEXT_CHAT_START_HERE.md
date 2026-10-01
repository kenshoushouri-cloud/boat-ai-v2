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
- Railway `postgres-recovery` = current data SoT until explicit cutover
- V4/V5/backtest/historical collectionを保護
- TOTO `toto-ai-v1` は別プロジェクト。変更しない
- Railway内で完結する履歴/バックテスト分離を優先
- Railway plaintext Variablesを列挙しない / `list_variables`禁止
- `purchase_action=false`
- 1回に1作業、結果は短く

現在:
- candidate-v4の必須odds unique indexは再構築済み、VALID/READY。再構築しない
- candidate-v4観測: DB約3.585GB / WAL約0.537GB / actual disk約4.331GB
- 新規 `postgres-history-archive`: PostgreSQL 18 + 5GB Volume、SUCCESS、空
- データ移動・削除・writer切替は未実施
- `/railway hobby-retention-finalize-readonly` を起動済み
- **次の1作業 = 最新のretention audit結果だけを確認し、history archiveへ分離可能な候補を特定**
- その後: archive設計 -> exact parity -> writer freeze -> final sync -> zero-delta parity -> writer retarget -> explicit cutover -> smoke -> oversized legacy resource確認 -> Pro→Hobby
- `Postgres` / `Postgres-AbWo` は内容未確認。削除・resize禁止
- 10月2日中のPro→Hobby完了が目標、10月3日がbilling renewal boundary

タイムアウト対策:
- Actions全件・Issue全コメント・巨大logを取らない
- specific run/comment/resourceだけ
- 一度に1作業

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / RAILWAY_ONLY_ARCHIVE / 5GB_V4 / PROTECT_TOTO / PURCHASE_FALSE`

---
