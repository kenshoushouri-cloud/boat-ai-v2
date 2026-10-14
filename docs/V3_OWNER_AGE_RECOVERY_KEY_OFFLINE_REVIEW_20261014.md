# V3復元鍵 — age実復号の非通信・非秘密共有手順レビュー（2026-10-14 JST）

**判定: 公開鍵固定値は一致。所有者秘密鍵での実復号は未検証、V3含め4DB実バックアップ/独立復元0/4でHOLD。** 本書はfeature branchのread-onlyソース監査のみ。実`age`実行、SSH鍵操作、依存ツール導入、DB/ConoHa/Drive通信、Secrets取得、CI実行なし。

## 確認範囲

- `ops/backup/keys/v3_recovery_recipient_20261013.pub` の公開鍵1行（末尾改行を除く）のSHA-256を**ローカル計算**し、`test_v3_recovery_age_roundtrip_offline.sh` と `backup_target_binding.py` の既存V3ピン `da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234` に**一致**。公開鍵の内容に対する照合であり、対応する本人秘密鍵の所有・復号成功を証明しない。
- `ops/backup/test_age_ssh_tempkey_roundtrip.sh` は `age`、`ssh-keygen`、`python3`、`cmp` が存在する**信頼済みホストでのみ**使い捨てEd25519鍵を作り、暗号化/復号のbit一致と暗号文改変拒否を試す。 `umask 077`、一時ディレクトリと終了時削除を実装。**本人鍵・実DBを使わない**。欠けたツールではexit69扱い、PASSと扱わない。
- `ops/backup/test_v3_recovery_age_roundtrip_offline.sh` は `RECOVERY_PRIVATE_KEY_FILE` に**秘密鍵本体ではなく信頼端末上のローカルパスだけ**を指定し、固定V3公開鍵→テスト文の暗号化→本人秘密鍵による実復号→比較を行う設計。現状未実行。成功しても本番dumpの全復号/隔離復元の証明にはならない。
- `ops/backup/ISH_AGE_OFFLINE_OWNER_TEST_20261014.md`：本人iPhone iSH標準のAlpine3.14配布元では`age`の導入に失敗。無理な`apk upgrade`/リポジトリ変更/未確認バイナリ追加はしない。GitHubへの鍵掲載、チャットへの秘密鍵/パスフレーズ投稿、VPSへの秘密鍵コピーはしない。

## 安全な順序と未解決ゲート

1. **ConoHa管理画面と既存2GB VPSが実際に復旧したことを本人側で確認**し、OS/SSH/資源をread-only診断。10/14受信したConoHaのコントロールパネル**ログイン通知はログイン実績のみ**であり、VPS復旧・管理/SSHの証明ではない。再購入/再チャージ禁止。
2. 本人の明示承認後、信頼できる環境に**正規手段で**必要なツールが揃った場合のみ、**使い捨て鍵**の`test_age_ssh_tempkey_roundtrip.sh`を実施。成功条件は暗号化、全復号、バイト一致、改変拒否。VPS上でこれだけ実行しても本人復元鍵の実証は未達。
3. **本人秘密鍵の持出し禁止を維持**したまま、所有者の信頼できる端末に`age`を導入できる安全な手段が別途確立できた場合のみ`test_v3_recovery_age_roundtrip_offline.sh`を端末内で検証。現在iSHに`age`がないためこの段階は**BLOCKED**。秘密鍵を外部ホストに移して検査を成立させる代替を勝手に採用しない。
4. archive/V4/V5の受取人公開鍵ピンも未登録。本人鍵の復号検証やDrive A/B OAuth、Railwayの原本同定、独立PG18の空DBと同時点証跡がないうちは**preflight/execute/本番移行HOLD**。1DBずつ事前に本人・料金承認。

## 2026-10-14：安全対策の実装と模擬テスト

- `ops/backup/test_v3_recovery_age_roundtrip_offline.sh`をfeature内で改善。先頭`set +x`、Pythonの**鍵本体非読込メタデータ検査**（絶対/正規パス、鍵/親ディレクトリのsymlink拒否、所有者・mode・単一hardlink・空ファイル・親ディレクトリの書込権限拒否）、鍵パスの環境変数を解除し、age診断出力を一時ファイルへ収め終了時削除。安全な端末以外では動かさない。
- `ops/backup/test_v3_recovery_key_local_guard_offline.py`を追加。**偽物の`age`・ダミー鍵・コピーした公開鍵**だけでローカル隔離LinuxのPython unittest **16/16 PASS**、`bash -n` PASS。共有ディレクトリは意図的に拒否され、専用ディレクトリで再試験。コードの模擬成功は実`age`暗号強度・本人秘密鍵復号・DB復元の証明でない。チェック済みGitHub blob内容を保存後read-only再取得確認。
- iSHの実`age`導入は不可のまま、本人鍵での実ラウンドトリップは**0回**。実ファイル/親ディレクトリの現在権限、OS互換性、実暗号化互換性、TOCTOU耐性は未検証。信用できる本人ローカル端末でのみ、別途承認後に実施。秘密鍵・パスフレーズ・鍵パスをチャット/GitHubへ送らない。
- ConoHa Gmailに10/14 **コントロールパネルへのログイン通知**あり。サポートの復旧返信・VPSのIP/SSH/OS等はまだ未確認。**新規購入・再チャージしない**。

## Next ONE task

ConoHaサポート返信と既存2GB管理画面へのアクセスを優先確認。復旧なら本人の許可・SSH環境確認後に**読取専用VPS診断**。未復旧なら`ops/conoha/v5_host_preflight_readonly.sh`を静的確認し、iPhone Safari/iSHで本人がIP/OSを非秘密で確認する安全な最小手順を整備（実実行/環境変更なし）。本人鍵、DB、通信、cron、課金、BUYは禁止。
