# 新チャット開始用短縮案内（2026-10-24 17:10 JST）

@GitHub

新競艇AI開発プロジェクトNo.2の続き。Repo `kenshoushouri-cloud/boat-ai-v2`。
まず`docs/HANDOFF_LATEST.md` → その指定先`docs/LIVE_HANDOFF_20261024_1710_COMPACT.md` → このファイル、の3点だけを確認。52KBに肥大化した旧handoff・過去史は一括取得せず、必要な特定事実のみ参照。SHA/run/件数/容量は固定値と見なさない。

V5は研究成果を再利用して非購入限定稼働を構築する。6艇確率/120券PL/非購入shadow記録/日次合成評価の隔離テスト18/18 PASS。ただし実ROI、真のfirst-capture、モデルT1.00 vs T2.20不一致は未解消。ConoHaの共有13VIEWは維持、stage venues初回1/13、物理切替0/13 NO-GO。Drive403 write STOP、既存collector/タイマー継続、BUYは禁止。

最新2026-10-24 17:10 Termius read-only：10/20展示の`historical`は0、`conoha_forward`28レース×6艇完全/計168行（時刻ラベル締切前だが原本証拠ではない）、別の`conoha_timeout_probe`1レース×6艇（研究/運用自動採用しない）。10/20全144R、完全出走144、公式結果144、clean K course132、厳格なhistorical学習候補0。重複レースの可能性があるため28+1を全体のuniqueとは断定しない。

**Next ONE task**：18:56 ConoHa 13-source key/default/PK/sequence gate PASS（13 rows/ROLLBACK）。既存`deploy/conoha/boat_shared_staging_delta_plan_offline.py`に完全PKのINSERT/UPDATE/DELETE純粋差分計画あり。GitHub新`v5/offline_stage_chunk_copy_sql.py`（主キー順1〜500行/明示カラム/安全なSQL生成、実DB未接続）とテスト6件（**未実行**）追加。既存の`boat_data_stage.*`と新候補の`v5_data.raw_*`でstage名に相違→本番DML前に一本化必須。次は6テスト隔離実行、次に本物の低負荷COPY executor＋差分同期を作る。stage1/13/live0/13 NO-GO、03:30自動未予約、Drive403 STOP、BUY OFF。
