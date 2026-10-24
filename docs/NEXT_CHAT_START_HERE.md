# 新競艇AI開発プロジェクトNo.2｜新チャット開始案内（2026-10-24 22:10）

@GitHub
@Railway

Repo: `kenshoushouri-cloud/boat-ai-v2`。

最初に **1. `docs/HANDOFF_LATEST.md` → 2. 指定先`docs/LIVE_HANDOFF_20261024_2210_COMPACT.md`全文 → 3. 本ファイル**だけ読み、古いhandoff/PROJECT_HISTORY/長いworkflowは大量参照しない。トーク容量とツール呼出を抑え、1回1作業。Termiusは短い貼付コード1つ。必要な変更はlive SHAで、GitHubの短縮引き継ぎ更新。

**最優先方針**：既存ConoHa原本収集を止めず、`railway.public.v2_*`13系統→`boat_data_stage.*`への一方向段階複製／差分同期。既存`boat_data.*`の13個非更新VIEWを使うV5 read-only実データbacktest・購入なしshadow研究はstage完成を待たず先行。正式な時点証拠がない過去値は実ROI/Forward実証に混ぜない。V5用venues stage24行だけあり、残12物理table未作成、原本物理切替0/13。旧データは既に複数保管先にあり、毎回探し直さない。Google Drive現行外部復元は未証明、Drive403新書込STOP、BUY OFF。

**時間の重要な訂正**：5分forward公式展示/オッズタイマーはGitHub定義で07:00〜23:55 JST限定、03:30には起動しない。夜間23:00収集後の結果補完は現行GitHub01:20/02:20/03:20。**ユーザー希望の早期化候補00:45/01:30/02:15**（既存提案`deploy/conoha/boat-v5-midnight-catchup.timer.proposed-early-20261024`）はまだConoHaへ未設置。03:30〜04:00は将来shadow**readerだけ**切替候補であり、本番自動切替未予約。

**Next ONE task**：ConoHaに実設置されている結果補完timer/23時night service・過去journal・競合状態をまずread-only監査し、結果補完を00:45/01:30/02:15へ安全に変えるコード/rollback手順を準備。同時にGitHub既存V5 scorer＋VIEWからの小規模read-only 2025-07以降backtestを実装。勝手なtimer変更・systemd停止・stage CREATE/COPY・03:30予約・BUYは禁止。すでにユーザー回答済みの保存先/希望を質問し直さない。
