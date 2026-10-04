# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_RECENT_FORM_14D.md`

次チャットで読むのは次の3点だけ。
1. `docs/HANDOFF_LATEST.md`
2. 上記 current compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoffは履歴扱い。次の1作業に必要なlive状態だけ再取得する。

Current:
- 目的: 競艇AIを本番運用可能な状態まで完成させる。
- 運用開始目標: **2026年10月中旬**。
- 最優先経路: **不足データ完了 → 最終整合性確認 → バックテスト → 結果確認 → 過去データ移行/保持範囲確定 → 運用開始**。
- Production data SoT: `postgres-hobby-fullhistory-candidate-v4`
- Railway: Hobby / candidate-v4 RAM cap 1GB
- Historical Recent Form: **2026-08-05まで完了**
- 次の固定範囲: **2026-08-06..2026-08-19**
- Railway cost hard target: **月額USD 20以下、安いほど良い**
- Railway Agent / Railway AI禁止
- `list_variables`禁止
- purchase / plan / volume resize禁止
- 1回に1作業、短い出力、Issue #42全コメント取得禁止

`MID_OCT_LAUNCH / RECENT_FORM_NEXT / BACKTEST_CRITICAL_PATH / COST_LE_20 / NO_RAILWAY_AGENT`
