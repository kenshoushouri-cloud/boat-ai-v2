# 新チャット起点（2026-10-26、V5優先）

@GitHub
@Railway

Repository `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md` → 指定compact → 本ファイルのみ参照。過去の長文ログは必要箇所だけ。

ConoHaの旧 `public.v2_*` にcollectorが書込中、13 `boat_data` VIEWは旧原本参照、V5 stage13物理表の初回+表別差分追込済み（10/26 03:16の時点、CDCなし）。正式writer cutover0/13、BUY OFF。V5 LIVE VIEW読み取り専用5分shadow monitorが起動したが、実V5予測計算はまだ未稼働。旧collectorは停止不可、odds/展示/気象の再現不可能な時点観測を保護。独立バックアップ復元gateも未完。

10/26朝 collectorは07:34時点200/288実行中、failed=0、丸亀8艇で選手成績解析の13値一括NULL疑い。13項目全部必須は不採用、**正当な未集計は高評価選手を減点せず**、解析失敗と出所不明はHOLD。pure policy `v5/entry_quality_policy.py` と synthetic tests追加済み（実行未検証）。稼働中コードには未反映。`docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`参照。

2026-10-26 07:52 JST、ユーザーのConoHa Termiusで morning.service の朝07:00開始処理が **07:45:54 JST 正常完了**：`progress race/result: 288/288 success=144 no_race=144 failed=0`, `Finished boat-v5-daily@morning.service`, `ActiveState=inactive Result=success ExecMainStatus=0`。`no_race` はHTMLにレース出走表が無い等でスキップした数であり、144中止を意味しない。丸亀（15）の `ENTRY_STATS_PARSE_FAILED` 8艇程度は朝処理全体の成功と別のデータ品質課題として残る。今日のV5 5分読取専用shadowは07:12にActive確認済、07:45以降の稼働状況は未確認。現在もV5実モデル推論/予測保存は未確認、stage writer完全切替0/13、BUY OFF。

2026-10-26 07:56 JST Termius実機：V5 read-only shadow timer=active（次08:00）、07:45/07:50/07:55のログ正常。07:45に元VIEW 138R、07:50と07:55に144R。次の6レースは全てentries=6/racers=6、exhibition=0/odds=0で`WAIT_INPUT`、`structurally_ready=0`。直近締切=08:35（21_01）、次08:47（10_01）。**正常入力監視＝予測モデル稼働ではない**。GitHub`boat-v5-forward-window.timer`は07..23の5分刻み、`v5/conoha_realtime_window_pg.py`は締切9〜24分前のみ処理、毎回最大2Rを公式サイト取得する。08:35の最初の取得候補は予定上08:15頃なので、07:55の展示/oddsゼロだけで障害とは判断できない。収集タイマーがlive稼働した証拠は別途必要。

10/26 10:12:40 JST Termius：V5専用stageの`races`だけ日中guarded差分同期完了。`DELTA_VERIFIED races source_rows=74208 stage_rows=74208 insert_update_delete=[144,0,0] bounded_windows=19`、`DELTA_TABLE_COMMITTED`、stage-only、旧writer/V4原本/13 LIVE VIEW untouched、継続CDCなし、BUY OFF。空き62.41GiB。残り11系統の10/26最新データは夜間同期未実施。V5本番prediction/writer cutoverは未実施。

**Next ONE task:** Termiusに以前と同じ`deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql` をread-only実行してもらい、今日の144RがV5 stageにもあり `missing_in_stage=0` であることを事後確認。既存collector/forward timer維持、データ削除・本番writer切替・BUY禁止。パス後に11表夜間同期準備と現行外部バックアップ＋独立復元を進める。
