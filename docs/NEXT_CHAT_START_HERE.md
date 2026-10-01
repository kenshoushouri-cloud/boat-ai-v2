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

古いhandoffは履歴扱いです。SHA・run・件数・容量は固定せず、次の1作業に必要なものだけlive再取得してください。

固定:
- GitHub `main` = code SoT
- `postgres-recovery` = current Production data SoT until explicit cutover
- V4/V5 prospective evidence / historical collection / backtestを保護
- Railway内で本番/現行DBと履歴/backtest DBを分離する方針
- TOTO `toto-ai-v1` は別プロジェクト。変更しない
- Keirin Railway projectはユーザーが削除済み
- Railway plaintext Variablesを列挙しない / `list_variables`禁止
- `purchase_action=false`
- 1回に1作業、結果は短く

現在:
- candidate-v4 = 5GB cutover candidate
- 必須odds unique indexはVALID/READY、再構築しない
- `postgres-history-archive` = PostgreSQL 18 + 5GB、SUCCESS、空/reserved
- retention = **FULL_HISTORY_PINNED**
- matched historical research完了前は履歴を移動・削除しない
- `Postgres` / `Postgres-AbWo` は未確認。削除/resize禁止
- Pro -> Hobby完了目標 = 2026-10-02、billing boundary = 2026-10-03

**次の1作業:**
`postgres-history-archive` へ将来分離できる historical/backtest data を read-only で棚卸しし、依存関係とretention境界を確認する。

同じターンで data move/delete / writer freeze / sync / cutover / resize / plan change はしない。

その後:
current parity -> writer freeze -> final sync -> zero-delta parity -> writer retarget -> explicit cutover -> smoke -> rollback確認 -> oversized legacy resource整理 -> Pro→Hobby

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / RAILWAY_ONLY_2DB / FULL_HISTORY_PINNED / HISTORY_INVENTORY_NEXT / PROTECT_TOTO / PURCHASE_FALSE`

---
