# V5 現行compact引継 — 2026-10-24 夜間タイマー確認版

本書が現行正本。GitHub repo: `kenshoushouri-cloud/boat-ai-v2`。新チャットは`docs/HANDOFF_LATEST.md`→本書→`docs/NEXT_CHAT_START_HERE.md`のみ。旧handoff・PROJECT_HISTORY・長いworkflowsは大量に参照しない。SHA/タイマー実環境/件数/容量は必要時liveで取得。1作業ずつ、短いTermius貼付コード。ユーザーは深夜に手動不可。

## 目的と優先順位
- V5主力競艇AI。2025-07以降の全期間を対象に精度とROIの真の検証、紙上非購入の実戦予測を最優先。精度を下げる因子は検証後にモデルから除外（収集は継続）。2026年10月末の限定非購入運用が目標、保証ではない。自動購入は最終工程までOFF。ConoHa主＋Railway費用を極力抑える（月$15-20以下が希望、低いほど良い）。Railway Agent/AI使用禁止。
- **旧原本の既存collectorは維持し、原本→V5共通stageへ一方向複製・差分同期、V5は読み取りのみshadowで並行稼働**。二重の外部サイト取得や停止済み旧collector再起動はしない。日中に分割コピー、深夜に整合追込、まずV5読取先だけ切替して非購入backtest。writer本体の切替は別途。
- `boat_data.*`既存VIEWをV5がREAD ONLYで参照できるので、物理stageが完成する前にbacktest・paper forwardを始める。既存inference/scorer/backtestのコードを確認して最小実データパイロットへ進むことが最優先。動くオッズ/展示/気象を旧collectorが事前取得・保存した分はsourceから移行可。ただし元から未取得の時点の動的情報は事後復元できない。後取得の結果/Kは補完可、過去に事前観測した証拠とは区別。

## DBとバックアップの確定状態
- DB `railway` 原本`public.v2_*`13物理表、`boat_data.*`13 VIEW、物理stage`boat_data_stage.venues`24行のみ。他12`boat_data_stage.*`はまだABSENT、**stage1/13・本番物理切替0/13 NO-GO**。旧候補`v5_data.raw_*`へコピーしない。履歴は別DB`boat_history_archive`。固定所在地：`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`、契約`boat_shared_storage_contract.py`。
- 12空stage DDL一括CREATE/ROLLBACK実PGリハーサルPASS、永続作成0。オンラインchunkコピー＋全PK INSERT/UPDATE/DELETE差分の安全gate/自動rollbackは未完成。source等を削除/置換しない。
- 2026-10-24 21:11 ConoHaローカル`railway.dump`(10/23)と履歴dump(10/24) byte数/SHA256/TOC両PASS。同VPSのみ、独立復元未証明。DB `railway`3482MB、archive1069MB、WAL816MB、空き67717MB。外部Google Driveには10/19世代の暗号化main+archive`.age`が現存、復号/実restore未検証。詳細`docs/V5_EXTERNAL_BACKUP_INVENTORY_20261024.md`、`docs/V5_INDEPENDENT_RESTORE_EXECUTION_RUNBOOK_20261024.md`。Drive書込403 RATE_LIMITにつき再試行STOP、既存V3/V4バックアップも上書き・削除禁止。
- 22:07 `tests/test_v5_offsite_encrypted_dump_verify.py` 合成8/8 PASS。ただし暗号化バックアップ現物の復号・独立DB復元は未実施。他の多数のV5 offline合成検査もPASSだが実backtest/実ROIの証拠ではない。

