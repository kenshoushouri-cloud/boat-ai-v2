# V5 切替前・証拠ゲート（2026-10-26 JST）

## 確認済み
- ConoHa `railway` の旧原本 `public.v2_*` 13系統は収集稼働を維持。`boat_data.*` 13 VIEWは旧原本参照のまま。
- `boat_data_stage.*` 13物理表の初回複製13/13、PK/列構造一致13/13。10/25会場・レース、10/26 03:05–03:16残11系統の各表差分COMMITと行/主キー範囲の照合成功。これは**表ごとの実行時点**の一致であり継続CDCではない。
- 自動購入OFF、本番切替0/13、旧収集停止なし。不要なデータ系統増設や重複外部取得は行わない。

## 依然として未合格（本番物理切替NO-GO）
1. **バックアップ：** 10/23–24ローカルdumpの同VPS SHA/TOC PASSのみ。VPS外の新鮮な世代の暗号ファイル受信・復号・独立DBへの全復元と回復試験は未実施。旧10/19のDrive保管だけでは足りない。Drive 403の新規書込再試行禁止。
2. **収集writerと読取経路：** 全systemd/cron/子worker/DDL/直接SQL/接続ロールを網羅した書込ルート証明は未完。旧原本と新stageへ書込が分裂する切替は厳禁。
3. **同一時点の完全性：** 13表を一つの整合スナップショットで全PK/全列双方向照合した証拠なし。COPY後の追加/更新/削除と最新の捕捉時刻は常に変化する。予測時刻より後の観測・後日補完を前向きROIに流用しない。
4. **新writer準備：** 独立シーケンス/default/IDENTITY、GRANT、VIEW依存、更新/復旧/二重書込防止のゲート未合格。
5. **自動復旧：** reader-only shadowの実稼働・障害時自動切戻し・非購入canaryの実証未完。

## 2026-10-26 06:17 JST 前日4系統の実機確認
- 2026-10-26 06:17 JST Termius実機：前日10/25の `races`168/168・`results`168/168・`entries`1008/1008 は全列・キー同一snapshot PASS。不足/余剰/異値0。`racer_results` は原本0/ステージ0で `HOLD_GAP_OR_NO_SOURCE`。**転送漏れとは言えないが、公式K-file詳細6艇の原本収集不足の可能性**。ソース `v5/conoha_midnight_results_pg.py` は通常のレース単位 `v2_results` のみ補完し、6艇詳細 `v2_result_entries` は別 `save_k_day_results_pg.py` がK-fileから保存（明示CONFIRM要）。`v5_data_views_v1.sql`にも10/7以降のK詳細欠損の既知注記。勝手にKデータ補完/外部取得を実行しない。

## 今すぐ進める一作業（旧経路に手を触れない）
- **Next ONE task:** GitHub登録済 `deploy/conoha/v5_k_result_entries_recent_gap_readonly_20261026.sql`（commit `c95e87cc8b12dadec7f24605f905448030216372`）をConoHaでREAD ONLY実行し、直近15日(前日まで)の詳細着順について原本・stageの6艇充足、最新race_id、日別欠損を確認する。**実VPSでの検査未実行**。欠損が原本起因ならK補完の実施可否を安全gateで別途設計。旧収集・stage13表維持、連続CDC/オフサイト独立復元/物理切替は未証明、BUY OFF。
- 既存 `deploy/conoha/v5_active_writer_routes_readonly_20261022.py` は実VPSの役割別参照/書込ヒント調査に再利用可。staticのヒントはwriter網羅証明でない。
- オフサイト実復元は `docs/V5_INDEPENDENT_RESTORE_EXECUTION_RUNBOOK_20261024.md` に従う。秘密鍵はGitHub/チャット/スクショに出さない。有料契約、再起動、既存Drive原本上書き不要。

**判定：V5 paper/read-only研究は既存VIEWで先行可能。本番物理切替・旧原本削除・BUYはNO-GO。**
