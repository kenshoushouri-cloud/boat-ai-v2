# iPhone iSH: 本人端末内だけで行う age 復元鍵テスト（2026-10-14）

**目的**: ConoHa管理画面の復旧を待たず、iSH内で復元用 Ed25519 公開鍵→暗号化→**本人の秘密鍵で復号**できることを実証。Railway/Drive DBには一切接続しない。**2026-10-14時点では所有鍵での実テスト未完了。**

## 現状と根拠
- ConoHaの支払い確認/2GBサービス申込完了のメールは受信済。2026-10-14時点でGmailにサポート返信は見つからない。Safariの管理画面ループは未解決、VPS IP/SSH/OSは未検証。**再購入・再チャージ禁止**。
- iSHはAlpine Linux x86（バージョンは端末で再確認）、過去にiSHでOpenSSHを使ったパスフレーズ付きEd25519鍵の作成/ローカル解除が成功。端末の秘密鍵とパスフレーズは**絶対にGitHub/チャット/外部サービスへ送らない**。
- 公式Alpineの **community** に `age` x86パッケージあり（例：v3.18/v3.21/v3.22）。`age`自身の公式仕様では SSH Ed25519公開鍵を受信先とし、対応するSSH秘密鍵を `age -d -i` に指定できる。**ただしiSH実行可能かは未検証**。
- ソース: https://pkgs.alpinelinux.org/package/v3.22/community/x86/age および https://github.com/FiloSottile/age

## 次の本人操作（一手順ずつ、実行は本人端末のみ）
iSHを開き、最初に **ageのインストールとバージョン確認だけ**（Railway/ConoHa費用なし）:

```sh
apk update && apk add age && age --version
```

- これが失敗したときは、`/etc/alpine-release` のバージョンと `apk`エラー内容（**秘密情報を含まない部分のみ**）を確認する。闇雲にedge/不明な外部リポジトリを追加しない。バージョン更新やOS全体の更新はこの手順では行わない。
- 成功してもまだ秘密鍵ファイルのパスの公開/貼付を求めない。鍵をテストする手順は端末で別途確認する。手元の `ops/backup/test_v3_recovery_age_roundtrip_offline.sh` は本人鍵のパスが必要だが、その値は端末内の環境変数のみで指定する。公開鍵の固定SHAも検証される。**ChatGPTは鍵の中身を要求しない**。
- 初回は鍵と暗号化小サンプルだけでテストし、`RECOVERY_ROUNDTRIP_OK=YES` のみ共有すれば十分。これは**実DB復元のPASSを意味しない**。
- 成功後に初めて4DBの退避手順・別保管・隔離PG18完全復元の実行承認を検討する。**BUY HARD HOLD**。
