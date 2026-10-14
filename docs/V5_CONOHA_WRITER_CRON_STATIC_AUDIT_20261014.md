# V5/ConoHa 2GB — 書込経路・cron候補の静的棚卸し（2026-10-14）

**判定：GitHub feature branch のコード調査のみ。実Railway/ConoHaサービス・DB・cron/Actionsの稼働状態は未確認。** 11ファイルで28個のコード根拠マーカー一致（**静的照合であり実行テストや稼働確認ではない**）。本資料はV5起動許可・移行・BUYの証明ではない。main/V4本番は無変更。

## 現行コードの入口・実書込み/副作用候補

|入口（静的コードから確認）|たどる先／DB更新・副作用|移行時の判定|
|---|---|---|
|`run_daily_data_prepare_pg.py`|同日限定で`repair_month_all_pg.py`を`runpy`起動、`REPAIR_DO_RACES=1`/`REPAIR_DO_ODDS=1`/`REPAIR_DO_RESULTS=0`。後者は`db_pg.upsert_rows`等で出走表・オッズ保存。非最終オッズ指定|**DB writer候補**：先行収集のV5経路とは別途機能検証。保護ロック必須、結果取得と重ねない|
|`run_window_pipeline_pg.py`|通常`run_odds_window_pg.py`の非最終オッズ更新、条件付き`collect_v24_motor2_forward_shadow_pg.py`、さらに`run_pre_window_pg.py`または`run_pre_window_deduped_pg.py`（PRE通知系）を呼ぶ|`WINDOW_RUN_PRE`の既定が有効。**V5 cronへ丸ごと流用禁止**。通知不要のV5では分離・無効化し、writer部分のみ別途審査|
|`run_window_refresh_pg.py`|`WINDOW_REFRESH_EXECUTE=1`のときのみ`run_odds_window_pg.py`へ。初期OFF、時間窓で実行|**オプションDB writer**。他のオッズ更新との重複・締切遅延回避が必要|
|`run_final_pg.py` → `v25_final_realtime_pipeline_pg.py`|`v21_realtime_collector_pg_safe.py`が展示/気象/出走/オッズ保存し、複数shadow、`run_v22_targeted_pg.py`経由の判断、最後に`v23_line_notifier_batch_pg.py`を呼ぶ。実行前にローカル対象IDファイルを初期化|**旧v25/V4周辺経路**。V5単独の収集・予想入口とは確認されていない。通知副作用があるため**丸ごとV5へ転用禁止**。TEST_MODE/DRY_RUNだけをBUY/通知無害の証明にしない|
|`run_nightly_results_pg.py`|当日対象があれば`repair_month_all_pg.py`を結果専用の`REPAIR_DO_RESULTS=1`で起動、shadow評価・報告の各段階を条件付き実行|**結果DB writerと派生更新候補**。直前収集とは異なる競走後フェーズで共通ロック、同一日再実行の挙動を別検査|
|`save_k_day_results_pg.py`|`CONFIRM_K_DB_WRITE=YES`を要し、`v2_result_entries` INSERT/UPSERT と既存`v2_results` UPDATE。6艇監査あり|**明確な結果writer**。Nightly resultsとの重複リスク。V5標準cronへ自動追加禁止|
|`db_pg.py`|`execute`、`upsert_rows`、条件付きDELETEの共通DBヘルパ|実行入口ではないが**すべての間接DB変更を調査する起点**。関数名だけで読取専用と推定しない|
|`collect_exhibition_st_forward_shadow_pg.py`|別研究系・デフォルトdry-run、オプトイン時に`v2_exhibition_st_forward_shadow` INSERT|V5主力への採用・定期実行は確認されていない。**研究writer、未統合**|

## 新V5（未配線・別審査）

- `v5/official_first_write_storage.py`：初回観測保存の**DDL/SQL文字列とreadback判定の提案のみ**。`ON CONFLICT (resource_key) DO NOTHING`、本ファイル単独ではDB通信/書込なし。
- `v5/official_first_write_executor.py`：**未デプロイ・未スケジュール**。外部注入されたDB transactionに対する`INSERT ... ON CONFLICT DO NOTHING`＋同一transactionでreadbackし、衝突/改変で例外。ただしDB上の整合性≠実際の公式締切前取得の独立証拠。別途コレクタと真正性監査が必要。
- `research/v5_strong_core_entry_form_freeze_plan.py`：**研究用・未配線**の凍結提案。DB接続/HTTP取得なし。2025-07-01以降の67週OOS実バックテストはまだ0/67で、ここから**有効なcron/学習・購入ジョブが存在するとは推定できない**。
- `ops/conoha/v5_offline_dag.py`：純粋な論理順序表示だけ（実行0）、V5 shadow予想はdisabled。実装を本番ジョブに結線しない限り収集/分析は動かない。

## 将来の2GB VPSに必要なロック範囲・投入順

1. **締切前**：出走表/公式直前情報/オッズの取得・保存（公式取得の時刻と原本凍結の真正な証拠を別保存）。V5の全DB writerが同一専用ユーザーの共通`flock`＋DB一意制約を通ること。**締切が迫れば長時間処理を開始しない**。無期限待機や後から「締切前取得」を作らない。
2. **予測**：`evidence_gate`のPASS（締切前に本当に取得/凍結した証拠あり）の場合のみV5 shadow。欠測/遅延なら`NO_PREDICTION`を残す。**通知・BUYは禁止**。
3. **競走後**：公式結果/返還等を別フェーズで収集・保存。再実行は事前一意キーと比較・原本不変確認後のみ。結果を先行予測へ漏らさない。
4. **低優先度**：結果評価→手動バックテスト。CPU/RAM/ディスク/WALの実測前に多窓を同時実行しない。リアルタイム締切前コレクタと重なる時は停止・分割する。
5. **実稼働の確定は保留**：GitHubスクリプトに入口が存在することと、**Railwayのどのcron/サービスが現在起動しているか**は別。V4本番保護のまま、VPS復旧後にread-onlyでジョブ一覧/スケジュール/DB接続設定（**値・Secrets非表示**）を監査し、重複writeがないことを確認してからConoHa側の専用systemd timerを**別承認で**構築。

## 次の1作業

ConoHaサポートの返信状況を優先確認。実機アクセス復旧までV5 writerの全ファイルの**共通ロック迂回がないか**を静的に点検できる、読取専用の検査プログラムとオフライン試験を準備する。cron有効化・環境変数設定・DB接続/書込・LINE/BUYは**一切実施しない**。バックアップ4DB原本/旧CMS鍵保護を継続。
