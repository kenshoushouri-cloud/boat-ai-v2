# 新しいチャットへの最短案内（2026-10-24 19:06 JST）

@GitHub

新競艇AI開発プロジェクトNo.2を続ける。repo `kenshoushouri-cloud/boat-ai-v2`。最初に`docs/HANDOFF_LATEST.md`→`docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`→本ファイルのみ参照。過去hand-offを大量に読み直さない。毎回同じ保存先探索をしない。

V5研究資産（6艇確率/120券/予測記録/日次評価）再利用、2025-07以降、10月末非購入限定運用目標。累計29/29は19:06以前の**合成テスト**であり実コピー・ROI・モデル証明ではない。現状DB`railway`13系統原本`public.v2_*`、`boat_data.*`はVIEW、隔離stageは`boat_data_stage.venues`のみ24件。**GitHubコードのコピー先も`boat_data_stage.*`に統一**（旧`v5_data.raw_*`は古い案）。既存差分コードを再利用。物理切替0/13 NO-GO。Drive書込403 STOP、BUY OFF。夜間手動不可、将来03:30候補だが無人タイマー未予約。

**Next ONE task：** 10/24 19:30、新stage名統一後の17テスト＋共通storage契約7テスト＝24/24 PASS（既存テストと重複あり）。ただし`--all` 実DBプレビューは `psycopg not installed` で停止。GitHub `deploy/conoha/v5_online_stage_batch_copy.py` をpsql fallback対応し、新`tests/test_v5_psql_stage_preview.py`4件追加（**未実行**）。次は/tmpで4件テスト＋`--all`の12系統catalog READ ONLY実行。ライブラリインストール不要。stage1/13・live0/13 NO-GO、03:30自動切替未予約、Drive403 STOP、BUY OFF。