## 5分タイマーと結果補完（**GitHubソースで確認**）
- `deploy/conoha/boat-v5-forward-window.timer`：**07:00〜23:55 JSTのみ5分刻み**（`OnCalendar=*-*-* 07..23:0/5:00 Asia/Tokyo`、Persistent=false）。目的は直前展示/オッズの未取得レースを締切9〜24分前（late-retryで5〜24分）に収集。**03:30には発火せず、変更不要。以前の「03:30も5分刻み」は誤説明、訂正済**。ただし実VPS installed unitの一致はread-only確認していない。
- `deploy/conoha/boat-v5-midnight-catchup.timer`：現在GitHubは**01:20／02:20／03:20 JST**の3回。serviceの最大実行1800秒(30分)、共通flockで同時稼働制御。`boat-v5-daily@night`23:00開始、最大90分=最悪00:30頃まで。早期案**00:45／01:30／02:15 JST**を`deploy/conoha/boat-v5-midnight-catchup.timer.proposed-early-20261024`へ保存済、**ConoHa実環境へは未適用**。
- 03:30〜04:00 JSTは未来の**V5 reader-only shadow切替の候補窓**。01:20等補完/PENDING/子プロセス/PG writer/差分が確定していることを自動gateで確認し、異常ならHOLDして旧VIEW読取継続。**今夜2026-10-25 03:30は未予約・未設置**。OS再起動要求あり、許可なくrebootしない。タイマー前倒しもinstalled unitと実行ログ・未確定状況をread-only確認してから別途適用。

## 2026-10-24 23:00 JST 実機検査・準備
- Termius実機検査スクリーンショットでinstalled forward `07..23:0/5:00`（active）、catchup `01:20/02:20/03:20`（active）、night `23:00`（active）一致を確認。10/24 03:20 catchup `KNOWN_RACES=168`、`PENDING_BEFORE=0`、`SAVED=0`、`PENDING_AFTER=0`、`GATE=COMPLETE`、終了成功。これは当日の正常性のみで将来の完走保証ではない。
- 読取監査 `deploy/conoha/boat_v5_night_timer_audit_readonly_20261024.sh` は実機実行済。GitHubへ安全ガード・自動ロールバック付き時刻変更スクリプト `deploy/conoha/boat_v5_catchup_early_apply_guarded_20261024.sh`（commit `99a03b805118aafbb8ec124fec0e276584342dfa`）を追加。**実VPSへの適用は未実施**、reader 03:30の自動切替も未予約。次はTermiusで同スクリプトを実行しPASS/HOLDを確認（20:00–23:59 JST限定、旧collector/BUY/DB writer非変更）。

## 2026-10-24 夜 12系統COPY最優先（ステージ専用、実機未予約）
- ユーザーが12系統COPYを最優先するよう明示指示。GitHubに `deploy/conoha/v5_stage12_snapshot_only_20261024.py`（commit `2aeefbe6cd9d50266f8cd9f26b3024daa95af39f`）と `deploy/conoha/v5_stage12_schedule_once_20261024.sh`（commit `56db44eaa1300315018b052fc96c9231ee09111f`）を追加。**ConoHa実機への予約・コピーはまだ未実施**。
- user Termius rootで2026-10-24 20:00〜23:59 JSTにinstallerを1回実行すると、翌10/25 02:50 JST一度だけstage-only snapshotを実行。元13 VIEW・元public writer・既存venues24行・BUY・タイマーは変更せず、既設boat_data_stageの残12実表を小さい順に各原子トランザクションで作成・初回スナップショットCOPY・COUNT検証・完了COMMENT。再実行で既存実表を消さない、未知の既存表はHOLD。収集者がアクティブ/容量不足/時間切れ等でHOLD。最大06:10まで、元収集は無停止。**CDC/update/delete最終差分・独立復元・本番route切替は一切未実施、live0/13維持**。COPY結果は翌日実機journalと13種メタ/差分監査で必ず再確認する。
- 実行コマンド（ユーザー向け）：`curl -fsSL https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/56db44eaa1300315018b052fc96c9231ee09111f/deploy/conoha/v5_stage12_schedule_once_20261024.sh | bash`。root接続後に手動1回必要。予約結果は `PASS: V5_STAGE12_COPY_ONLY_SCHEDULED`、後日journal `journalctl -u boat-v5-stage12-copy-20261025.service --no-pager -n 80`。PASSは予約成功であって12表の実コピー完了とは異なる。

- 23:25 Termius試行で旧stage予約installerは `HOLD: System utilities unavailable`（`/usr/bin/runuser`固定パスが不適合の可能性）を返し、**予約は作成されていない**。改修コミット `56db44eaa1300315018b052fc96c9231ee09111f` は `runuser`/`flock` をPATH + sbin/binから探索。ユーザーは今夜の残り23時台に**修正版の予約コマンドを一度実行**し、`PASS: V5_STAGE12_COPY_ONLY_SCHEDULED` と次回02:50を確認する。旧installerを再実行しない。

