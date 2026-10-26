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

## 2026-10-26 07:34 JST 朝収集200/288とrookie/未集計仮説
- ユーザー実機ログ: 07:32:02進捗200/288、success108、no_race92、failed0。07:34時点`ActiveState=activating`、朝収集は続行中。
- ユーザー指摘: ルーキー・出走経験が少ない選手の平均ST/当地成績が公式表で「-」の未集計となる可能性。ただし丸亀の警告には登録番号4524など長年の既存選手も含まれる。公式ボートレースの4524は103期A1級で新人ではない。
- 現行`repair_month_all_pg.py`の`_parse_entry_stat_block`はavg STのNoneは許容する一方、全国/当地勝率・連対率・モーター/ボート番号と率のNoneを不許可としており、「-」含有で13値窓全体を失敗し、13特徴を一括NULLにする可能性。**仮説でありHTMLを未確認**。選手番号自体はDB欠損0。未集計は0として代入しない。予測には不足情報はunknown/HOLDとして扱う。
- 現行朝collector稼働中はコード更新・重複取得/再起動をしない。完走後、丸亀の1レース1艇を最小限のread-onlyパーサdiagnosticで診断する。

## 2026-10-26 V5 13項目NULL判定方針（購入は引き続きOFF）
- **13項目全必須を全レース一律条件にしない**。ルーキー・当地未経験・新モーター等の公式未集計値は正規のunknownとして保持、値0で偽装せず、予測対象除外の是非は当該モデルで「欠測フラグあり/なし」など前向き履歴バックテスト後に決める。
- **現行パーサの一括NULL fallback（`ENTRY_STATS_PARSE_FAILED`）は品質障害**であり、該当艇の出走レースはモデルの必須特徴が復旧するまで予想の本番判定・購入をHOLD。該当場の全12Rを機械的に除外せず、race_id+lane単位で判定する。
- **モデル必須特徴が未取得/不正値、締切前snapshotの出所と時刻不明、6艇の識別不一致**は購入HOLD。モデルが任意特徴として正式対応している「公式未集計」に限って紙上予測可。最適化前の代替値・後日取得の混入は禁止。
- 次は朝collector完走後に丸亀失敗艇の公式HTMLを最小限に調べ、「公式未集計」か「HTML解析失敗」かを分離。既存collector起動中の修正・重複GETは禁止。

## 2026-10-26 欠損の扱いのV5実装（BUY OFF）
- ユーザー判断：「13項目全部必須にはせず、高評価選手は正規の一部未集計でも能力スコアを下げない」。決定に従い `v5/entry_quality_policy.py`（commit `20c80b7a53cb289ae142adbfc8eda59333fc50ae`）をGitHub追加。6艇・登録番号・13項目を検証し、元の実力評価値を変えず、公式未集計の証拠/出所不明NULL/明示パーサ失敗/13項目一括欠損を分離。全状態 `buy_eligible=False`。正規の欠損は研究候補、原因不明/解析失敗はHOLD。
- 合成回帰テスト `tests/test_v5_entry_quality_policy.py`（commit `104ecd12943c9cd9a12e5a353099b94d00953138`）をGitHub追加。**テスト実行は未確認**（実行環境からGitHub rawの取得ができず）。本番のparser, daily collector, stage writer, shadow timerは変更していない。V5モデル実データ推論は依然未証明。仕様 `docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`。

## 2026-10-26 07:52 JST 朝収集完了
- 2026-10-26 07:52 JST、ユーザーのConoHa Termiusで morning.service の朝07:00開始処理が **07:45:54 JST 正常完了**：`progress race/result: 288/288 success=144 no_race=144 failed=0`, `Finished boat-v5-daily@morning.service`, `ActiveState=inactive Result=success ExecMainStatus=0`。`no_race` はHTMLにレース出走表が無い等でスキップした数であり、144中止を意味しない。丸亀（15）の `ENTRY_STATS_PARSE_FAILED` 8艇程度は朝処理全体の成功と別のデータ品質課題として残る。今日のV5 5分読取専用shadowは07:12にActive確認済、07:45以降の稼働状況は未確認。現在もV5実モデル推論/予測保存は未確認、stage writer完全切替0/13、BUY OFF。

