# boat-ai-v2

競艇3連単AI予想システム。BOAT RACE公式データ取得、Railway PostgreSQL保存、PRE候補抽出、直前情報取得、FINAL判定、LINE通知、結果回収、Shadow検証、バックテスト、データ品質監査までを含む運用システムです。

## Source of truth

- **GitHub**: コードの正
- **Railway**: 本番実行環境の正
- **Railway PostgreSQL**: データの正
- **Supabase**: 旧構成。現行本番DBではありません

Railway側のService / Start Command / Variables / CronはGitHubだけでは完全確認できないため、運用変更時はRailwayの現在値と照合してください。

## 本番DB

接続は `DATABASE_URL` を使用します。

主要テーブル:

- `v2_races`
- `v2_race_entries`
- `v2_results`
- `v2_odds_trifecta`
- `v2_exhibition`
- `v2_race_weather`
- `v2_feature_snapshots`
- `v2_realtime_odds_snapshots`

出走表テーブルは **`v2_race_entries`** です。`v2_entries` ではありません。

## 主要本番入口

### 日次データ準備

```text
run_daily_data_prepare_pg.py
  -> repair_month_all_pg.py
```

当日race / entries / 事前oddsを準備します。事前取得oddsを確定値扱いしないため、`run_daily_data_prepare_pg.py` は `ODDS_IS_FINAL=0` を強制します。

### PRE window pipeline

```text
run_window_pipeline_pg.py
  -> run_odds_window_pg.py
  -> collect_v24_motor2_forward_shadow_pg.py
  -> run_pre_window_pg.py
       -> v24_pre_candidate_notifier_pg.py
       -> collect_candidate_filter_shadow_pg.py
```

基本window:

- `morning`: 08:30〜10:15
- `day`: 09:45〜15:00
- `night`: 14:45以降

境界レースの取りこぼし防止のためwindowは一部重複します。

`run_pre_window_pg.py` には historical / future / live 判定、live guard、replay safetyがあります。過去日replayでは原則 `DRY_RUN=1` / `TEST_MODE=1` を使用してください。

### FINAL pipeline

```text
run_final_pg.py
  -> v25_final_realtime_pipeline_pg.py
       -> v21_realtime_collector_pg.py
       -> collect_v24_motor2_forward_shadow_pg.py   # Motor2 FINAL Shadow
       -> collect_n02_windlt4_final_shadow_pg.py    # N02 FINAL Shadow
       -> run_v22_targeted_pg.py                    # production decision
       -> v22_exhibition_shadow_pg.py               # Exhibition Shadow
       -> v23_line_notifier_batch_pg.py             # LINE notification
```

Motor2 / N02 / 展示Shadowは、現状では本番BUY/WATCH/SKIPやLINE通知対象を直接変更しない検証系です。ただし本番pipelineから呼ばれているため、未使用ファイルとして削除しないでください。

### Nightly

```text
run_nightly_results_pg.py
```

現在の主なstage:

1. 当日結果取得 (`repair_month_all_pg.py`)
2. Candidate Filter Shadow当日評価
3. Candidate Filter累積report
4. N02 Forward report
5. 展示Shadow当日評価
6. 展示Shadow累積report
7. N02 WIND_LT4 Variant Forward比較
8. Motor2 Forward Shadow当日評価
9. Motor2 PRE/FINAL累積比較report

Nightlyから呼ばれるevaluate/reportファイルも本番付随依存です。

## 定期レポート

PostgreSQL版:

- `run_monthly_performance_report.py` -> `v27_performance_report_line.py`
- `run_daily_status_report.py` -> `v28_daily_status_report_line.py`

`v27` / `v28` は現在Railway PostgreSQL版です。

## データ補修

中心ファイルは `repair_month_all_pg.py` です。

主な環境変数:

- `REPAIR_START_DATE`
- `REPAIR_END_DATE`
- `REPAIR_VENUES`
- `REPAIR_RACE_NOS`
- `REPAIR_RACE_IDS`
- `REPAIR_DO_RACES`
- `REPAIR_DO_RESULTS`
- `REPAIR_DO_ODDS`
- `REPAIR_WORKERS`
- `REPAIR_ODDS_WORKERS`
- `REPAIR_SLEEP_SEC`
- `ODDS_IS_FINAL`