## 2026-10-24 23:34 JST 実機予約PASS（ユーザー画面）
- Termius root実行で `TOOLS_OK: flock=/usr/bin/flock runuser=/usr/sbin/runuser`、`PASS: V5_STAGE12_COPY_ONLY_SCHEDULED (NOT YET COPIED)`、`NextElapseUSecRealtime=Sun 2026-10-25 02:50:00 JST`、`ActiveState=active` を確認。**翌02:50の実行予約は成功、まだ物理コピー実行・完成は未確認**。今夜追加コマンド不要。
- 翌日 `journalctl -u boat-v5-stage12-copy-20261025.service --no-pager -n 80` と `boat_data_stage` 全13物理表/行数検査が次の一作業。 `STAGE12_INITIAL_COPY_PASS families=12 of_12` が現れない限り完了宣言しない。active legacy collector・時間/容量/その他gate失敗ならHOLDして現行収集継続。後続CDC/全差分・物理本番切替は別工程、BUY OFF。OS `SYSTEM RESTART REQUIRED` バナー表示中だが今夜rebootは実施しない。
- 結果catchupの早期案は先刻実機で `PASS` 適用、次回10/25 00:45 JST確認済。前掲の未適用記述は検査時点の旧履歴であり、現況としない。

## 2026-10-25 08:16 JST 実コピー全12系統PASS（この節が旧未コピー記録に優先）
- User Termius journal 4画面より `STAGE12_PLAN already_done=0 todo=12 venues_protected=24`、02:50:09〜02:53:42 JST、12件の `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12 live_routes_unchanged=YES final_delta=NOT_DONE cutover=NO_GO BUY=OFF`、systemd `Deactivated successfully / Finished` を確認。12系統計13,129,507行（各COPY瞬間）。
- 各表行数: races=73896, results=73896, entry_snapshots=128742, race_condition_snapshots=27569, racer_condition_snapshots=164406, racer_course_stats_snapshots=291518, entries=443376, exhibition_snapshots=487410, weather_snapshots=87065, racer_results=431472, odds_snapshots=2515990, trifecta_odds=8404167。先行venue stage24件も維持（目標13の初回物理stage完了）。各表は個別transaction内でINSERT/COUNT一致。**現在までの更新/削除差分同期・内容ハッシュ双方向照合・独立外部復元・本番reader/writer切替は未実施。** live physical 0/13、原本と既存collector変更なし、BUY OFF。旧文の「stage1/13」「COPY未実施」「予約のみ」は時点の古い情報。
- 次の最小read-only検査用 `deploy/conoha/v5_stage_13_snapshot_proof_readonly_20261025.sql`（commit `a9f171a9abfd5a80e435934a3c295e2d263c5274`）をGitHubへ追加。PGカタログのみで13物理stage＋12完了COMMENT＋13原表＋13 live VIEWを確認。**この検査はまだConoHa未実行**。コピー再実行禁止（既存stage保護）。

## 2026-10-25 08:21 JST catalog実機確認
- 2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。
- 続くPK/列一致の軽量13系統メタ検査をGitHubに追加（上記script）。旧COPYコード再実行不要。旧収集維持。

## 2026-10-25 08:25 JST 差分準備メタ検査PASS
- 2026-10-25 08:25 JSTのユーザーConoHa画面で13/13の`relation_shapes`・`copy_column_shape`・`pk_shape`=PASS、PK `id`/`race_id`/複合`race_id,lane`/`venue_code`、source user_triggers=0、source FK_in/out=0、複数表にserial defaultあり。`ROLLBACK`、`V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES`で正常終了。これはメタデータ一致の証拠であって差分=0/CDCではない。
- GitHubへvenues小規模のINSERT/UPDATE/DELETE guarded delta pilotを追加。実VPSへは未適用。既定PREVIEWではvenue24行のINSERT/UPDATE/DELETE差分件数をread-onlyで算出し、PGのREPEATABLE READでstageのみ整合するAPPLYは別gate。恒久的CDCとは別。

## 2026-10-25 08:34 JST venues差分実測
- 2026-10-25 08:34 JST Termius実機：venues source24/stage24、read-only full outer compare INSERT=0 UPDATE=24 DELETE=0、`VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES`。更新24件は欠損24件ではない。何列が更新されたかは旧previewで未分類。
- 24会場のみ安全に追込する既存コードをPGのUPSERT構文と差分分類改善のため改修（`44b00fd433adb5b2608f87c7e3b423523ba2b607`）。実VPSでのstage書込はまだ行っていない。