## 2026-10-26 07:56 JST realtime forward window
- 2026-10-26 07:56 JST Termius実機：V5 read-only shadow timer=active（次08:00）、07:45/07:50/07:55のログ正常。07:45に元VIEW 138R、07:50と07:55に144R。次の6レースは全てentries=6/racers=6、exhibition=0/odds=0で`WAIT_INPUT`、`structurally_ready=0`。直近締切=08:35（21_01）、次08:47（10_01）。**正常入力監視＝予測モデル稼働ではない**。GitHub`boat-v5-forward-window.timer`は07..23の5分刻み、`v5/conoha_realtime_window_pg.py`は締切9〜24分前のみ処理、毎回最大2Rを公式サイト取得する。08:35の最初の取得候補は予定上08:15頃なので、07:55の展示/oddsゼロだけで障害とは判断できない。収集タイマーがlive稼働した証拠は別途必要。

## 2026-10-26 08:37 JST 初R直前のforward収集状況
- Termius画面 08:30:19 `20261026_21_01`（**芦屋**1R、08:35締切）が出走6/選手6/展示6/三連単オッズ120で`INPUT_SHAPE_PASS_NOT_MODEL`。08:35以降は締切超過なのでshadow対象から消えるのは正常。
- `20261026_10_01`（**三国**1R、08:47締切）は08:30/08:35に出走6/選手6/オッズ120だが**展示0**で`WAIT_INPUT`。会場コード21=芦屋、10=三国、11=びわこ。先行アシスタント会場名誤記を訂正。
- 08:15〜08:35の`boat-v5-forward-window.service`で`V5_FORWARD_COLLECTOR_RC=0`と`Finished`を実機確認。これはsubprocess正常終了で**展示6行保存の保証ではない**。既存`v21_realtime_collector_pg_safe.py`は`V5_FORWARD_BEFOREINFO_PENDING`と`DATA_QUALITY_WARNING exhibition_status`や`exh_rows`を別に記録する。今は三国1Rについてその詳細理由を確認するのが最優先。
- GitHub forward runner `v5/conoha_realtime_window_pg.py`の標準windowは締切9〜24分前。08:35実行が08:47締切に対する最後の標準5分トライとなり得る。コード内に手動`--late-retry`(5〜9分前)はあるが、何も見ずに二重GET/改timer/再起動を行わない。08:47を過ぎた情報を締切前スナップショットとして保存しない。V5本予測・BUY・物理writer切替は依然未実施。

## 2026-10-26 08:41 JST 三国1R展示6艇成功／芦屋2R待機
- ユーザーTermiusログ：08:30:30 `20261026_10_01`（三国1R・08:47締切）は`DATA_QUALITY_WARNING exhibition_status=official_absent valid_time_count=0 source=primary_structured_rows_no_times`、08:30:40`before=ok exh_rows=0 odds=120`。`V5_FORWARD_COLLECTOR_RC=0`は保存内容PASSを意味しない。
- 同じ三国1Rが08:35:31に`before=ok exh_rows=6 odds=120 source=official_odds3t`、08:35:32に`saved_exhibition_rows: 6`、`V5_FORWARD_COLLECTOR_RC=0`を確認。**公式の掲載が遅れていただけの可能性が高く、この1Rは展示保存まで成功**。モデルの推論可否・取得時刻の再検証は別途必要。
- 08:40:28 `20261026_21_02`（芦屋2R・09:01締切）は`official_absent valid_time_count=0`、08:40:38 `exh_rows=0 odds=120`、`saved_exhibition_rows: 0`。この時点では公式未掲載であり、次回既存forward収集で回復する可能性がある。欠測を0で埋めず、予測HOLD。
- V5監視は共通LIVE VIEWを読み、stage物理writer切替は未実施。旧collector・forward timerを触らない。BUY OFF。

