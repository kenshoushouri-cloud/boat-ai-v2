# V5最新引き継ぎ入口（2026-10-24 22:10 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_2210_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`の3点だけ読む。古いhandoff/長いworkflowは必要になった部分だけ読む。SHA/件数/稼働状態は必要なときだけlive確認。

最優先は**13ソースのV5共通領域複製と既存VIEWによるread-only backtest／購入なしshadow並行運用**。V5用stageはvenues24行のみ（1/13）、live物理切替0/13。既存原本収集を維持・二重収集なし。バックアップはConoHa内dump二つがSHA/TOC PASS、外部現在世代の独立復元は未証明。Drive新規書込403 STOP。BUY OFF。
タイマー：forward 07:00〜23:55（深夜なし）、night23:00、catchup現行01:20/02:20/03:20。**00:45/01:30/02:15への早期化案をGitHubに保存済みだが本番未適用**。将来03:30 shadow reader切替は未予約。次は設置timer/過去job read-only確認→安全な変更・戻しコード準備。同時にV5の既存scorer＋VIEW接続を優先。
