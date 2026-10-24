# V5専用・VPS外バックアップのフェイルクローズ計画（2026-10-24）

**設計・審査用／未実行／NO-GO**。Google Drive APIへの接続、rclone設定変更、バックアップ転送、ConoHaでの操作、cronの有効化、本番切替、自動購入は本書の作成だけでは承認されない。

## 0. 基準と現状
- バイト数・SHA-256の唯一の基準記録：[`CONOHA_LOCAL_BACKUPS_20261024_CHECKSUMS.md`](CONOHA_LOCAL_BACKUPS_20261024_CHECKSUMS.md)。`railway.dump` 393,138,215 bytes、`boat_history_archive.dump` 81,865,791 bytes。GitHubには秘密のトークン・SQLダンプ・暗号鍵を保存しない。
- 現在はConoHa **同一VPS上の2ファイル**。railwayは`venues`24行の限定隔離復元のみ、archiveは3テーブルを一時DBに隔離復元・削除済み。どちらもスナップショット時点の原本データ全列・件数比較未了。**2つのDBの取得時刻も異なり、整合した1時点の復元セットとは証明されていない**。
- `rclone listremotes` に`drive:`、`gdrive_a_backup:`、`v5_gdrive:`あり。`v5_gdrive`は`type=drive`、明示`root_folder_id`/team_drive/custom_client_idなし。refresh tokenが他の一部remoteと異なるが、**Googleアカウント・V5専用保存領域の独立性は未確認**。2026-10-24 00:09にDrive APIが HTTP 403 `RATE_LIMIT_EXCEEDED`。再接続・再試行・uploadはまだ禁止。
- `boat_data`13件は現行VIEW、本番物理正本切替0/13。`boat_data_stage.venues`は24行を初回コピー済み（再コピー禁止）、`boat_data_stage.entry_snapshots`未作成。legacy collector/timersを停止しない。

## 1. バックアップ対象（V5完成・自動運用の範囲）
| 分類 | 必須内容 | 状態 |
|---|---|---|
| DB 1 | `railway`（旧原本・共有VIEW・既存stageを含む整合dump） | ローカルdump・限定復元済み／外部未保存 |
| DB 2 | `boat_history_archive`（履歴を含む別DB） | ローカルdump・隔離復元済み／外部未保存 |
| V5本体 | 実際にデプロイされたGit commit/依存lockとコード、V5固有スクリプト、runner/collector、systemd unit/timerの**定義と有効化状態** | **未棚卸し／未バックアップ** |
| 起動・復旧要件 | Python/OS/PG版、起動手順、外部依存、機密環境変数の**名前と取得/再設定手順**、鍵管理方法 | **未棚卸し**。GitHubへ認証値を書かない |
| 復元整合の証拠 | 各DBの取得時刻、スナップショット境界、実テーブル照合、復元ログ、双方SHA-256 | **不完全** |

V3/V4の使用しないデータ・保存先は**V5専用の新しい保全先に混ぜない**。ただし運用原本・必要履歴・戻しに必要な既存情報を「古い版」と誤認して除外しない。自動バックアップの対象、周期、世代保持、通知、通信上限は検証後に別途設計・承認する。

## 2. 進行ゲート（1つでも欠落したらSTOP）
**G0 — データ保全**
- 両ローカルdumpをread-onlyで保護し、SHA-256・bytesを出所と照合。元dumpは上書きしない。V5本体／設定の保全対象を棚卸し、必要な項目が揃うまで「V5全体バックアップ完了」と呼ばない。
- 現在の2 dumpは取得時刻が異なる。移行直前の最新差分や各DB間の同一時点整合を別途証明しない限り「本番切替可能」の根拠にはしない。

**G1 — 外部保存先の分離（API状態が正常に戻り、別途確認許可後）**
- 遠隔バックアップの保存先アカウントとルート領域を検証する。V5専用の明示パスを設ける（例：`v5-only/backups/2026-10-24T...Z-<unique-id>/`。**例示であり作成済みではない**）。
- 旧`drive:`・`gdrive_a_backup:`・V3/V4保存先は**参照・上書き・削除対象にしない**。トークンが異なってもアカウント分離と断定しない。専用パスを作れない／API 403再発ならSTOP。
- アクセス権とバックアップの秘密保護を先に審査。DB dumpに個人情報や認証値が入り得るため、専用領域・最小権限・必要ならクライアント側暗号化と鍵の別保管を検討。鍵喪失リスクと復元手順を事前確認。