## 2026-10-26 将来のV4整理・バックアップ・削除の順序（未実施、明示承認必須）
- ユーザーは「V4重複削除→V5バックアップ→V4バックアップ削除」の順を提案。**V4を先に削除する手順は採用しない**。現時点で旧 public.v2_* が現行リアルタイムwriter、boat_data.* VIEWも旧表を参照、boat_data_stage.* は08:00時点まで現行writerではない。V5本番推論/物理writer切替も未完成。
- 安全順序：①全13系統のレースID・主キー・本文・日次/締切前スナップショットの**必要データ全期間**を棚卸し、②切替前に**現行V4原本とV5 stage双方を含む最新世代**の暗号化外部バックアップを取得、③隔離PGへ独立復元＋一致検証、④短い切替窓に最終差分同期→writer/read/timer経路をV5に切替→新規収集/時刻証拠/rollbackを検証、⑤複数日安定稼働とバックアップ自動化確認、⑥V4原本の重複分を**削除対象明細の個別承認後**に削除、⑦不要なV4旧バックアップを新V5バックアップの独立復元/必要世代保有を維持して世代ごと整理。
- 一度でもstageに存在しない履歴・展示/変動オッズ・気象・予測凍結証拠があればその旧原本は「重複」と扱わず保護。少なくとも切戻し可能な旧世代を稼働安定まで残し、新旧バックアップを同時削除しない。Railway/ConoHa容量節約は整合性検証後。
- 旧10/19暗号Drive世代と10/23-24同VPS dumpsは現行10/26バックアップ/独立復元の代用不可。最新世代のDrive保管・独立リストアは未達。**削除も切替も本ターン未実施、BUY OFF、収集継続**。
- 08:40:19 V5 VIEWで三国1R(10_01)出走6・展示6・odds120で入力形状PASS。芦屋2R(21_02)は08:40の展示0・odds未準備、収集継続し欠測を0で埋めない。

## 2026-10-26 09:13 JST V4/V5重複容量監査・実機完了
- Termiusで read-only `deploy/conoha/v5_v4_stage_disk_comparison_readonly_20261026.sql` を実行。`mapped_families=13 both_physical=13 old_source_total_gib=3.035 v5_stage_total_gib=3.580 paired_storage_total_gib=6.615`。単位GiB（インデックス/TOAST込み）。V5が旧原本より0.545GiB多いが、理由は未検証。
- 別枠のpublic旧研究系等TOP10に `v2_v24_motor2_forward_shadow=262.7MiB`, `v2_opponent_pressure_shadow_v2=28.4MiB`, `v4_exhibition_quarantine_20261017=22.1MiB`等。ただし**13ペアと重複した削除候補である証明なし**、消してはいけない。
- `pg_total_relation_size`は割当容量であり、旧3.035GiBをそのまま削除許可とみなさない。`NO_PARITY_PROOF_NO_CUTOVER_NO_DELETE`で正常終了し書込/削除なし。旧表はcollector稼働中、V5 stageは03:16の差分追込後も継続CDCなし。正式writer cutover0/13、BUY OFF。オフサイト新世代バックアップ/隔離復元未実施。
- 安全な優先順：最新stage差分(まずREAD ONLYの当日ID照合)→全13系統の最終差分同期と本文/PK parity→現行V4+V5包含バックアップのオフサイト独立復元証明→短い切替窓で全writer/V5読み書き検証→安定稼働→旧3.035GiB相当原本の削除候補ごと承認→バックアップ世代整理。リアルタイム・展示・オッズは停止せず、データ保持を優先。
- ConoHa固定VPS契約の場合、容量解放だけで直ちに月額が下がるとは限らない。Railway費用には本ConoHa DBの容量削除は直接効かない。空き容量確保と将来のプラン選択が主効果。

