# 新しいチャットへの最短案内（2026-10-24 19:06 JST）

@GitHub

新競艇AI開発プロジェクトNo.2を続ける。repo `kenshoushouri-cloud/boat-ai-v2`。最初に`docs/HANDOFF_LATEST.md`→`docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`→本ファイルのみ参照。過去hand-offを大量に読み直さない。毎回同じ保存先探索をしない。

V5研究資産（6艇確率/120券/予測記録/日次評価）再利用、2025-07以降、10月末非購入限定運用目標。累計29/29は19:06以前の**合成テスト**であり実コピー・ROI・モデル証明ではない。現状DB`railway`13系統原本`public.v2_*`、`boat_data.*`はVIEW、隔離stageは`boat_data_stage.venues`のみ24件。**GitHubコードのコピー先も`boat_data_stage.*`に統一**（旧`v5_data.raw_*`は古い案）。既存差分コードを再利用。物理切替0/13 NO-GO。Drive書込403 STOP、BUY OFF。夜間手動不可、将来03:30候補だが無人タイマー未予約。

**Next ONE task：**19:45 DDL候補12/12・venues保護・ROLLBACKのread-only PASS（source odds snapshot約666MB）。GitHub `deploy/conoha/v5_stage_12_bootstrap_guarded.py`：12空stage一括トランザクション生成、デフォルトプレビュー。失敗時全ロールバック。別承認・独立復元証拠ゲートがない`--apply`を拒否。 `tests/test_v5_stage_12_bootstrap_guarded.py` の6合成テスト新設・**未実行**。次は1回のTermiusで隔離6テスト＋offline DDLプラン作成を実行。DB変更禁止、旧venues24行保持、stage1/13・live0/13 NO-GO、Drive403 STOP、BUY OFF、03:30未予約。
