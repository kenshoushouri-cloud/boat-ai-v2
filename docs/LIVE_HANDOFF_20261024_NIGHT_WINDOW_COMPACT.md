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

## 次の1作業
**ConoHaのinstalled forward + catchup + nightタイマーと直近ログを短いread-onlyコードで1回だけ照合し、前倒し補完が本当に安全か確認する。** 既にGitHubの設定は判明しており同じ資料探索を繰り返さない。その後、00:45/01:30/02:15への変更を必要なら承認範囲で適用。V5研究は既存VIEWをread-onlyで先行、stage物理コピー・reader切替実行は未準備なので誤って本番実行しない。BUY/Drive書込/本番原本writer切替は引き続き禁止。
