# iPhone iSH: age 導入不可（環境調査結果 2026-10-14）

## 本人実機の確認
- 本人スクリーンショット：iSH `apk update && apk add age && age --version` は、iSH提供の `http://apk.ish.app/v3.14-2023-05-19/{main,community}` の x86 index 更新には成功したが、`age (no such package)` で失敗。**age未導入・実暗号化/復号0回**。
- 本文の旧「標準`apk add age`でインストールできる」という提案は、この本人環境では誤り。新しいAlpineのcommunityに存在してもiSH固定3.14にあるとは限らない。
- `apk update`とインストール失敗はDBやGitHubデータを触らない。**既存SSH鍵/パスフレーズを変更しない、`apk upgrade`や`/etc/apk/repositories`編集、他バージョンの`.apk`の強制インストール、不明なバイナリ入手は行わない**。iSHはRailway/復元鍵の重要資産を保持している。

## 今後の安全な実行順
1. **ConoHaサポートから既存VPSの管理画面問題が解決したことを確認**。2GBの支払い/申込完了メールは2026-10-13に受信済。2026-10-14のGmail確認時は回答未着。追加購入/再チャージ禁止。まず既存VPSのOS/IP/SSH状態を把握する。
2. ConoHa本人管理の信頼できる環境（Ubuntu推奨、OSは実機で確認）で、正規OSパッケージから`age`と`openssh-client`を準備し、**使い捨てテスト鍵のみ**で`ops/backup/test_age_ssh_tempkey_roundtrip.sh`により暗号化→復号→改変拒否を検証。導入/費用/環境変更はその時点で本人承認。
3. 実age往復ができた後で、**本人が保管する復元秘密鍵をチャット・GitHub・第三者サーバへ移さない方法を別途確定**。`ops/backup/test_v3_recovery_age_roundtrip_offline.sh`は本人鍵が安全に利用できる端末上でのみ実行する。テスト成功でも本番DB復元成功ではない。
4. 4DBの暗号化バックアップと独立PG18フル復元は全て未実施。本人別承認・複数コピー・SHA一致・独立復元なしにRailway原本を停止/削除しない。BUY HARD HOLD。

## 参考
- iSHが独自の固定APKリポジトリを使う例：https://github.com/ish-app/ish/issues/2570
- Alpine 3.14は旧系列：https://www.alpinelinux.org/releases/
