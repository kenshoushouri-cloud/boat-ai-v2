# V5 writer 共通ロック検査 — 入力範囲・対象漏れの静的照合（2026-10-14）

**判定：部分的な宣言チェックのみ。実cron/DB/VPSの安全性およびV5本番配線は未確認（HOLD）。** GitHub feature branchの2ファイルだけを読んだオフライン・read-onlyコード照合。Railway/ConoHa/cron/Secrets/BUYへのアクセス・変更なし。

参照：`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md` と `ops/conoha/v5_writer_lock_static_check.py`。旧監査は11ファイル/28コード根拠を静的照合したもので、稼働一覧の証拠ではない。

## 検査できること・できないこと

- checker入力は**手作成の**`{"schema":1,"jobs":[...]}` JSON。各`jobs[]`の `name / phase / service_user / lock_file / argv` を検査。空配列と重複名は拒否。
- `argv`は限定形式の `…/ops/conoha/v5_serial_resource_guard.sh --execute -- /usr/bin/python3 <repo内の許可名.py>` （先頭`/bin/bash`等のみ任意）。文字列の直接起動形について「ガードを通す宣言か」を点検するだけ。**実ファイル、実ユーザー、実環境変数、実cron定義、実行されたプロセスは調べない。**
- `lock_file`の文字列一致は証明にはならない。ガード本体は`V5_SERIAL_LOCK_FILE`環境変数で実ロックパスを変更可能。宣言JSONに実環境を載せていないため、**同一ロックを実際に使う保証なし**。
- **非空の一部ジョブしか入力しなくてもPASS可能**。`DECLARED_COMMANDS_PASS`は**完全性や稼働許可を意味しない**。入力漏れ・間接実行・別のschedulerは検出対象外。
- 上流スクリプトの`runpy`、`subprocess`、条件付きwriter、背景子プロセス、Python内での接続・SQLは単なるargv検査では保証できない。別の入口から実行したときのロック必須化も別審査。

## 既存静的監査の入口との突合

|区分|入口・ファイル|今回の照合結果|
|---|---|---|
|許可候補（宣言だけ）| `run_daily_data_prepare_pg.py`, `run_odds_window_pg.py`, `run_window_refresh_pg.py`, `run_nightly_results_pg.py`, `save_k_day_results_pg.py`, `collect_exhibition_st_forward_shadow_pg.py` |checkerの許可名6個と一致。ただし**V5の稼働承認なし**、研究writerも含むため自動cron化禁止|
|明示的に非許可| `run_window_pipeline_pg.py`, `run_final_pg.py` → `v25_final_realtime_pipeline_pg.py` |旧PRE/通知/旧final経路を誤ってV5 cron化しないため、**許可名にないのは妥当**|
|間接writer・共通ヘルパ| `repair_month_all_pg.py`, `db_pg.py`、旧finalの`v21_realtime_collector_pg_safe.py`ほか |直接`argv`の許可名ではない。**独立起動・間接DB変更の全探索未実施**。ガードの実効範囲未確認|
|新V5実装候補| `v5/official_first_write_executor.py` |transaction注入型の未配線writer。許可名には**未登録**、将来のV5配線時は個別設計・審査が必要|

## リスクとブロック条件

1. **最優先の検査漏れ：** GitHubのcron / Actions / launch定義から、実際に定義されたwriter入口の**全件一覧を作っていない**。この状態ではcheckerに「PASS」が出ても網羅性は不明。
2. **環境による迂回：** 実`V5_SERIAL_LOCK_FILE`と共通所有者・権限・systemd/cron実行ユーザーを未照合。JSON申告値と異なる可能性を否定できない。
3. **動的経路：** 間接writer・背景処理・別デプロイの入口を未監査。
4. **テストと本番は別：** GitHub上に18件のテスト関数があるが、本照合はコード読取であり新規実行結果を意味しない。既存のoffline PASSは4DB復元やV5 OOS検証の代替ではない。
5. **本番HOLD継続：** main/V4本番/4DB/旧CMS鍵を変更せず、VPS実測・実暗号化外部バックアップ4/4・隔離復元4/4・締切前証拠・67週OOSとForwardが完了するまでcron有効化/BUY不可。

## Next ONE task

ConoHaサポート返信を再確認。復旧なら新規購入せずread-only実機診断。未復旧なら**featureブランチのV5関連cron/Actions起動宣言を読取専用で最小範囲確認**し、この許可候補6件・非許可経路との対応表を作る。**現行Railway cron稼働状況と実環境の判定はしない**。外部接続・ジョブ実行・writer配線・main変更・課金・BUY禁止。
