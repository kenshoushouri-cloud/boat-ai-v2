# V5 外部バックアップの独立復元試験 — 実施手順（2026-10-24、未実行）

## 目的と現在の事実
- ConoHa VPSの`railway.dump`(2026-10-23)と`boat_history_archive.dump`(2026-10-24)は21:11にbyte数/SHA256/TOCがPASS。ただし**同じVPSのみ**で保管。PG内`railway`3482MB、履歴1069MB、WAL816MB、空き67717MB。
- 既存Google Driveの**暗号化旧世代**`boat-ai-v5-temp-202610`には`main_current_20261019.dump.age`(297756932B)と`archive_current_20261019.dump.age`(52130144B)が存在する。別のDrive接続にも一部複製がある。鍵復旧関連の`.age`ファイル(371B)もメタデータ上存在する。中身・解読鍵・真正性は未確認。
- **同じ10/19というファイル名は一貫した2DBバックアップの証明ではない。** 10/24のデータを覆うバックアップではない。Google Drive書込は403でSTOP中。

## すでにGitHubに追加した実行可能な検証コード
- `v5/offsite_encrypted_dump_verify.py`。**本番ConoHaとは別の隔離された端末**に置いて使う。指定した2つの`.age`ファイルが正しい既知サイズか、age v1ヘッダがあるか、SHA256はいくつかをストリーミング検査（デフォルトはこれだけ）。Drive APIもDBも使用しない。秘密鍵を必要としない。
- `--decrypt-toc --identity <非公開ローカルidentityファイル> --independent-machine-confirmed`の明示指定時だけ、`age`復号→非公開一時フォルダー内で`pg_restore --list`→復号dump削除。エラー詳細・秘密鍵・平文をログ出力しない。**これがPASSでも全文復元・件数一致・当日バックアップは証明しない**。
- `tests/test_v5_offsite_encrypted_dump_verify.py`に8件の合成回帰テスト追加。2026-10-24作成時点では未実行。

## 独立試験を始める前の準備（手動環境はまだ構築していない）
1. VPSと別の既存PC・隔離VMなど**復元試験専用環境**を選ぶ。有料サービスを新規契約しない。PG互換性、ディスク空き、鍵の管理手段と作業者を確認。
2. 既存Driveの10/19 main/archivalファイルを、**元ファイルの変更なし**で独立端末の限定権限フォルダーへ取得する。復元のためだけの受信であり、ConoHaからの再アップロードではない。フォルダーURL等は`docs/V5_EXTERNAL_BACKUP_INVENTORY_20261024.md`に既出。
3. `python3 -B v5/offsite_encrypted_dump_verify.py --folder <暗号化2ファイルの入ったフォルダー>`を実行。元Drive掲載サイズとの一致＋計算した**暗号文SHA256**を別の検証記録に保存。復号鍵の中身はChatGPT・GitHub・スクリーンショットに出さない。
4. `age`・`pg_restore`・ローカルidentityの管理が確認でき、管理者が明示承認した場合だけ`--decrypt-toc`を追加。既存の小さな`boat_v5_key_recovery_20261019.age`自体が`age`秘密鍵ではなく、使い方の事前確認が必要。
5. 復号後のPG dumpを**本番とは別のPostgreSQL**へ隔離して復元し、PG版/拡張/役割/全表と要約件数/主キー/重要レース検査/VIEW/シーケンス整合を照合する。競艇予測の締切前証明とは区別。試験結果には受信暗号文SHA、復号dump SHA、restoreログ要約、独立ホストの識別、照合件数、日時、破棄状況を残す。現行ConoHa VPSまたは`railway`現行DBへ復元しない。
6. **10/19の旧世代PASS≠10/23-24現行保全PASS**。本番V5物理切替/夜間03:30を許可するには、最新世代を別名/専用Drive領域などVPS外へno-overwrite保存し、同様の独立受信・復号・実復元・最新差分整合を試験する必要がある。Google Drive 403の解消と転送設計は別審査。

## 自動化の境界
- 検査コードはVPS上の`systemd`を変更せず、SQL書込・Google Driveアップロード・夜間切替・BUYを行わない。
- 結果のラベル：`FILE_METADATA_PASS`→`AGE_DECRYPT_AND_TOC_PASS`→`ISOLATED_DB_RESTORE_PASS`→`CURRENT_GENERATION_RECOVERY_PASS`は**独立した別段階**。途中のPASSを後段の証拠に昇格させない。
- 現状 **OFFSITE_RESTORE=UNVERIFIED、STAGE12_PERSISTENT_CREATE=NO_GO、LIVE_CUTOVER=NO_GO**。既存収集は続ける。GitHubのスキーマ・分割COPY・全PK差分コードはこの間も実装を継続できる。
