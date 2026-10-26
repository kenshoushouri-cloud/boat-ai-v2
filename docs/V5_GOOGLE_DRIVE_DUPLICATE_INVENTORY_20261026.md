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
