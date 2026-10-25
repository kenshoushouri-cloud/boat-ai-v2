# 新チャット起点（2026-10-26、V5優先）

@GitHub
@Railway

Repository `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md` → 指定compact → 本ファイルのみ参照。過去の長文ログは必要箇所だけ。

ConoHaの旧 `public.v2_*` にcollectorが書込中、13 `boat_data` VIEWは旧原本参照、V5 stage13物理表の初回+表別差分追込済み（10/26 03:16の時点、CDCなし）。正式writer cutover0/13、BUY OFF。V5 LIVE VIEW読み取り専用5分shadow monitorが起動したが、実V5予測計算はまだ未稼働。旧collectorは停止不可、odds/展示/気象の再現不可能な時点観測を保護。独立バックアップ復元gateも未完。

10/26朝 collectorは07:34時点200/288実行中、failed=0、丸亀8艇で選手成績解析の13値一括NULL疑い。13項目全部必須は不採用、**正当な未集計は高評価選手を減点せず**、解析失敗と出所不明はHOLD。pure policy `v5/entry_quality_policy.py` と synthetic tests追加済み（実行未検証）。稼働中コードには未反映。`docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`参照。

2026-10-26 07:52 JST、ユーザーのConoHa Termiusで morning.service の朝07:00開始処理が **07:45:54 JST 正常完了**：`progress race/result: 288/288 success=144 no_race=144 failed=0`, `Finished boat-v5-daily@morning.service`, `ActiveState=inactive Result=success ExecMainStatus=0`。`no_race` はHTMLにレース出走表が無い等でスキップした数であり、144中止を意味しない。丸亀（15）の `ENTRY_STATS_PARSE_FAILED` 8艇程度は朝処理全体の成功と別のデータ品質課題として残る。今日のV5 5分読取専用shadowは07:12にActive確認済、07:45以降の稼働状況は未確認。現在もV5実モデル推論/予測保存は未確認、stage writer完全切替0/13、BUY OFF。

**Next ONE task:** Termiusで既存 `boat-v5-shadow-live-readonly.service` の07:45以降のログをread-only検査し、288タスク完走後の `V5_LIVE_ORIGINAL_TODAY_RACES`, 6艇entry数、展示/odds待機状況を確認する。旧collectionタイマー維持、二重HTTP GET/朝再実行/再起動禁止。丸亀の8艇の成績項目は公式未集計かparser誤認か、別に限定診断する。V5の実データ強化型予測への接続は安全なas-of feature gateが整うまで未稼働。物理stage writer切替とBUYは独立復元/経路証明が済むまでNO-GO。
