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

## 次の1作業
**Next ONE task:** 小容量`races`1系統のみ、`deploy/conoha/v5_stage12_delta_reconcile_guarded_20261025.py`（commit `cb4b7482695e3ceefb9efebdc104a8b387fe0d6c`）を`--table races --apply`＋`V5_STAGE12_DELTA_APPROVED=YES`で日中08:00–22:59 JSTにstage-only実行。73,896行前後で100,000行超はHOLD、時間上限120秒、1表1transaction、主キーkeysetでINSERT/UPDATE/DELETE、各range照合＋最終件数。**VPS実行は未実施**、`DELTA_TABLE_COMMITTED races`を実機で確認後に次表へ。12表一括APPLYはまだ行わない。原本・既存VIEW・collector・BUY不変更、本番切替NO-GO。
