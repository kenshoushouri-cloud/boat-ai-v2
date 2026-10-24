# 新チャット開始用短縮案内（2026-10-24 17:10 JST）

@GitHub

新競艇AI開発プロジェクトNo.2の続き。Repo `kenshoushouri-cloud/boat-ai-v2`。
まず`docs/HANDOFF_LATEST.md` → その指定先`docs/LIVE_HANDOFF_20261024_1710_COMPACT.md` → このファイル、の3点だけを確認。52KBに肥大化した旧handoff・過去史は一括取得せず、必要な特定事実のみ参照。SHA/run/件数/容量は固定値と見なさない。

V5は研究成果を再利用して非購入限定稼働を構築する。6艇確率/120券PL/非購入shadow記録/日次合成評価の隔離テスト18/18 PASS。ただし実ROI、真のfirst-capture、モデルT1.00 vs T2.20不一致は未解消。ConoHaの共有13VIEWは維持、stage venues初回1/13、物理切替0/13 NO-GO。Drive403 write STOP、既存collector/タイマー継続、BUYは禁止。

最新2026-10-24 17:10 Termius read-only：10/20展示の`historical`は0、`conoha_forward`28レース×6艇完全/計168行（時刻ラベル締切前だが原本証拠ではない）、別の`conoha_timeout_probe`1レース×6艇（研究/運用自動採用しない）。10/20全144R、完全出走144、公式結果144、clean K course132、厳格なhistorical学習候補0。重複レースの可能性があるため28+1を全体のuniqueとは断定しない。

**Next ONE task**：17:39 六代表日展示保存カバレッジを確認：2025-07 155/156、2025-10 141/144、2026-01 165/168、2026-04 132/132、2026-07 167/168、2026-10 29/144。**既存データ保存先は固定 `docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md` 参照。毎チャットの保存先再探索はしない。** GitHubの`deploy/conoha/v5_stage_13_batch_gate_readonly_20261024.sql`で13ソースの物理stage準備を1回のread-onlyで点検、その結果からまとめて段階COPY+差分追従（別承認）を準備。V5 scorerは既存VIEWから先行接続。旧stage venues二重COPY、VIEW/BUY/Drive無断切替を禁止。
