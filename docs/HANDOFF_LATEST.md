# V5 現行引継入口（2026-10-26・V5早期稼働優先）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットでは本書→compact→`docs/NEXT_CHAT_START_HERE.md`だけ確認。古い引き継ぎや長いworkflowは大量に読まない。実環境の件数・タイマー・SHAは必要時だけ再取得。

## 確認済み
- 10/25初回stage物理コピー13/13。10/26 03:16までに各系統1回の差分追込13/13成功（**継続CDCではない**）。`public.v2_*`が既存原本、`boat_data.*`13 VIEWはその原本を参照、`boat_data_stage.*`13物理表がV5移行先。本番writer/read切替 **0/13**。
- 10/26朝の公式K8日分・1,295実施レース・7,770艇詳細は解析可能。公式KとのDB差13レースは全て中止（10/21江戸川12、10/25若松12）。**K詳細のDB補完は未実施**。
- 同日Google Drive既存3バックアップフォルダー確認、最新の確認済暗号バックアップは10/19。現行世代のVPS外保全と隔離DBでの復元試験は未達。Drive書込403の既知問題は無理に再試行しない。
- 旧collector（リアルタイム・5分系・結果補完）は稼働継続、BUY OFF。Railway月額は可能な限り低く、Agent/AI禁止。

## 2026-10-26 ユーザー方針（最優先）
V4で公式Kや結果補完を続けて毎回V5へ再コピーするのは廃止し、**V5を先に非購入read-only/shadowで稼働、その後データwriterをV5所有stageに移す**。全日収集停止はしない。後取得で復元できない締切前の変動オッズ・展示・気象を優先保護。

計画 `docs/V5_FAST_START_NO_FULL_DAY_PAUSE_20261026.md`。
読み取り専用のstage鮮度検査 `deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql`（commit `2dbd7b7bf390756160a10c9b18c6c0ce88ca1c7c`）はGitHub登録済み、**実ConoHaで未実行**。
K詳細書込前の限定gate `v5/k_detail_backfill_gate_20261026.py`。既存guarded K writerに`--stage-only`（commit `672460c735b830b85ac2f52db88592db57591119`）を追加し旧原本に書かずV5 stageへ直接補完する準備ができた。**現DBでは未テスト/未実行、最新世代の独立復元が未成立なので実書込許可なし**。

## 2026-10-26 07:01 JST V5 race-day fast start
- ユーザーの実機SQL：共通13VIEW（原本参照）+stage13物理表は存在PASS、当日`boat_data.races`8件と`boat_data_stage.races`0件でstageが明確にstale。原本の当日データ収集は進行中。
- レース開始前のV5稼働要求あり。writer本番切替/1日収集停止は厳禁。既存`boat-v5-forward-window.timer`のGitHub既定は07..23の5分刻み、実VPSのactive/journalは未確認。
- 既存live VIEWを読むだけのV5非購入paper入力 watcher `deploy/conoha/v5_shadow_live_input_readonly_20261026.py`（commit `4756ce1d3043ba48efdc17c889431f4bd86ac720`）追加。同作業を一度実行→5分おきのread-only timerを**明示インストールするための**`deploy/conoha/v5_shadow_live_input_schedule_guarded_20261026.sh`（commit `84f6f47bcf49b59ca101aa114c2954bd4b1f1c12`）追加。VPSにはいずれもまだ実行/設置していない。リアルV5モデル予測の稼働は証明されていない。

## Next ONE task
Termiusで既存morning/forwardタイマーのlive active+journalを確認。正常であればread-only shadow watcherをインストールし、`V5_SHADOW_READONLY_PASS`と`V5_SHADOW_INPUT_READONLY_STARTED_WITH_LIVE_VIEWS`を実機確認。これは**V5入力監視開始のみ**で予測エンジン本番稼働ではない。次に実DB入力を既存V5推論パイプラインへ接続する。元collector・原本・VIEW/ステージwriter・BUY不変更。
