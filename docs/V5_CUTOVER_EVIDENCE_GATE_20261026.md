# V5 切替前・証拠ゲート（2026-10-26 JST）

## 確認済み
- ConoHa `railway` の旧原本 `public.v2_*` 13系統は収集稼働を維持。`boat_data.*` 13 VIEWは旧原本参照のまま。
- `boat_data_stage.*` 13物理表の初回複製13/13、PK/列構造一致13/13。10/25会場・レース、10/26 03:05–03:16残11系統の各表差分COMMITと行/主キー範囲の照合成功。これは**表ごとの実行時点**の一致であり継続CDCではない。
- 自動購入OFF、本番切替0/13、旧収集停止なし。新規47系統の増設や重複外部取得は禁止。

## 依然として未合格（本番物理切替NO-GO）
1. **バックアップ：** 10/23–24ローカルdumpの同VPS SHA/TOC PASSのみ。VPS外の新鮮な世代の暗号ファイル受信・復号・独立DBへの全復元と回復試験は未実施。旧10/19のDrive保管だけでは足りない。Drive 403の新規書込再試行禁止。
2. **収集writerと読取経路：** 全systemd/cron/子worker/DDL/直接SQL/接続ロールを網羅した書込ルート証明は未完。旧原本と新stageへ書込が分裂する切替は厳禁。
3. **同一時点の完全性：** 13表を一つの整合スナップショットで全PK/全列双方向照合した証拠なし。COPY後の追加/更新/削除と最新の捕捉時刻は常に変化する。予測時刻より後の観測・後日補完を前向きROIに流用しない。
4. **新writer準備：** 独立シーケンス/default/IDENTITY、GRANT、VIEW依存、更新/復旧/二重書込防止のゲート未合格。
5. **自動復旧：** reader-only shadowの実稼働・障害時自動切戻し・非購入canaryの実証未完。

## 今すぐ進める一作業（旧経路に手を触れない）
- `deploy/conoha/v5_previous_day_core_row_parity_readonly_20261026.sql` で**直前JST日の4系統（races/results/entries/racer_results）**について一つの `REPEATABLE READ READ ONLY` snapshot内で全行JSON正規化・不足/余剰/内容不一致を検査。これは限定範囲の読取検査であり4/13の試験だけ。全13同期完了や本番切替GOと解釈しない。
- 既存 `deploy/conoha/v5_active_writer_routes_readonly_20261022.py` は実VPSの役割別参照/書込ヒント調査に再利用可。staticのヒントはwriter網羅証明でない。
- オフサイト実復元は `docs/V5_INDEPENDENT_RESTORE_EXECUTION_RUNBOOK_20261024.md` に従う。秘密鍵はGitHub/チャット/スクショに出さない。有料契約、再起動、既存Drive原本上書き不要。

**判定：V5 paper/read-only研究は既存VIEWで先行可能。本番物理切替・旧原本削除・BUYはNO-GO。**