`repair_month_all_pg.py` はrace / entries / results / odds取得の基盤です。本番依存があるため安易に移動・分割しないでください。

## データ品質上の重要事項

- 締切時刻はrace_noごとに取得し、別Rの時刻へ誤fallbackしないこと
- 三連単ticketは1〜6号艇、3艇重複なしの有効ticketだけを扱うこと
- Motor/Boat率は0〜100の範囲を検証すること
- 会場コードは公式対応を維持すること
  - `06` 浜名湖
  - `08` 常滑
  - `09` 津
  - `21` 芦屋
  - `23` 唐津

## Shadow / Researchの原則

予測改善は次の順で行います。

1. データ品質確認
2. Historical analysis
3. OOS
4. Walk-forward
5. Forward Shadow
6. Live sample蓄積
7. 本番採用判断

高ROIでも単発高配当依存の場合は採用しません。`n`, `bets`, `hit count`, `ROI`, `max payout`, `single-hit share`, venue/month/odds分布、train/OOS差を確認します。

目標は候補数を増やすことではなく、**期待値の低いレースを見送る能力を高めること**です。

## LINE通知安全策

主な変数:

- `DRY_RUN`
- `TEST_MODE`
- `DAILY_LINE_LIMIT`
- `MONTHLY_LINE_LIMIT`
- `MAX_ITEMS_PER_MESSAGE`
- `BATCH_NOTIFY`

historical test / replayでは誤通知防止を最優先してください。

## Repository classification

詳細なA〜G分類、production exceptions、研究/保守ファミリーの扱いは `REPOSITORY_CLASSIFICATION.md` を正とします。

- **A Production**: 本番入口・本番必須依存
- **B Production Shadow**: 本番jobから呼ばれるShadow / evaluator / report
- **C Research**: analyze / backtest / feature_lab / walk-forward等
- **D Maintenance**: repair / diagnose / debug / probe / inspect / audit等
- **E Legacy Supabase**: 現在、既知の残存実コードなし
- **F Delete confirmed**: 現在、既知の残存対象なし
- **G Metadata / Docs**: README、分類文書、設定メタデータ等

ファイル名やv番号だけで新旧を判断せず、`import`, `runpy.run_path`, `subprocess`, Railway Start Commandを確認してから整理します。

## Repository cleanup status

2026-08-21に旧Supabase / 旧JOB_MODE群を段階的に削除しました。

削除済みの主な群:

- 不可視Unicode重複 `diagnose_motor2_parser_pg.py⁠`
- `app/jobs/*`
- `data_pipeline/*`
- 旧 `backtest/*` ディレクトリ
- `db/client.py`
- `config/settings.py`
- 旧 `models/*`
- 旧 `betting/*`
- 旧 `notifications/*`
- `main.py`
- `Procfile`
- `run_pre_day_pg.py`
- `run_pre_night_pg.py`
- `run_nightly_results_learning.py`
- `v26_nightly_results_learning.py`
- `run_odds_retention_cleanup.py`
- `v29_odds_retention_cleanup.py`

現行PostgreSQL本番コード、Shadow、研究用 `backtest_*.py` / `analyze_*.py` はこのcleanupで削除していません。

## Railwayとの対応

過去に確認されている主なService名:

- `cron-data-prepare`
- `cron-racer-course-stats`
- `cron-monthly-report`
- `test-beforeinfo-extra`
- `cron-final-check`
- `cron-window-morning`
- `cron-window-day`
- `cron-window-night`
- `cron-nightly-results`
- `cron-daily-report`

これはGitHub内コードだけから現在値を保証できる一覧ではありません。Railwayへ変更を加える前に、Service一覧、Start Command、Cron、Variables、deployment sourceを現在のRailway設定と照合してください。

## Secret management

以下をGitHubへcommitしないでください。

- `DATABASE_URL`
- LINE token / user/group IDなどのsecret
- API key
- password

Railway Variables / service references等を使用します。
