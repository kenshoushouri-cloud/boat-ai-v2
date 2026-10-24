# V5現行引継入口（2026-10-24 夜間運用確認版）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/長いworkflowは履歴扱い、必要なものだけ参照。最新のSHA/DB/timer時刻等は必要時liveで確認。

**要点：** 2026-10-24 23:00 JST実機検査で5分直前情報収集07:00〜23:55、catchup 01:20/02:20/03:20、night 23:00を確認。03:20 catchup PENDING_AFTER=0/GATE=COMPLETE。GitHubに早期案00:45/01:30/02:15の安全ガード・ロールバック付き適用script追加済、**ConoHa未適用**。03:30 reader-shadow切替未予約。旧収集継続、BUY OFF、stage1/13/live0/13。catchup前倒しは実機PASS。ユーザーの12系統物理stage COPY優先指示により10/25 02:50 JSTの1回限りstage-only予約スクリプトをGitHub追加（実機未適用）。次はTermiusで予約1回、翌日結果検証。実切替0/13、CDC/独立復元未証明、BUY OFF。