**G2 — 書込前のno-overwrite保証（転送も別承認）**
- 保存先・オブジェクト名は**新規世代の一意な名前のみ**。同名/不明な存在状態なら上書きやスキップ継続ではなく**STOP**。既存オブジェクトを変更しない挙動を合成/隔離テストで確認する。
- `rclone sync`、`move`、`delete`、`purge`、`--ignore-existing`で欠落を隠す運用は禁止。`--immutable`などの保護だけを無条件に信頼せず、存在検査＋転送後照合の二重ゲート。削除やretention整理も別承認。
- 再試行の急増禁止：API 403時はSTOP、指数バックオフ・レート制限・低並列/低転送量・タイムアウト/ログ抑制を定義してから再開。ConoHa CPU/RAM/WAL/通信費・収集処理を監視し、ピーク時に大容量送信しない。
- 検証前の世代は`PENDING`、二つのDBとV5本体・復元要件の証拠が揃った後だけ`VERIFIED`とする。名前や日付のみで成功扱いしない。

**G3 — ファイル整合（実際の受信バイトで証明）**
- 新規remoteオブジェクトそれぞれの実際の受信バイト数を照合し、**外部から独立した検証環境へ再取得して全バイトSHA-256を計算**、元の2つの基準値と完全一致を確認する。
- DriveのETag・rclone一覧サイズ・メタデータ・アップロード成功応答・転送時チェックサムだけではPASSにしない。復号する場合は**復号後の元dumpのSHA**と比較し、暗号化オブジェクト自体のhashは別に管理。
- 取得が失敗／途中欠落／ハッシュが異なる場合STOP。部分ファイルを本番復元対象にしない。ログには認証情報・dump中身を出さない。

**G4 — VPS外での隔離復元**
- 本番とは別の環境へ受信dumpを復元。DB/PG version、役割/拡張/シーケンス/VIEW依存、全テーブル、必要な件数・内容の一致、V5起動/収集復旧手順を検査する。復元したDBの破棄/後片付け証明を残す。
- 現行`railway`のvenues限定復元、archiveの同VPSでの復元だけではこのゲートはPASSしない。
- フルデータ一致と最新性が確認できない場合、復元可能性は部分PASS、**本番切替NO-GO**を維持。

**G5 — 継続運用と移行承認**
- 新規バックアップの自動実行・世代保持・失敗通知・restore定期試験は、G0〜G4の成功後に個別承認。現行collector/timersと同時実行しない運用枠・費用上限を定義する。
- 全writer/reader認証、増分同期による取りこぼしゼロ、巻き戻し導線、切替前の新鮮な復旧点、購入機能を無効のままにすることを別審査。**バックアップ検査PASSだけで切替やBUY承認を出さない**。

## 3. 証拠・状態の書式（設計）
各世代について`generation_id`、`source_database`、`source_dump_created_at`、`local_file_name`、`bytes`、`sha256`、`remote_account_verified`、`destination_path`、`remote_created_at`、`retrieved_bytes`、`retrieved_sha256`、`restore_test_environment`、`restore_validation`、`status=PENDING|VERIFIED|FAILED`を保存。認証値・URL署名付きトークンは記録しない。

FAIL-CLOSEDの例：リモート不明 / 403 / 同名ファイル存在 / ハッシュ不一致 / 一時復元不成功 / V5本体不在 / 切替個別承認なし → **即STOP、旧バックアップと稼働中の正本維持**。

## 現時点の判定
**DESIGN_DONE、EXTERNAL_BACKUP_NOT_CREATED、EXTERNAL_RESTORE_NOT_TESTED、CUTOVER_0_OF_13_NO_GO、BUY_DISABLED**。

**Next ONE task**：GitHubだけで、V5本体のバックアップ対象インベントリに必要なファイル・systemd・環境定義の証拠採取項目を整理する（ConoHaの実調査・Drive通信は未承認）。その後ConoHaのread-onlyコマンドを1つずつ案内する。
