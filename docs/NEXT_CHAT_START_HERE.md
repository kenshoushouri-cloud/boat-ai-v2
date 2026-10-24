# 新チャット開始用短縮案内（2026-10-24 17:10 JST）

@GitHub

新競艇AI開発プロジェクトNo.2の続き。Repo `kenshoushouri-cloud/boat-ai-v2`。
まず`docs/HANDOFF_LATEST.md` → その指定先`docs/LIVE_HANDOFF_20261024_1710_COMPACT.md` → このファイル、の3点だけを確認。52KBに肥大化した旧handoff・過去史は一括取得せず、必要な特定事実のみ参照。SHA/run/件数/容量は固定値と見なさない。

V5は研究成果を再利用して非購入限定稼働を構築する。6艇確率/120券PL/非購入shadow記録/日次合成評価の隔離テスト18/18 PASS。ただし実ROI、真のfirst-capture、モデルT1.00 vs T2.20不一致は未解消。ConoHaの共有13VIEWは維持、stage venues初回1/13、物理切替0/13 NO-GO。Drive403 write STOP、既存collector/タイマー継続、BUYは禁止。

最新2026-10-24 17:10 Termius read-only：10/20展示の`historical`は0、`conoha_forward`28レース×6艇完全/計168行（時刻ラベル締切前だが原本証拠ではない）、別の`conoha_timeout_probe`1レース×6艇（研究/運用自動採用しない）。10/20全144R、完全出走144、公式結果144、clean K course132、厳格なhistorical学習候補0。重複レースの可能性があるため28+1を全体のuniqueとは断定しない。

**Next ONE task**：2026-10-24 18:20 writer監査PASS：4timer active、対象serviceは瞬間的にinactive、cron該当0、DB他セッション0（全writerの認証ではない）。ユーザーは一括準備を希望し必要な準備を承認。GitHub `deploy/conoha/v5_cutover_one_command_prepare_20261024.sh`をアップロード済み。**次は1コマンドでConoHa上に保存先13関係/書込監査/容量/ローカル保全/波分け計画/03:30候補ゲートの準備レポートを生成。** DBコピー・timerインストール・切替は含まない（未達ゲートのためNO-GO）。独立復元/全writer/差分追従/自動復帰後に本番の別承認。現行stage1/13/live0/13、Drive403 STOP、BUY OFF。
