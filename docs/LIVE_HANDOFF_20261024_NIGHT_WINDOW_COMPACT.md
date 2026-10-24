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
- ユーザーが12系統COPYを最優先するよう明示指示。GitHubに `deploy/conoha/v5_stage12_snapshot_only_20261024.py`（commit `a3aa10efe03752137d62cc51e4b8f5503d7b2fe6`）と `deploy/conoha/v5_stage12_schedule_once_20261024.sh`（commit `3fc34d2f5c7303ef2dde7bf55912fb6a31facd0a`）を追加。**ConoHa実機への予約・コピーはまだ未実施**。
- user Termius rootで2026-10-24 20:00〜23:59 JSTにinstallerを1回実行すると、翌10/25 02:50 JST一度だけstage-only snapshotを実行。元13 VIEW・元public writer・既存venues24行・BUY・タイマーは変更せず、既設boat_data_stageの残12実表を小さい順に各原子トランザクションで作成・初回スナップショットCOPY・COUNT検証・完了COMMENT。再実行で既存実表を消さない、未知の既存表はHOLD。収集者がアクティブ/容量不足/時間切れ等でHOLD。最大06:10まで、元収集は無停止。**CDC/update/delete最終差分・独立復元・本番route切替は一切未実施、live0/13維持**。COPY結果は翌日実機journalと13種メタ/差分監査で必ず再確認する。
- 実行コマンド（ユーザー向け）：`curl -fsSL https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/3fc34d2f5c7303ef2dde7bf55912fb6a31facd0a/deploy/conoha/v5_stage12_schedule_once_20261024.sh | bash`。root接続後に手動1回必要。予約結果は `PASS: V5_STAGE12_COPY_ONLY_SCHEDULED`、後日journal `journalctl -u boat-v5-stage12-copy-20261025.service --no-pager -n 80`。PASSは予約成功であって12表の実コピー完了とは異なる。

## 次の1作業
**Termiusで上の一度きりの12系統stage COPY予約scriptを実行してPASS/HOLDを確認する。** 既にcatchup時刻前倒しは実機でPASS。翌日02:50のステージ初回COPY結果をjournalで確認、欠ける系統はHOLDの原因を調査して再実行方針を判断。その後insert/update/deleteの全差分・独立復元・本番writer routeの安全試験を別途実施。BUY/Drive書込/原本切替は禁止。
