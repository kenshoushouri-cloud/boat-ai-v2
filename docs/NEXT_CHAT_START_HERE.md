# 新しいチャットへの最短案内（2026-10-24 19:06 JST）

@GitHub

新競艇AI開発プロジェクトNo.2を続ける。repo `kenshoushouri-cloud/boat-ai-v2`。最初に`docs/HANDOFF_LATEST.md`→`docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`→本ファイルのみ参照。過去hand-offを大量に読み直さない。毎回同じ保存先探索をしない。

V5研究資産（6艇確率/120券/予測記録/日次評価）再利用、2025-07以降、10月末非購入限定運用目標。累計29/29は19:06以前の**合成テスト**であり実コピー・ROI・モデル証明ではない。現状DB`railway`13系統原本`public.v2_*`、`boat_data.*`はVIEW、隔離stageは`boat_data_stage.venues`のみ24件。**GitHubコードのコピー先も`boat_data_stage.*`に統一**（旧`v5_data.raw_*`は古い案）。既存差分コードを再利用。物理切替0/13 NO-GO。Drive書込403 STOP、BUY OFF。夜間手動不可、将来03:30候補だが無人タイマー未予約。

**Next ONE task：**21:11 バックアップ+容量 read-only PASS。archive実ファイルをbounded SHAで1件同定、railway/archiveともbytes/SHA/TOC PASS。同VPSのDBは3482+1069MB、WAL51セグメント816MB、ファイルシステム空き**67717MB（約67GB）**。移行先12物理stage=0、venues既設のみ。独立したVPS外復元は未確認、Drive403書込STOP、03:30夜間切替未予約。ConoHa VPS3.0に無料24hスナップショット機能があるが現契約版未確認で独立DB復元証拠ではない。**次は既存の外部保管バックアップで独立復元に使えるものを限定的に確認、または外部保全先を準備**。同じローカル監査を繰り返さず、Stage/差分/復帰コードをGitHubで並行開発。本番DDL/COPY/BUYは未実行。
