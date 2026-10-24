# 新チャット開始用短縮案内（2026-10-24 17:10 JST）

@GitHub

新競艇AI開発プロジェクトNo.2の続き。Repo `kenshoushouri-cloud/boat-ai-v2`。
まず`docs/HANDOFF_LATEST.md` → その指定先`docs/LIVE_HANDOFF_20261024_1710_COMPACT.md` → このファイル、の3点だけを確認。52KBに肥大化した旧handoff・過去史は一括取得せず、必要な特定事実のみ参照。SHA/run/件数/容量は固定値と見なさない。

V5は研究成果を再利用して非購入限定稼働を構築する。6艇確率/120券PL/非購入shadow記録/日次合成評価の隔離テスト18/18 PASS。ただし実ROI、真のfirst-capture、モデルT1.00 vs T2.20不一致は未解消。ConoHaの共有13VIEWは維持、stage venues初回1/13、物理切替0/13 NO-GO。Drive403 write STOP、既存collector/タイマー継続、BUYは禁止。

最新2026-10-24 17:10 Termius read-only：10/20展示の`historical`は0、`conoha_forward`28レース×6艇完全/計168行（時刻ラベル締切前だが原本証拠ではない）、別の`conoha_timeout_probe`1レース×6艇（研究/運用自動採用しない）。10/20全144R、完全出走144、公式結果144、clean K course132、厳格なhistorical学習候補0。重複レースの可能性があるため28+1を全体のuniqueとは断定しない。

**Next ONE task**：17:55 共有13系統一括catalog gate PASS（13 rows、DB3479MB、venues stage=r、live VIEW=v）。ユーザー提案の**収集短時間停止→不足は後日取得可能な種類だけ補完**を高速移行計画に採用。停止/切替は**未実行・個別承認別**、真の直前オッズ等は再生不可の恐れ/当時原本として偽装禁止。`docs/V5_SHORT_MAINTENANCE_AND_RECOVERY_FASTPATH_20261024.md`と固定保存先`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`参照。次は既存`deploy/conoha/v5_active_writer_routes_readonly_20261022.py`等で4timer・次回起動・workerを短時間read-only棚卸し。stage1/13・live0/13、Drive403 STOP、BUY OFF。