## 2026-10-26 09:42 JST V5当日races未同期確定
- ユーザーTermiusでread-only `v5_fast_start_shadow_freshness_readonly_20261026.sql`再実行、13 VIEW/13物理stageすべて存在PASS。ただし`TODAY_RACES | live_original=144 | v5_stage=0 | missing_in_stage=144 | STAGE_STALE_USE_LIVE_VIEWS_FOR_PAPER_UNTIL_SYNC`。朝収集完了後もstageへの自動CDCはない。旧原本LIVE VIEWを読むshadow監視だけは継続できる。
- 現時点でV5への正本切替はNO_GO。stage13表の存在≠144Rの当日鮮度≠13表全期間同値。
- GitHub既存`deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py`の`--table races --apply`は**昼間08:00-22:59 JSTに限りraces一表のみ**stage-only差分同期を許容。元public表・VIEW・collectorには書込なし、PGスキーマ/PK/marker/16GiB空き/件数上限/120秒予算/トランザクション同値検証などがある。主キー全期間を同期し、stageにしかない行は削除し得るため、これはstage物理表を更新する作業である。夜間の残り11表同期を昼間に行わない。実行完了証明はまだ無い。
- 外部現行バックアップ独立復元は未完。stage-onlyコピーはV5正本切替やV4削除の許可ではない、旧原本は継続しBUY OFF。

## 2026-10-26 10:13 JST STAGE races全期間delta成功
- ユーザーTermius実機確認：10:12:35 `DELTA_PREVIEW_METADATA_PASS races pk=race_id columns=16 source_disk_MB=16`→`PREVIEW_COMPLETE families=1 NO_WRITES NO_CUTOVER`。
- 10:12:40 `DELTA_VERIFIED races source_rows=74208 stage_rows=74208 insert_update_delete=[144,0,0] bounded_windows=19`、`DELTA_TABLE_COMMITTED races legacy_untouched=YES live_view_untouched=YES CDC=NO cutover=NO_GO BUY=OFF`、`STAGE12_DELTA_SNAPSHOT_PASS families=1`。空きディスク62.41 GiB。13系統のうち**races一系統だけ当日144件をstageに追加**し、全期間のそのテーブルをread+stage-writeトランザクション内で検査。現行writer/13 VIEW未切替、旧表未削除。
- **事後の別トランザクション確認はまだしていない**。残り11系統の10/26最新entries, 展示, odds, 結果, 天候等は同期されておらず、venuesは前回stage保存。旧collector稼働中は今後も差分発生。V5本番予測未稼働、BUY OFF。
- シェルに途中で折返し/編集されたように見える表示があるが、実行結果は前段preview→後段applyとも成功。次に削除・本番切替を行う根拠にはしない。

## 2026-10-26 10:18 JST races同期の独立事後検証PASS
- ユーザーTermiusで`deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql` read-only実行：13個のVIEWとstage存在PASS。 `TODAY_RACES | live_original=144 | v5_stage=144 | missing_in_stage=0 | STAGE_RACE_IDS_MATCH_NOW`。 `ROLLBACK`、追加書込みなし。**現時点の今日のraces主キーの一致**。全列比較/11系統鮮度・予測稼働/継続CDC/独立復元は未証明。10:12:40 `races`は全期間74208/74208行と当該トランザクション中検証済み。
- 残る11系統だけを翌朝03:05（2026-10-27 JST）に一度syncする、新`deploy/conoha/v5_stage11_delta_schedule_once_20261026.sh` をGitHubに追加・日付ガードを確認（commit `77a02288896df3fc6b8de6c98458a935420588da`）。既存の10/25用一回限り設定の複製を日付更新し、runnerは10:12にraces実績のある`f7f52aea5bb30a034a19837d2b449d07eeb3db9b`にピン留め。新規一時systemd timer名は`boat-v5-stage11-delta-20261027`、previewはPGカタログ限定no write、続く夜間`--remaining --apply`はstageのみ。旧タイマー/旧データの変更なし、CPUQuota50% MemoryMax750M、flock/DBチェックあり。
- **この時点ではGitHubコード作成のみ**、ConoHaへinstall/schedule未実行。予約はユーザーのTermius実行後に初めて有効になる。`BUY OFF`・writer切替NO-GO・独立外部復元は未達。stageだけを夜間に追込んでも翌日のデータは再びlagするため、writer移行設計を別途要する。


