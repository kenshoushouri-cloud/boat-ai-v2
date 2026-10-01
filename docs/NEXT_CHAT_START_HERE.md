# Next Chat Start Here

Paste this into a new chat:

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

GitHub repository `kenshoushouri-cloud/boat-ai-v2` を最優先で確認してください。

最初に次の順で読んでください。
1. `docs/HANDOFF_LATEST.md`
2. そこから指定された current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`
4. deep-history文書は必要な場合だけ

その後、古いsnapshotを現在値と決めつけず、**作業は1つずつ**read-onlyで再取得してください。最初に current main と latest commit、その次に現在の作業に必要な Issue #42 / PR / Actions / Railway Production / PostgreSQL evidence だけを確認してください。

重要方針:
- GitHub main = code Source of Truth
- Railway PostgreSQL Production = data Source of Truth
- 2026-09-29 formal V4は永久UNAVAILABLE
- V5 gateは V4 >=20 resolved FORMAL_AVAILABLE days / S03_M2 >=100 official observations / evidence contract clean
- historical reconstructionはprospective gateへ加算しない
- `purchase_action=false`
- Railway plaintext Variablesを列挙しない、`list_variables`を呼ばない
- Railway Agentは通常MCPで取得できない場合だけ使う
- destructive/high-impact操作は対象を明示して個別承認を取る

現在の優先順位:
1. daily prospective evidenceを落とさない
2. historical不足データ回収を重複triggerなしで継続
3. 10/03 billing boundaryに向けてPro -> Hobby移行準備
4. pre-Hobby archiveは確保済みなので、**次はProductionから隔離したrestore drill**
5. restore/parity確認前にhistorical DELETE・volume削除・Production切替をしない
6. 2026-10-15前後のV5 operational-readiness reviewへ進む

タイムアウト対策として、一度に複数作業を進めず、**1作業完了ごとに短く結果だけ報告**してください。途中経過の長文表示は不要です。

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / RESTORE_BEFORE_DELETE / HOBBY_PREP / 929_UNAVAILABLE / PURCHASE_FALSE`

---
