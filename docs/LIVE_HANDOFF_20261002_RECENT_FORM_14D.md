# Live Handoff — V5 Backtest Preparation

## 1. Goal / critical path
- 競艇AIを安全に本番運用可能な状態へ完成させる。
- 運用開始目標: **2026年10月中旬**。
- Critical path:
  **historical不足補完 → final coverage/leakage/integrity → V5 matched-contract backtest → V4 baseline比較 → 結果確認/運用方式確定 → 過去データarchive/保持最適化 → 運用開始**
- historical reconstructionはbacktest用。Prospective V4/V5 gateへ加算しない。

## 2. Current architecture
- GitHub `main` = code SoT
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`
- Production model = **V4**
- V5 = **research-only**
- Railway = Hobby
- candidate-v4 RAM cap = **1GB**
- candidate-v3 = SLEEPING / volume-data保護
- TOTO staged patchには触れない

## 3. Historical completion
- Historical Recent Form = Official K prior-day only / fill-missing-only
- leakage必須条件:
  - `SAME_DAY_RESULT_USED=0`
  - `FUTURE_RESULT_USED=0`
  - `FILL_MISSING_ONLY=1`
- Recent Formは **2026-09-30まで補完完了**
- 2026-09-17..09-30 正規run = **13,248 rows / PASS**
- 同範囲の重複runは **0 rows updated / PASS** で無害終了
- historical取得フェーズは、final read-only auditで残差が見つからない限り完了扱い

## 4. Latest safety state
- Volume current size = **4450.639872 / 5000 MB**
- WAL = **100,663,296 bytes**
- replication slots = **0**
- candidate-v4 = online / crashed 0 / recentFailures 0
- 1GB近辺までmemoryを使うことはあるためOOM監視は継続
- Railway cost hard target = **USD 20/month以下、安いほど良い**

## 5. V5 backtest intent — confirmed
過去handoffで次の方針を確認済み:
- ProductionはV4のまま
- historical coverage完了後に **matched-contract backtest**
- **current V4 / V5 candidate core / optional V5.1** を
  **same time split / no-leakage / same-contract** で比較
- 次回backtestの研究主対象は **V5 candidate core**
- V5 backtest結果だけでProductionへ自動昇格しない

## 6. Important workflow warning
- `.github/workflows/railway-data-coverage-audit.yml` は内部で
  `railway variable list` を使うため **使用禁止**
- 2026-10-04の実行はDB接続前にFAIL。Production変更なし。
- `list_variables` / `railway variable list` は今後も使わない
- candidate-v4専用read-only coverage workflow
  `.github/workflows/candidate-v4-feature-coverage-readonly.yml`
  は `list_variables` 不使用だが `workflow_dispatch` 専用

## 7. Next ONE task
**V5 candidate core の現行実装と、final matched-contract backtestの安全な実行経路を current main だけで特定する。**

- 過去handoffを大量検索しない
- まず current main のV5/backtest関連コード・workflowだけ確認
- この1作業が終わるまで別作業を始めない
- Production変更はしない

## 8. Permanent rules
- **1回に1作業**
- 出力は短くする
- read-only優先
- destructive/config変更は明示承認が必要
- Railway Agent / Railway AI禁止
- `list_variables`禁止
- purchase / plan / volume resize禁止
- Issue #42全コメント取得禁止
- SHA / run / 件数 / 容量は固定値とせず、次の1作業に必要なものだけlive再取得
- 古いhandoffは特定の過去判断が必要な時だけ参照

`MID_OCT_LAUNCH / V5_RESEARCH_BACKTEST_NEXT / V4_PRODUCTION / HIST_THROUGH_20260930 / ONE_TASK_ONLY / COST_LE_20 / NO_LIST_VARIABLES / NO_RAILWAY_AGENT`
