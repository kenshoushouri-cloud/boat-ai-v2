# 新しいチャットへの最短案内（2026-10-24 19:06 JST）

@GitHub

新競艇AI開発プロジェクトNo.2を続ける。repo `kenshoushouri-cloud/boat-ai-v2`。最初に`docs/HANDOFF_LATEST.md`→`docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`→本ファイルのみ参照。過去hand-offを大量に読み直さない。毎回同じ保存先探索をしない。

V5研究資産（6艇確率/120券/予測記録/日次評価）再利用、2025-07以降、10月末非購入限定運用目標。累計29/29は19:06以前の**合成テスト**であり実コピー・ROI・モデル証明ではない。現状DB`railway`13系統原本`public.v2_*`、`boat_data.*`はVIEW、隔離stageは`boat_data_stage.venues`のみ24件。**GitHubコードのコピー先も`boat_data_stage.*`に統一**（旧`v5_data.raw_*`は古い案）。既存差分コードを再利用。物理切替0/13 NO-GO。Drive書込403 STOP、BUY OFF。夜間手動不可、将来03:30候補だが無人タイマー未予約。

**Next ONE task：**21:04バックアップ検査：`railway` SHA/bytes/TOC PASS後、記録パスのarchive読み取れず停止（欠損確定ではない）。GitHub `deploy/conoha/v5_stage_backup_capacity_gate_readonly_20261024.sh`を修正、`/var/backups`以下深さ3以内の既存archive dumpを名前+bytes+SHA256一致のみで自動照合。修正後未実行。次は同スクリプトをTermiusから1回再実行し、両dumpとWAL/空き容量を確認。Drive/DDL/COPY/停止なし、stage1/13/live0/13 NO-GO、03:30未予約。
