# boat_ai_v2

競艇 3連単専用 AI予想システム v2

## 概要

- 安定モードと馬王モード（穴狙い）の2モード並行運用
- 朝の一括予想配信 + レース直前のEVベース買い目配信
- 1日800〜1,200円の投資を目安に運用

## モード説明

### 安定モード

- 確率・スコアベースで買い目選択
- 1日最大7点・100円/点
- 3連単優先・2連単保険

### 馬王モード（穴狙い）

- オッズ15倍以上の穴のみ狙う
- 1日最大5点・100円/点
- 1点勝負

## 実行ファイル

|ファイル                     |内容            |タイミング  |
|-------------------------|--------------|-------|
|`run_morning_jobs.py`    |朝まとめ予想をLINE配信 |毎朝8時JST|
|`run_pre_race_jobs.py`   |直前にEV再計算・買い目配信|5分ごと   |
|`run_results.py`         |前日結果の取得と保存    |毎朝     |
|`run_report.py`          |前日レポートの作成と通知  |毎朝     |
|`run_odds.py`            |オッズ取得         |随時     |
|`run_seed.py`            |当日レース投入       |毎朝     |
|`run_backtest.py`        |バックテスト実行      |随時     |
|`run_missing_results.py` |欠損データ補完・払戻修正  |随時     |
|`run_repair_entries.py`  |出走表NULLデータ修復  |随時     |
|`run_backfill_history.py`|過去データ一括取得     |随時     |

## 環境変数（Railwayで設定）

|変数名                        |内容                      |
|---------------------------|------------------------|
|`SUPABASE_URL`             |SupabaseプロジェクトURL       |
|`SUPABASE_KEY`             |Supabase service_roleキー |
|`LINE_CHANNEL_ACCESS_TOKEN`|LINEチャネルアクセストークン        |
|`LINE_USER_ID`             |LINE送信先ユーザーID           |
|`ENABLE_LINE_NOTIFY`       |LINE通知ON/OFF（true/false）|

## インフラ構成

- **Railway**: ジョブ実行（各サービスにCronスケジュール設定）
- **GitHub**: コード管理（privateリポジトリ）
- **Supabase**: データ保存（v2_races・v2_results等）
- **LINE Messaging API**: 予想通知配信

## Railwayサービス構成

|サービス名          |JOB_MODE |Cron (UTC)     |内容      |
|---------------|---------|---------------|--------|
|boat-v2-results|`results`|`30 17 * * *`  |前日結果取得  |
|boat-v2-seed   |`seed`   |`0 18 * * *`   |当日レース投入 |
|boat-v2-odds   |`odds`   |`30 18 * * *`  |オッズ取得   |
|boat-v2-morning|`morning`|`0 23 * * *`   |朝まとめ予想配信|
|boat-v2-prerace|`prerace`|`*/5 0-9 * * *`|直前予想配信  |
|boat-v2-report |`report` |`30 2 * * *`   |前日レポート配信|

## 主要テーブル（Supabase）

- `v2_races`: レース基本情報
- `v2_race_entries`: 出走表・選手成績
- `v2_odds_trifecta`: 3連単オッズ
- `v2_exhibition`: 展示データ
- `v2_results`: レース結果・払戻
- `v2_predictions`: 予想買い目
- `v2_notifications`: LINE通知ログ
- `v2_daily_stats`: 日次集計
- `v2_backtest_runs`: バックテスト結果サマリー
- `v2_backtest_races`: バックテスト詳細