## 2026-10-26 10:30 JST stage11タイマー予約の偽HOLDと安全復旧
- ユーザーTermiusスクショ：既存`v5_stage11_delta_schedule_once_20261026.sh`は11表の`DELTA_PREVIEW_METADATA_PASS`、`PREVIEW_COMPLETE families=11 NO_WRITES`通過後、`HOLD: Unexpected next start, timer stopped: Tue 2026-10-27 03:05:00 JST`。**データ同期未実施、予約タイマーはスクリプト自らstop済み**。
- 原因をGitHubソースで確認：予定は27日03:05だが末尾の検証条件が`"2026-10-26 03:05:00"`を要求するコード誤り。予約時刻自体は正しい。`deploy/conoha/v5_stage11_delta_schedule_once_20261026.sh`を修正（commit `b619fc7727e223b32ba2fe41a615a825433b16d5`）。**この修正版を再実行しない**（前回のstage runnerファイルが既設で、systemdタイマーが停止済み）。
- 既設一時timerが残っていれば、予定日時とstage-onlyコマンドを検証して`systemctl start`だけ実施し、GC済みなら別名の安全な一回限りtimerを設定する復旧専用`deploy/conoha/v5_stage11_delta_timer_recover_guarded_20261026.sh`（commit `2f53818294e85b5a0674a248f04dfaaf6f3585cb`）追加。root/10月26日日中限定、runner既存検査、旧4タイマー active検査、stageサービス非稼働、unit仕様検証と実行予定JST検証、不一致ならSTOP/HOLD。既存collector, DB, VIEW, BUYは触れない。
- **復旧コードはGitHubに作成したのみ、Termius未実行**。実機PASSまで27日03:05の同期予約は未確定。夜間sync後も完全cutoverではない。外部バックアップ/独立復元未達。旧V4原本を削除しない。

## 2026-10-26 10:39 JST stage11予約復旧PASS・最新backup事前検査準備
- 2026-10-26 10:39 JST ユーザーTermiusにてstage11一回限り復旧タイマー予約のPASSを実機確認：`PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED`、`UNIT=boat-v5-stage11-delta-20261027-recovery.timer`、`NEXT=Tue 2026-10-27 03:05:00 JST`、`STAGE_SCOPE=11_NO_RACES`、`LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO`。データ差分同期はまだ実行されていない。元の停止済みタイマーの再起動・重複予約は絶対にしない。
- バックアップ準備：既存Driveバックアップは過去の10/19世代のみ確認履歴、ConoHa同VPSの10/23 railwayと10/24 history dumpは最新10/26データの独立保全を証明しない。Google Driveコネクタの2アカウントをREAD ONLYで`boat-ai-v5`/`main_current_202610`/`dump`検索したが、新しい暗号化バックアップファイルを特定できなかった（検索結果ゼロ≠不在の証明）。既存Pythonインベントリに`/var/backups`と既知の2dumpフォルダを追加したread-only `deploy/conoha/v5_backup_restore_path_inventory_readonly_20261026.py`（commit `b43a725e4dcc20fb460fe200aa001645910fc01c`）をGitHub作成、実機未実行。秘密・ダンプ本文・DBに触れない。BUY OFF。

