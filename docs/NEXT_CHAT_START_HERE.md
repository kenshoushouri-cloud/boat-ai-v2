# Next Chat Start Here

Paste the block below into a new chat.

---

@GitHub  
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に GitHub repository `kenshoushouri-cloud/boat-ai-v2` を確認してください。

読むのは次の3点だけです。
1. `docs/HANDOFF_LATEST.md`
2. そこから指定されている current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古い `LIVE_HANDOFF_*`、`PROJECT_HANDOFF.md`、`CURRENT_STATE.md`、dated purpose/timeline handoff は履歴です。特定の過去判断が必要な場合だけ参照してください。

その後、handoff内のSHA・run・件数を固定値とせず、**一度に1作業だけ** live で再取得してください。最初に current `main`、次にその1作業に必要な GitHub / Issue #42 / Railway / PostgreSQL evidence だけを確認してください。

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

現在:
- backup + encrypted restore/parity-verified archive secured
- retention policy = **FULL_HISTORY_PINNED**
- isolated 5 GB candidate = `postgres-hobby-fullhistory-candidate-v3`
- ENOSPC診断で不足indexを特定
- `ux_v2_venues_venue_id` はcandidate-only repair済み
- 残るblockerは `ux_v2_odds_trifecta_race_ticket`
- **次の1作業 = 5 GB制約内でremaining indexをcandidate-onlyで解決し、その後exact parityを再確認**
- parity承認前にProduction切替・historical DELETE・volume削除/resize・plan変更をしない

タイムアウト対策:
- GitHub Actions全件一覧、Issue全コメント、巨大logなどをまとめて取得しない
- 必要なrun / page / resourceだけを限定取得する
- 途中経過は短く、1作業完了ごとに結果だけ報告する

`READ_HANDOFF_LATEST / ONE_TASK_AT_A_TIME / AVOID_BULK_OUTPUT / FULL_HISTORY_PINNED / 5GB_CANDIDATE / PARITY_BEFORE_CUTOVER / PURCHASE_FALSE`

---
