# 新チャット最小起点 — 新競艇AI開発No.2

@GitHub
@Railway

repo `kenshoushouri-cloud/boat-ai-v2`。必ず`docs/HANDOFF_LATEST.md`→指定`docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`→本書だけ先に読む。古い長い引継ぎ・PROJECT_HISTORYを一括参照せず、チャット/タイムアウト対策で1作業ずつ必要最小限のlive取得。

目的：V5主力・2025-07以降の精度/ROI検証・紙上非購入の早期稼働。旧原本collectorを継続し共通stageへ一方向コピー、V5 shadowとread-only backtestを先行。現行13原表`railway.public.v2_*`/13共有VIEW`boat_data.*`、物理stage既存`boat_data_stage.venues`24行のみ、残12未作成、物理本番切替0/13。原本削除禁止。ConoHa同VPSのdump2件sha/TOC PASS、VPS外復元未証明。Drive新規書込403 STOP。Railway安価（$15–20より低く）、Agent/AI禁止、BUY OFF。日中の研究・準備は継続。

**タイマー誤解を訂正：** GitHub`deploy/conoha/boat-v5-forward-window.timer`は`07..23:0/5:00 Asia/Tokyo`、07:00〜23:55のみで03:30は起動しない。結果catchupは01:20/02:20/03:20、service各最大30分、nightは23:00開始/最大90分。前倒し案`00:45/01:30/02:15`は`deploy/conoha/boat-v5-midnight-catchup.timer.proposed-early-20261024`にあるが未設置。V5 reader-only shadow切替候補03:30も**未予約**。直前に実unit・完走/未確定PENDING/flock/子worker/DB状態を確認しFail-closed。

**Next ONE task:** ConoHa上のinstalled forward/catchup/night timerと直近journalを一度read-onlyで比較し、前倒しを実施できるか判断する。コードが必要ならTermiusに貼れる短いコードを1つ示す。その後、結果補完前倒しとV5 read-only実データbacktestの準備。秘密鍵・BUY・Drive書込・実stage作成/物理原本切替を無断で実行しない。
