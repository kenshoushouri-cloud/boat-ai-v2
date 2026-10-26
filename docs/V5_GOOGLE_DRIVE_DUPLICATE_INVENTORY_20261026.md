# V5 / Google Drive 2アカウント 重複・世代整理台帳 (2026-10-26 JST)

**接続済みGoogle Drive APIを直接READ ONLYで列挙したメタデータ。** 旧ファイルの移動・削除は一切未実施。ファイル名とbyte数が一致してもバイト内容・復号可能性・独立復元を確認するまで、重複確定/削除承認とはしない。

## 2026-10-26 の整理実施
- Drive B root（以前V5一時セットが確認できたアカウント）へ`boat-ai-v5-production-backups-20261026`新規作成済み。**これはV5正式専用領域であり、現在のバックアップ実体は未転送。**
- 専用領域の中へ新規2フォルダー作成・読み返して存在確認：
  - `00_pending_integrity_and_restore_verification`: 新たに暗号化転送した世代が受信/復号/独立復元等を未通過の間に置く領域。
  - `10_verified_recovery_generations`: 独立環境へ再取得してハッシュ・復号・DB独立復元をパスした世代だけを格納する領域。
- A/Bの**旧一時V5・V3/V4・復旧鍵・旧main/archive世代の元ファイルは一切移動/削除/上書きしない**。

## Drive全既知rootフォルダーの直接一覧結果
| 区分 | フォルダー | ファイル | provider bytes | 判定 |
|---|---|---|---:|---|
| A | `boat-ai-main-temp-202610` | `main_current_20261019.dump.age` | 297756932 | B同名同サイズ、重複**候補** |
| A | 同上 | `main_current_20261018.dump.age` | 297740778 | 異なる世代、保全 |
| A | `boat-ai-history-archive-temp-202610` | `archive_20261016.dump.age` | 52125309 | 古い履歴世代、保全 |
| A | `boat-ai-v3-temp-202610` | `v3_20261016.dump.age` | 302987522 | 旧V3保全 |
| A | 同上 | `boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066.zip` | 302656753 | 別復元資産、保全 |
| A | `boat-ai-v4-temp-202610` | `v4_full_20261018.dump.age` | 347209759 | 旧V4保全 |
| A | `boat-ai-v5-key-recovery` | `boat_v5_key_recovery_20261019.age` | 371 | B同名同サイズ、重要鍵資料**削除禁止** |
| B | `boat-ai-v5-temp-202610` | `main_current_20261019.dump.age` | 297756932 | A同名同サイズ、重複**候補** |
| B | 同上 | `archive_current_20261019.dump.age` | 52130144 | 同世代名でも復元一貫性未確認 |
| B | `boat-ai-v5-key-recovery` | `boat_v5_key_recovery_20261019.age` | 371 | A同名同サイズ、重要鍵資料**削除禁止** |

Aの`boat-ai-v2-key-recovery`はrootで存在確認済みだが子ファイル内容は今回未列挙。B新専用領域はフォルダー2つのみ、バックアップ本体0件。

### 重複削除ゲート
1. A/B同名同サイズmainの受信バイトを計算したSHA-256で一致確認する（Drive providerのsize一致では不足）。
2. 少なくとも1世代の鍵復旧・独立検証先の読み戻し・実際のDB独立復元・最新世代への切替可否を検証する。
3. 保有世代数とV5復旧に必要な旧V4原本依存を判断した後、旧Drive世代/重複ファイルの削除について**別の明示確認**を得る。復旧鍵/元データの世代やV3/V4 assetsは自動削除禁止。
4. ConoHa側の既存バックアップ9候補合計740088294 bytes（`/root`/var/backups`の既知拡張子に限定）も暗号化オフサイト転送→再取得/復元検証した**実ファイル単位**で削除判断。systemd/collector/V5本体保全用のディレクトリ内に未知拡張子の成果物がある可能性があるため、9件をConoHa上の全バックアップとは断言しない。

## ConoHaの状態と次工程
- 2026-10-26 11:01 JSTのTermiusログでは`BACKUP_FILE_CANDIDATES=9`、`BACKUP_TOTAL_BYTES=740088294`と個別パス9件まで表示。
- 同スクリーンショットは遠隔照合の末尾`PREFLIGHT=...`が表示される前で、シェルプロンプトに戻っていない。**`v5_gdrive:`とBの同一アカウント性/Drive空き容量/403の解消は未確認**。ここで再実行して余分なAPI呼び出しをしない。
- 10/27 03:05 JST`boat-v5-stage11-delta-20261027-recovery.timer`が予約済み。元の停止済みタイマーは起動禁止、収集は従来のまま、BUY OFF、writer cutover NO-GO。

**Next ONE task:** Termiusの進行中`v5_drive_offload_preflight_20261026.py`の終了出力（`PREFLIGHT`または`HOLD`）のみ確認し、remoteのアカウント同一性と空き容量を確定する。転送・削除はそれ以後の独立ゲート。

## 2026-10-26 拡張：.dump以外の保全実体が存在（GitHub基準証拠）
ConoHaの前回インベントリの9件／740088294 bytesは既知のバックアップ拡張子のみ。以下の既知TAR3件は**その9件に含まれていない**（内容は未再確認）。
- `/var/backups/boat-collector-20261024-7Tn5rg/collector.tar`: 2283520 bytes, SHA256 `823a46ee4820e66373abaec7d6e099c3e1d99ae019488691e03d6fbd2a4d7d62`
- `/var/backups/boat-v5-20261024-Dip2iAH2/v5-runtime.tar`: 25200640 bytes, SHA256 `4f1b2c6cd497e0300b34bad2e08aa570b5eeab09b472bf0be846f89d8c954968`
- `/var/backups/boat-v5-systemd-20261024-Qwz5OloV/units.tar`: 20480 bytes, SHA256 `dc2b54596477a6440f51596d76a84285ea3cf203522355cc1eb4393b224936fb`
合計27,504,640 bytes別途。9件と加えると**確認候補だけで767,592,934 bytes**（重複/他拡張子/必須設定の有無は未検証）。TARには重要な機密が含まれる可能性があるため、平文のDrive転送は禁止。

GitHubに`deploy/conoha/v5_backup_integrity_baseline_readonly_20261026.py`（commit `1d4f80a6f76e6cd415624bd274875bf70980bf46`）を追加。基準SHA/サイズが既知の`railway.dump`, `boat_history_archive.dump`, 上記TAR3件の**5件についてローカル読み取り専用照合**する。合計502,508,646 bytes；旧研究用7件を勝手に不要・削除可と判断しない。照合が通っても、最新DB backup/Google Drive転送・リモートSHA・別VPS復元を意味しない。

**今回の重複候補A/Bの暗号化済み同名ファイルについては、依然としてDrive取得バイトのSHAが不明のため削除なし。** 復旧鍵はA/Bいずれも保護する。