## 2026-10-25 08:40 JST venues stage差分反映PASS
- 2026-10-25 08:40 JST: ConoHa Termiusでvenues source/stage各24、`VENUES_STAGE_DELTA_TRANSACTION_PASS upserted=24 deleted=0 bidirectional_equal_in_transaction=YES legacy_source_untouched=YES live_view_untouched=YES continuous_cdc=NO cutover=NO_GO BUY=OFF`、`VENUES_STAGE_ONLY_DELTA_COMMITTED_NOT_CDC_NOT_LIVE`確認。**venues stage差分反映・同一snapshot照合成功**。元public/VIEW unchanged。初回物理stage13/13、live物理切替0/13。
- 残12表向け分割・stage-only差分runnerをGitHub追加（上記commit）。PREVIEW/実APPLYはまだConoHa未実行。古い「venues未反映」記録は履歴扱い。

## 2026-10-25 08:46 JST 12系統差分準備検査実機PASS
- 2026-10-25 08:46 JSTユーザーTermiusで12系統すべて `DELTA_PREVIEW_METADATA_PASS`、`PREVIEW_COMPLETE families=12 current_delta_counts=NOT_MEASURED no_table_scan=YES NO_WRITES NO_CUTOVER`。原本/ステージ列・主キー・初回コピーCOMMENT一致（12/12）。これは構造チェックで、12系統の差分適用やCDC、差分0を示さない。
- 新規12表ガードrunnerを`races`に限り日中小規模実APPLY可へ修正（`cb4b7482695e3ceefb9efebdc104a8b387fe0d6c`）。実DB変更未実施。`json`型列に等価演算子が無い場合のSQL失敗を防ぐため、変更行比較を`to_jsonb`双方向比較へ修正（`cb4b7482695e3ceefb9efebdc104a8b387fe0d6c`）。

## 2026-10-25 08:51 races stage差分成功
- 2026-10-25 08:51:38 JSTユーザーのConoHa画面で `races` stage差分反映が成功。`DELTA_VERIFIED races source_rows=74064 stage_rows=74064 insert_update_delete=[168, 0, 0] bounded_windows=19`、`DELTA_TABLE_COMMITTED races`、`STAGE12_DELTA_SNAPSHOT_PASS families=1`、旧原本/VIEW不変更・BUY OFF・CDC=NOを確認。初回コピー13/13、stage差分反映2/13（venues+races）、本番物理切替0/13。
- GitHubに翌日03:05 JSTの一度限りの残11系統stage delta予約用scriptを追加、VPS未実行・予約未登録。

## 2026-10-25 09:02 JST 11系統差分の予約実機PASS
- 2026-10-25 09:02 JST、ユーザーのConoHa Termius画面で `PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED`、`NEXT=Mon 2026-10-26 03:05:00 JST`、`STAGE_SCOPE=11_NO_RACES`、`LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO` を確認。**予約は成功したが11系統の実差分同期は未実行**。初回snapshot13/13、差分同期済2/13（venues+races）、V5本番物理切替0/13。

## 2026-10-26 06:07 JST 残11系統の差分追込実機PASS
- 2026-10-26 06:07 JSTのTermius画面（03:05:01–03:16:49 JST 実行ログ）で `STAGE12_DELTA_SNAPSHOT_PASS families=11 as_of_per_table_not_CDC=YES` とsystemd `Finished`、11系統各 `DELTA_VERIFIED`→`DELTA_TABLE_COMMITTED` を確認。新規追加は計44,536行（results168, entry_snapshots1938, race_condition323, racer_condition1938, racer_course_stats0, entries1008, exhibition918, weather323, racer_results0, odds_snapshots37920, trifecta_odds0）、更新/削除はいずれも0。初回物理stage13/13、差分反映13/13（venues、races＋11）、本番物理切替0/13。各表の実行時点で整合、連続CDC/最終共通時点の完全同一性を保証しない。旧collector・原本・13 VIEW不変更、BUY OFF。

