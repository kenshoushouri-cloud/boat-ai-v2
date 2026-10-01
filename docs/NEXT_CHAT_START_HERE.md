# Next Chat Start Here

Paste the block below into a new chat.

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を最優先で確認してください。

読むのは次の3点だけです。
1. `docs/HANDOFF_LATEST.md`
2. そこから指定されている current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古い `LIVE_HANDOFF_*`、`PROJECT_HANDOFF.md`、`CURRENT_STATE.md`、dated purpose/timeline handoff は履歴です。特定の過去判断を確認する必要がある場合だけ参照してください。

その後、handoff内のSHA・run・件数を固定値とせず、**一度に1作業だけ**liveで再取得してください。最初に current `main`、次にその1作業に必要な PR / Actions / Issue #42 / Railway Production / PostgreSQL evidence だけを確認してください。

固定ルール:
- GitHub `main` = code Source of Truth
- Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4 = permanently UNAVAILABLE
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / clean evidence contract
- historical reconstructionはprospective gateへ加算しない
- `purchase_action=false`
- Railway plaintext Variablesを列挙しない / `list_variables`を呼ばない
- Railway Agentは通常MCPで取得不能な場合だけ
- destructive/high-impact操作は対象を明示して個別承認を取る

現在の優先順位:
1. daily prospective evidenceを落とさない
2. historical writer `36703692641` を重複triggerなしで継続
3. 2026-10-03 billing boundaryへ向けPro -> Hobby準備
4. Railway backupと暗号化logical archiveは確保済み
5. **次の1作業はProductionから隔離したrestore drill**
6. restore/parity前にhistorical DELETE・volume削除・Production切替・plan変更をしない
7. recovery完了後は `recent_form -> matched-readiness -> matched-contract backtest -> V5 review`

タイムアウトとトーク容量対策のため、途中経過の長文表示は不要です。**1作業完了ごとに短く結果だけ報告**してください。

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / PURCHASE_FALSE`

---
