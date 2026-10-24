# V5 外部バックアップの実在確認（2026-10-24 21:11以降、read-only）

**外部クラウドのファイル名・大きさ・更新日時を確認しただけであり、実際のファイルSHA256／復号・DB復元成功ではない。** 今回は2つの接続済みGoogle Driveアカウントで名称検索→既存フォルダー直接一覧をREAD ONLY実施。rcloneの`v5_gdrive:` remoteと同じアカウントに結びつく証拠はない。外部コピーの暗号化方式は拡張子`.age`による推測であり、実復号は未実行。

## 既存Google Driveバックアップ（所有アカウント名やsecretは記載しない）

| Google Drive 接続 | 既存フォルダー | ファイル名 | provider-reported size | provider更新日UTC |
|---|---|---|---:|---|
| Drive接続1 | `boat-ai-main-temp-202610` | `main_current_20261019.dump.age` | 297756932 B | 2026-10-19 04:06:47 |
| Drive接続1 | `boat-ai-main-temp-202610` | `main_current_20261018.dump.age` | 297740778 B | 2026-10-18 10:19:13 |
| Drive接続1 | `boat-ai-history-archive-temp-202610` | `archive_20261016.dump.age` | 52125309 B | 2026-10-18 10:09:34 |
| Drive接続2 | `boat-ai-v5-temp-202610` | `main_current_20261019.dump.age` | 297756932 B | 2026-10-19 04:06:47 |
| Drive接続2 | `boat-ai-v5-temp-202610` | `archive_current_20261019.dump.age` | 52130144 B | 2026-10-19 04:26:07 |

- 別アカウント2本の同名同サイズ`main_current_20261019.dump.age`は**バイト内容が同じか未確認**（サイズ一致はhash一致ではない）。Drive接続2のmainとarchiveは日付が同じでも**DBの一貫した同一スナップショットとは確認していない**。
- 参照リンク（現存するクラウドフォルダー、ユーザー専用閲覧）：Drive接続2の`boat-ai-v5-temp-202610` https://drive.google.com/drive/folders/1oO2OAAKGBPYX0VHVKcBOnLSotdcXpjBZ
- Drive接続1: `boat-ai-main-temp-202610` https://drive.google.com/drive/folders/1Tf2vRm9hT5tJ1DWFTkM7813yrFo5cNFa ; `boat-ai-history-archive-temp-202610` https://drive.google.com/drive/folders/1LzTWFaPjtrWSJEsPOnn75tL9AaAOvaVM

## 現行ConoHaローカル保全とは別物
- 10/24 21:11 read-only local SHA+bytes+TOC PASS: `railway.dump` 2026-10-23（393138215 bytes）と`boat_history_archive.dump` 2026-10-24（81865791 bytes）。**ConoHa同一VPS内にあり、こちらはVPS外の証拠ではない**。
- Main PG railway ≈3482MB, archive ≈1069MB, WAL ≈816MB, filesystem free ≈67717MB. 12 physical stage tables missing, venues stage present. No persistent stage or cutover done.
- 外部Driveの直近観測世代は10/19。**現時点10/24の完全・最新復元先として扱えない**。ただしオフサイトの先行世代が既に存在することは確認されたので、保存先を再探索しない。

## 次の安全な工程
1. 既存暗号化V5セットの解読鍵/復旧手順が存在するか、**名前や状態だけ**を独立に確認。秘密鍵や復号パスフレーズはチャットやGitHubへ送らない。
2. 既存10/19のDrive原本を上書きせず、ファイルを受信してSHA・復号・別環境でのrestoreを独立検証するプランを確定する。ただし10/19分の成功で10/24バックアップを代替してはいけない。
3. 現在の10/23-24保全の新規オフサイト転送は、Google Drive 403 RATE_LIMITの解消と専用destination、no-overwrite、別承認後のみ実施。旧V3/V4フォルダー削除禁止。
4. ConoHa公式VPS3.0なら無料一時スナップショット可（1世代・24h失効）が存在するが、契約版未確認。独立DB復元の証明として誤ってPASS扱いしない。新規有料自動バックアップ加入はユーザー料金確認なしにしない。

**判定：既存外部ファイルは存在。ただし当日一貫復元、V5完全システム、独立復元成功の証拠は未完了。** 物理stage作成と本番切替の所定ガードは維持。
