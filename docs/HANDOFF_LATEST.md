# V5現行引継入口（2026-10-24 夜間運用確認版）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/長いworkflowは履歴扱い、必要なものだけ参照。最新のSHA/DB/timer時刻等は必要時liveで確認。

**要点：** 5分直前情報収集timerは07:00〜23:55 JST限定、03:30に動かない。結果catchupは01:20/02:20/03:20の3回、前倒し案00:45/01:30/02:15はGitHub提案のみ・ConoHaへ未設置。03:30 shadow-reader切替も未予約。現行収集継続、BUY OFF、stage venues1/13/live0/13。次は実VPSのinstalled timerと収集・catchupログのread-only照合、並行してV5の既存VIEW研究。
