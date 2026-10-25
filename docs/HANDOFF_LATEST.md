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

## 2026-10-26 07:12 JST V5 shadow input実機起動確認
- ユーザーTermiusで`V5_SHADOW_READONLY_PASS sampled=5 structurally_ready=0 LIVE_SOURCE_ONLY=YES NO_MODEL_SCORING=YES NO_BUY=YES NO_DB_WRITES=YES`、`PASS: V5_SHADOW_INPUT_READONLY_STARTED_WITH_LIVE_VIEWS`、新しい`boat-v5-shadow-live-readonly.timer` ACTIVE、次回07:15 JSTを確認。ConoHa既存morning/forward timerもactive、forward 07:05/07:10 finished successfully。
- 07:12までに当日原本races48行。次のモデル候補5レースはentries/選手ID6/6だが、展示6/6及びodds120/120は全て0（未取得時点）、最も早い保存済み締切10:42。07:10台のmorning収集は`daily_v5_safe.sh DEADLINE`を連続出力しており、完了証明はまだない。ユーザー認識の「約8:30初R」の取りこぼしがないか朝収集完了後に調べる。
- 5分read-only input監視の稼働成功と**V5強化型の実データ予測計算の稼働**は別。既存の`offline_mainline_inference.py`は5因子を呼出元から受け取る合成安全HOLDモデルで、実DB feature adapter＋prior-day fit asof証明のrunnerは未確認。従って予測稼働やROI証明を断言しない。
- カーネル更新後の再起動警告が出ているが、今の収集中は再起動禁止。旧collectorの継続、BUY OFF、本番物理切替0/13。

- 2026-10-26 07:18 JST Termius実機: morning.service `ActiveState=activating`, `Result=success`, `ExecMainStatus=0`（**ジョブ未完了**）。07:16:25 `progress race/result: 100/288 success=64 no_race=36 failed=0`。GitHub `repair_month_all_pg.py`による `no_race` は公式出走表HTMLが無い/「データがありません」等でスキップした件数で、**取得成功でも必ずしも確定的な開催中止でもない**。完了ログまでは288件完了と言わない。収集停止・重複再実行は禁止。

## 2026-10-26 07:29 JST 朝の収集継続＋ENTRY_STATS解析警告
- ユーザーTermiusの `boat-v5-daily@morning.service` は `ActiveState=activating`（未完走）。`Result=success ExecMainStatus=0` が表示されたが、これは実行完了の証明ではない。`progress race/result: 100/288 success=64 no_race=36 failed=0` は07:16:25時点の古い最後の進捗行。07:27〜07:29に `ENTRY_STATS_PARSE_FAILED` が複数行発生（20261026_15_01,04,06,07,09,12、複数艇）。
- GitHub `repair_month_all_pg.py` 調査済：`_parse_entry_stat_block` がNoneだと `avg_st,national/local win/place, motor/boat number and rates` など13項目を**NULL fallback**し、船番・登録番号等の出走情報は保存継続。したがって`failed=0`でも特徴量欠損の可能性あり。今日の予測では不足項目を適当な0や過去成績で埋めない。
- 追加したread-only SQL `deploy/conoha/v5_morning_entry_stats_null_audit_readonly_20261026.sql`（commit `f67160d201de90eab7bd19bde6eaa5a55e111509`）で会場別当日のmotor/boat/avgST等NULLを確認可能。**実VPS未実行**。DB操作・コード修正・収集再実行はしていない。
- 明確な次のゲートは現在の朝収集288タスク完走を証明→各場NULL統計の実機確認→丸亀(15)の parser 問題の範囲を限定→不完全入力なら予測HOLD。旧collector, shadow input monitor, BUY OFFを維持、DB物理V5切替NO-GO。

## 2026-10-26 07:32 JST ENTRY_STATS_DB_NULL実機監査
- 9会場（01,04,05,06,08,09,10,11,15）各12R・72艇、合計648艇の `boat_data.entries` READ ONLY as-of監査が完了。選手番号欠損0。全国勝率・当地勝率・モーター番号・ボート番号は丸亀(15)のみ各8行欠損。他8会場の同項目は欠損0。丸亀72艇のうち8艇が`probable_stats_parse_gaps=8`、丸亀平均ST欠損10。全9会場平均ST欠損18（01=3、05=1、10=2、11=2、15=10）、平均ST単独NULLと構造解析不能を区別。
- ユーザーの画面07:29の`ENTRY_STATS_PARSE_FAILED`は丸亀の複数艇。実際の`repair_month_all_pg.py`は`_parse_entry_stat_block`の解析失敗で全13成績値NULL fallback。原因はまだ未特定（L行欠落・13数値窓不整合等候補）。公式ページの現時点のHTML構造を検証するまで本番パーサを修正しない。
- 朝収集はなおactive(07:29時点)。**現在のcollectorを停止/重複再実行/途中でコード差替えしない**。リアルタイム情報を保護。モデルは丸亀で欠損特徴量を適当な0として入力せずHOLD。
- 次の最小作業：`journalctl`で朝収集の完走288/288とfailedを確認。後に丸亀のみパーサdiagnostic read-only（必要なら公式サイト1R最小アクセス）→過去に取得済みの情報を優先した補修方針を設計。Stage物理writer切替と購入はまだNO-GO。

## Next ONE task
朝morning収集が完走したかread-onlyで再確認（`systemctl show boat-v5-daily@morning.service -p ActiveState -p Result -p ExecMainStatus` と `journalctl -u boat-v5-daily@morning.service --since '2026-10-26 07:00' --no-pager | grep -Ei 'progress|Finished|Failed|ENTRY_STATS_PARSE_FAILED' | tail -25`）。解析欠損8艇を除外してV5非購入READ ONLYを継続。収集中のcollectorには触れず、その後丸亀のHTML parser限定調査。