## 2026-10-26 切替ゲート準備（GitHubのみ）
- `docs/V5_CUTOVER_EVIDENCE_GATE_20261026.md`に残不足（独立復元、全writer/readルート、同時点13表整合、sequence/default、切戻し）を整理。`deploy/conoha/v5_previous_day_core_row_parity_readonly_20261026.sql`で直近日4系統の1スナップショット全列一致をREAD ONLY検査できるよう準備。実機未実行。無人切替未予約。

## 2026-10-26 06:17 JST 前日データ照合とK-file欠損疑い
- 2026-10-26 06:17 JST Termius実機：前日10/25の `races`168/168・`results`168/168・`entries`1008/1008 は全列・キー同一snapshot PASS。不足/余剰/異値0。`racer_results` は原本0/ステージ0で `HOLD_GAP_OR_NO_SOURCE`。**転送漏れとは言えないが、公式K-file詳細6艇の原本収集不足の可能性**。ソース `v5/conoha_midnight_results_pg.py` は通常のレース単位 `v2_results` のみ補完し、6艇詳細 `v2_result_entries` は別 `save_k_day_results_pg.py` がK-fileから保存（明示CONFIRM要）。`v5_data_views_v1.sql`にも10/7以降のK詳細欠損の既知注記。勝手にKデータ補完/外部取得を実行しない。

## 2026-10-26 06:24 JST 公式K詳細欠損日確定
- 2026-10-26 06:24 JST ユーザーTermiusの15日K詳細監査で原本とstageの最新race_idは双方 `20261020_23_12`。10/11–14,10/18–20の7日間は日別全レース6艇分が両方で一致、10/15–17および10/21–25の8日間は両方とも選手別K詳細0行（計1,308既知レース、6艇想定7,848行相当）。`coverage_diff=0`で移設漏れではなく旧原本へのK結果取込未完。10/25のraces/results/entriesの全列照合はPASS、racer_resultsは原本0/先0のためHOLD。既存夜間collectorは3連単の通常確定結果のみ、公式K詳細保存は別job。
- 8日を対象とした一括・読取のみ・最大8公式HTTP取得のguarded K parser previewを追加した。原本/ステージへのK補完未実施。

## 2026-10-26 06:32 JST 公式K8日preview実機結果
- 2026-10-26 06:32 JST ユーザーの公式K-file8日preview結果：8/8 HTTP200、6日(10/15,16,17,22,23,24)はDB既知race_idとKの解析race_idが全一致、全レース6艇、parser失敗0・重複0 → 984レース=5,904艇の書込前品質PASS（**まだDB補完・stage再追込は未実施**）。残2日：10/21 DB156 vs K144（12 race_id不足）、10/25 DB168 vs K167（1不足）。DB原本には近15日中8日で詳細行が存在せず、旧コピー漏れではない。差の13race_idが開催中止/欠測/公式K未掲載なのか未確定。データ登録を強行しない。

## 2026-10-26 V5早期稼働優先への判断（最新）
- K8日分は1,295実施レース、7,770艇行相当を解析可能。K欠番13レースは全てキャンセル確認済み：10/21江戸川全12R、10/25若松12R。**まだDB補完は未実施**。
- 方針をV4補完→V5再コピーから転換。V5のread-only/shadow評価を先行稼働し、今後のK補完/新規writerはV5所有stageへ直接書込する正式ルートを整備。予測scorerは本番実行未証明で、単なるDB VIEW監査を「V5予測稼働」と誤記しない。
- 1日のcollector停止は不可：締切前変動オッズ/展示/気象の当時の取得履歴を再現できないことがある。旧collectorは移行前に止めず、切替は短い管理窓+rollback検証。収集二重化禁止。
- 10/26にGitHub `docs/V5_FAST_START_NO_FULL_DAY_PAUSE_20261026.md` と `deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql` を追加。実ConoHa未実行。新しい外部復元試験はまだない。
- V5初回stage 13/13、10/26 03:16時点の各表差分追込13/13（継続CDCなし）、live物理切替0/13。旧原表/13VIEWそのまま、BUY OFF。

