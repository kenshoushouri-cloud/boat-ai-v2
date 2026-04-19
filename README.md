# boat_ai_v2

競艇 3連単専用 v2 システム

## 主な機能
- 3連単予想
- EVベース買い目選定
- 推奨レースのみ通知
- 前日レポート
- 結果取得
- 通知ログ保存

## 実行ファイル
- `python main.py`  
  単レースのテスト実行

- `python run_day_jobs.py`  
  昼開催の推奨レース通知

- `python run_night_jobs.py`  
  夜開催の推奨レース通知

- `python run_results.py`  
  前日結果の取得と保存

- `python run_report.py`  
  前日レポートの作成と通知

## 必要設定
`config/settings.py` に以下を設定
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `MODEL_VERSION`

## 本番運用想定
- Railway: ジョブ実行
- GitHub: コード管理
- Supabase: データ保存
- LINE Developers: 通知
- Pythonista: 補助運用
