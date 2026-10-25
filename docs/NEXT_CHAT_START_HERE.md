# 新チャット起点（2026-10-26 V5早期稼働）

@GitHub
@Railway

Repository: `kenshoushouri-cloud/boat-ai-v2`。最新優先 `docs/HANDOFF_LATEST.md`、そこが指すcompact、当文書だけ参照。長い履歴は再読しない。

13系統のstage初回物理コピー完了（10/25）、表別差分同期13/13（10/26 03:16まで、継続CDCではない）。元 `public.v2_*`、13現行 `boat_data` VIEW、V5物理 `boat_data_stage` の三つを区別。正式writer cutover 0/13。K詳細8日=1295実施レース（中止13除外）×6艇、まだ補完DB書込なし。

**方針:** V5非購入read-only/shadowを今すぐ優先、以後K結果補完はV5物理stageを正本として直接反映できるwriterへ移す。V4→V5の繰り返しコピーは終了させる。1日収集休止はせず、変動オッズ/展示/気象を守る。短い管理窓にのみwriter切替。旧原本・タイマー停止/削除やBUY禁止。

当日03:16以後のstageは新しいデータを追従していない可能性。最新オフサイト世代の復元試験・全writer監査・切戻しは未合格。`docs/V5_FAST_START_NO_FULL_DAY_PAUSE_20261026.md`参照。

**Next ONE task:** `deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql` をConoHaでREAD ONLY実行。今日の原本とstageの鮮度を確認し、V5のpaper shadow入力/モデルの実運転を進める。運用コスト最小、Railway Agent/AIなし。