## 2026-10-26 10:44 JST ConoHaバックアップ保存先監査（read-only実機結果）
- ユーザーTermiusで`deploy/conoha/v5_backup_restore_path_inventory_readonly_20261026.py`実施。`V5_BACKUP_PATH_AUDIT_COMPLETE_NO_WRITES_NO_BUY`、各ツール`pg_dump/pg_restore/psql/age/rclone/sha256sum=ON_PATH`、rclone.conf存在のみ確認（内容/秘密未読）。
- `railway_dump_20261023`ディレクトリ=SCANNED_METADATA_ONLY、`plain_pg_dump_files=1 bytes=393138215`。既存10/23 SHA基準とファイルサイズ一致（ハッシュ再検証していない）。
- `history_dump_20261024`は`NOT_ACCESSIBLE_OR_ABSENT`、過去GitHub指定`/var/backups/boat-history-20261024-U6CRLt`が見つからなかった。**履歴dump自体の削除や紛失とは未確定**。別の場所や名前の可能性をread-onlyで調査する必要あり。実ディレクトリ`/var/backups`の直下には該当拡張子ファイル0だが、監査スクリプトは下位を再帰走査しない。
- `/root/boat-v5-backups`直下に古いplain dump×6 合計261703682bytes（最終mtime 2026-10-21T15:20:15Z）、`/root`直下plain dump×1 3380606bytes。`ROOT_FILESYSTEM_FREE_BYTES=67011411968`（約62.41GiB）。既存local dumpを消したり移動・上書きしていない。
- `CURRENT_BACKUP_COVERAGE_NOT_VERIFIED`、`INDEPENDENT_RESTORE_NOT_TESTED`、`NIGHT_CUTOVER_GATE=NO_GO`。これは**2026-10-26最新のV4+V5+履歴を復元できるバックアップではない**。10/27 03:05 stage11復旧timerはすでにActiveでPASS、手を触れない。BUY OFF、旧writer維持。

## 2026-10-26 10:48 JST バックアップのDrive B集約方針・保存先作成済み
- ユーザー指示：「ConoHaに保存したバックアップは全部Google Driveへ移し、ConoHaのバックアップ常駐容量をなくす」。**Google Drive移動前に独立検証し、V4原本や稼働DB自体は移動しない**。ConoHaのV5実DB/収集は継続し、将来のバックアップはPG dump→age暗号化→rclone（ストリーミングで余計なローカルdumpを増やさない）を目標にする。停止・cutover・BUYは別。
- 10:48 Termiusのfindで`/var/backups/boat-history-20261024-U6CRLt/boat_history_archive.dump`が**実際に存在**、81,865,791 bytes。前10:44のPythonに出た`NOT_ACCESSIBLE_OR_ABSENT`は実機の別read-only証拠と矛盾するため、存在の否定には使わない。既知`railway.dump`393,138,215 bytes（10/23）、`/root/boat-v5-backups`6 dump計261,703,682 bytes、`/root`直下1 dump 3,380,606 bytesが候補。多重保存・重要度・サイズを実際の移送前に再調査する。
- Google Drive（既存2接続中 **B**、10/19既存V5フォルダ`boat-ai-v5-temp-202610`を直接metadata確認可能な接続）で**本番専用の新規フォルダ作成成功**：`boat-ai-v5-production-backups-20261026`、folder ID `1WJ8MQUN1P1wFGHOi-lws-PaMeIXXFSID`。既存V3/V4/10/19ファイルは一切未変更。Google DriveのV5用B folderは作成できたが、**ConoHa`v5_gdrive:`の接続がBと一致する証拠はまだ無い**。10/24にAPI 403の実績がある。
- 安全なread-only＋最小API（DriveルートフォルダのIDとquotaのみ）`deploy/conoha/v5_drive_offload_preflight_20261026.py`（commit `474e8ef3ece1254183c75a0a218bc87f59c26e03`）をGitHub追加。root内と既知`/var/backups/boat-*`のバックアップ拡張子のメタデータだけ棚卸しし、`rclone lsjson v5_gdrive:`で**専用folder ID一致**および`rclone about`で空き容量を検証。秘密・DB/dump中身は未読、リモートファイル書込/削除なし（OAuthトークン更新が発生する可能性はある）。
- **ConoHaからのバックアップ転送/削除は未実行、最新DB dumpはまだ作成していない**。age復号鍵/公開recipient・Drive接続同一性・Drive容量とAPI安定・暗号化no-overwrite転送/再取得した復号後SHA/隔離復元が全部未完。切替NO-GO、V4削除禁止、BUY OFF、10/27 03:05のstage11 sync timerは変更なし。

