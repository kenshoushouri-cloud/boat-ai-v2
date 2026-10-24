# V5現行引継入口（2026-10-24 19:06 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/PROJECT_HISTORY/旧長いworkflowを一括読みしない。SHA/稼働状況/件数はliveで必要な箇所だけ再取得。

最新21:11：ConoHaローカル2 DB dumpのbytes/SHA/TOC両方PASS、railway3482MB・history1069MB・WAL816MB、DB/backup同一FS空き67717MB（約67GB）。移行先12表ABSENT・venues既存stage、live0/13。外部独立復元が未証明。次は新規Drive uploadせずVPS外保全/復元を解決、並行してGitHubでstage copy差分/rollback実装。03:30未予約、BUY OFF。詳しくはcurrent compact末尾。