## 2026-10-26 07:12 JST (当日V5 shadow稼働実機PASS)
- V5既存VIEW read-only 5分入力監視は起動成功。Termiusに `PASS: V5_SHADOW_INPUT_READONLY_STARTED_WITH_LIVE_VIEWS`、`V5_SHADOW_READONLY_PASS sampled=5 structurally_ready=0`、次07:15/ActiveState=active。原本今日48Rまで取得、前向き5Rは出走6/6、展示0/6、オッズ0/120で未使用。07:12の締切最短は10:42。
- 既存morning/forward.timer=active、forward 07:05/07:10終了。07:10以降morning収集はDEADLINEログが継続しており、morning完了は未証明。今日の最初のRを取りこぼさないよう先に監視。
- **V5モデルの実データスコア・3連単予測はまだ未稼働。** 入力監視PASSを予測稼働と誤認しない。合成offline strong-coreにはリアルDB 5-factor fit adapterが不足。公式時刻の前向き凍結証明も未確立。BUY OFF/実物理切替0/13、収集停止や再起動なし。

## 2026-10-26 13項目欠損と高評価選手の扱い（最新）
- 本来公式未集計の一部値がNULLでも高評価選手の実力を下げない。13項目全項目必須一律除外を採用しない。一方、`ENTRY_STATS_PARSE_FAILED`や13項目一括NULL・根拠不明NULLは研究投入保留、勝手に0埋め禁止。
- GitHubにpure `v5/entry_quality_policy.py`と合成テスト`tests/test_v5_entry_quality_policy.py`追加。公式未集計の**証拠**を要求して、スコア値はそのまま、信頼度・可否を別にする。全状態BUY OFF。**テストは追加済み・実行は未検証**。本番collector/5分監視/timerは未変更。詳細`docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`。
- 07:34 JSTの朝収集200/288 success108 no_race92 failed0・`ActiveState=activating`が直近証拠。07:32のDB調査は丸亀(15)8艇で一括stats NULL疑い、他会場に平均ST単独NULLあり。公式未集計か解析失敗かはHTML現物未確認。モデル実推論は未稼働。

## 2026-10-26 07:52 JST 朝収集288件完走
- 2026-10-26 07:52 JST、ユーザーのConoHa Termiusで morning.service の朝07:00開始処理が **07:45:54 JST 正常完了**：`progress race/result: 288/288 success=144 no_race=144 failed=0`, `Finished boat-v5-daily@morning.service`, `ActiveState=inactive Result=success ExecMainStatus=0`。`no_race` はHTMLにレース出走表が無い等でスキップした数であり、144中止を意味しない。丸亀（15）の `ENTRY_STATS_PARSE_FAILED` 8艇程度は朝処理全体の成功と別のデータ品質課題として残る。今日のV5 5分読取専用shadowは07:12にActive確認済、07:45以降の稼働状況は未確認。現在もV5実モデル推論/予測保存は未確認、stage writer完全切替0/13、BUY OFF。

## 2026-10-26 07:56 JST first-race shadow/forward evidence
- 2026-10-26 07:56 JST Termius実機：V5 read-only shadow timer=active（次08:00）、07:45/07:50/07:55のログ正常。07:45に元VIEW 138R、07:50と07:55に144R。次の6レースは全てentries=6/racers=6、exhibition=0/odds=0で`WAIT_INPUT`、`structurally_ready=0`。直近締切=08:35（21_01）、次08:47（10_01）。**正常入力監視＝予測モデル稼働ではない**。GitHub`boat-v5-forward-window.timer`は07..23の5分刻み、`v5/conoha_realtime_window_pg.py`は締切9〜24分前のみ処理、毎回最大2Rを公式サイト取得する。08:35の最初の取得候補は予定上08:15頃なので、07:55の展示/oddsゼロだけで障害とは判断できない。収集タイマーがlive稼働した証拠は別途必要。

## 次の1作業
**Next ONE task:** 08:15〜08:25の既存`boat-v5-forward-window.service`ログに `V5_FORWARD_TARGET` / `V5_FORWARD_COLLECTOR_RC` / `V5_FORWARD_WINDOW_CANDIDATES`が出るか、次の5分shadowに08:35締切レースのexhibition/oddsが出るかREAD ONLYで確認する。明確なタイミング内でも0なら既存forward収集経路の安全診断を優先し、08:35の未取得スナップショットを事後取得で捏造しない。旧収集を止めない、二重GET/再起動/物理V5切替/購入はしない。モデル本体は未稼働、stage当日鮮度未同一。