## 2026-10-26 11:01 JST Drive重複監査・V5新フォルダー整理
- 10/26 11:01 JST ConoHa Termius backup preflight has so far listed 9 candidate files total 740088294 bytes. Screenshot did not show final `PREFLIGHT` or `HOLD` and no root shell prompt: rclone remote ID/quota still unverified, do NOT rerun or transfer until final result read. Existing files preserved.
Google Drive connector direct root+folder READ-ONLY metadata audit of both accounts: A has 7 named known backup/recovery files including V3/V4, B has 3 old V5/recovery files. Duplicate CANDIDATES (name+byte-size only): A/B `main_current_20261019.dump.age` 297756932 bytes each, and A/B recovery-related `boat_v5_key_recovery_20261019.age` 371 bytes each. Content hash, decrypt, independent restore unverified; **do not delete keys or any backup**. Different dates and types are distinct restore generations, not safe duplicates.
Drive B new V5-only production root has 2 new subfolders confirmed by connector readback: `00_pending_integrity_and_restore_verification`, `10_verified_recovery_generations`, created 2026-10-26; backup objects not uploaded. Canonical full inventory `docs/V5_GOOGLE_DRIVE_DUPLICATE_INVENTORY_20261026.md`. No old A/B files moved or deleted, no backup uploads, V4 legacy unchanged, BUY OFF, 27 Oct 03:05 stage11 recovery timer untouched.

## 2026-10-26 続行：ConoHa 9dump以外の復旧資産を補完
- 前回ConoHaインベントリ9件／740088294 bytesは指定拡張子の一覧で全バックアップではない。既存GitHub保全記録から`collector.tar`2283520 bytes,`v5-runtime.tar`25200640 bytes,`units.tar`20480 bytesの**3件が別に存在した履歴**を確認。候補合計は最低12件767592934 bytes（現存/最新SHA未照合、追加未発見もあり得る）。V5本体は秘密が含まれる可能性があり平文Drive転送禁止。
- 過去の証拠SHAが残る`railway.dump` / `boat_history_archive.dump` / 上記TAR3件の計5資産（502508646 bytes）をnice低優先度・readonlyでhash/size検証する`deploy/conoha/v5_backup_integrity_baseline_readonly_20261026.py`（commit `1d4f80a6f76e6cd415624bd274875bf70980bf46`）を新規作成。**実機未実行**。これがPASSしても旧世代保護のみで、当日最新バックアップ/Drive転送/独立復元の証明ではない。
- Drive A/Bの同名同サイズdump・復旧鍵の重複**候補**は削除禁止。Drive BのV5正式保存先はpending/verifiedの空フォルダー2個作成済み。遠隔preflightの最後の行`PREFLIGHT/HOLD`未受領につき、ConoHa`v5_gdrive:` ID照合/空き容量不明。新規転送0件、既存削除0件。2026-10-27 03:05 JST stage11 recovery timerはそのまま保持。

## Next ONE task
ConoHa Termiusでcommit固定`v5_backup_integrity_baseline_readonly_20261026.py`を`nice -n 15 python3 -`で一回だけ実行し、5件の`MATCH`と`V5_LOCAL_CHECKSUM_GATE`を確認。異常ならHOLD、削除なし。その後、すでに実行済みのDrive preflightの最終`PREFLIGHT`または`HOLD`結果を確認する（remote APIを不用意に再実行しない）。remote ID/空き・age recipient/復号経路がPASSするまでアップロードもしない。