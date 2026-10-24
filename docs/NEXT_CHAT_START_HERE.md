# 新しいチャットへの最短案内（2026-10-24 19:06 JST）

@GitHub

新競艇AI開発プロジェクトNo.2を続ける。repo `kenshoushouri-cloud/boat-ai-v2`。最初に`docs/HANDOFF_LATEST.md`→`docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`→本ファイルのみ参照。過去hand-offを大量に読み直さない。毎回同じ保存先探索をしない。

V5研究資産（6艇確率/120券/予測記録/日次評価）再利用、2025-07以降、10月末非購入限定運用目標。累計29/29は19:06以前の**合成テスト**であり実コピー・ROI・モデル証明ではない。現状DB`railway`13系統原本`public.v2_*`、`boat_data.*`はVIEW、隔離stageは`boat_data_stage.venues`のみ24件。**GitHubコードのコピー先も`boat_data_stage.*`に統一**（旧`v5_data.raw_*`は古い案）。既存差分コードを再利用。物理切替0/13 NO-GO。Drive書込403 STOP、BUY OFF。夜間手動不可、将来03:30候補だが無人タイマー未予約。

**Next ONE task：**19:58 Termius `Ran 6 tests`/OK、`V5_STAGE_12_PREPARATION_FINISHED`。計画保存`/var/backups/v5_stage_12_plan_ZP9Q5IEp.txt`（SQL計画、バックアップではない）。GitHub `deploy/conoha/v5_stage_12_atomic_rollback_trial_20261024.sh`新規：12空stage CREATEを一時transaction内で実施し必ず**ROLLBACK**、別read-only接続で12個ABSENTとvenues保持を検証するリハーサル。**実DBリハーサルはまだ未実行**。次はTermiusで1回実行し結果確認。永続DDL・移行COPY/BUY/夜間03:30自動切替未許可。stage1/13/live0/13 NO-GO、Drive403 STOP。
