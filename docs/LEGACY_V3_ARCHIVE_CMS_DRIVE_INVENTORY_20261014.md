# 旧V3・履歴アーカイブ・旧CMS：Google Driveバックアップ並行準備（2026-10-14）

**判定：保存先は準備済み。実DBのバックアップ実行は0/4、隔離復元0/4。旧CMS 1ファイルの存在のみDrive側でread-only確認。** 本ターンはGoogle Drive 2アカウントを接続ツールでメタデータ照合し、GitHub引継ぎを参照した。Railway DB/Volumeには未接続、GitHub artifact本体の取得/転送・課金・Google OAuth新規認証・SSH・復号実行なし。アカウント名、メール、フォルダID、ファイルID、秘密情報はpublic GitHubへ記載しない。

## Drive read-only live結果

|原本と用途|アカウント|専用非共有フォルダ|フォルダ内の確認結果|現行DBの退避/復元|
|---|---|---|---|---|
|旧V3 PostgreSQL（休止/wake注意）|Google A|`boat-ai-v3-temp-202610`|旧CMS系ZIP **1件**（302,656,753 bytes / application/zip / 非共有）|**0/0**|
|履歴 archive PostgreSQL|Google A|`boat-ai-history-archive-temp-202610`|**0件（空）**|**0/0**|
|V4本番 PostgreSQL|Google A|`boat-ai-v4-temp-202610`|**0件（空）**|**0/0**|
|V5主力候補 PostgreSQL（Railwayサービス名は candidate-v4）|Google B|`boat-ai-v5-temp-202610`|**0件（空）**|**0/0**|

フォルダ一覧で共有`false`を確認。ZIP名称は`boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066.zip`、Drive上の更新時刻は2026-10-13 09:57:58 UTC。**GitHub Actions artifact由来の旧CMS資産であり、現行V3 DBバックアップを代替しない。** ファイル存在/サイズだけの確認であり、ダウンロード・全体SHA-256・暗号化検証・復号・独立PG18全復元は**いずれも未確認**。拡張子がZIPでも安全な復元性の証拠にはならない。

## 旧CMSの残りと期限

現行compact handoffによれば、2026-10-01の旧CMS暗号化GitHub artifactは**合計3件、うち1件を本人がDrive Aへ保存済、残り2件未確認**。GitHubのartifact一覧APIは今回の接続経路では400（許可対象外）となり、**残り2件の現在の存在・容量・SHA・失効日はlive再取得できていない**。**2026-12-30失効予定は過去の引継ぎ記録**であり、現在のGitHub retention設定を再検証した数字ではない。移送済の1件も内容復元は未検証。**旧CMS 3件の保全達成を宣言しない**。失効が近づく前に、GitHub本人画面か承認済みのartifact列挙経路から残りの存在と保存方法を確認する。

## 安全な並行順序・不足数

1. **今（非通信/小負荷）**：旧CMS残り2件の正確なartifact名/サイズ/失効時刻をread-only特定し、非共有のDrive A内で分離保存する手順を確定。サイズ・通信/追加料金・本人操作・鍵/検証方式を確認してからコピー。Driveの既存ZIPは改名/移動/削除しない。
2. **旧V3 DBの実バックアップ（0/1）**：V3公開鍵固定済だが本人秘密鍵の実`age`復号検証・Drive rclone OAuth未了。Railway休止DBの**wake/ネットワーク費**を個別に見積もり事前承認。実施後に3点セット`.dump.age/.sha256/.ready`確認、外部再取得SHA、本人鍵全復号と独立PG18復元が必須。
3. **archive DB（0/1）**：専用Drive Aは空、受取人公開鍵pin未登録、外部TCPなし。本人鍵/認証/経路と復元基盤が確立するまで接続不可。旧V3と**同時実行しない**。
4. **V4・V5 DB（各0/1）**：本番/研究原本保護。個別承認を得た後に同じ検証ゲートで順次退避。V4はGoogle A、V5はGoogle B。**現在のDrive接続が成功していても、VPS上rclone OAuthが成立したことを意味しない**。
5. 各DBとも**実バックアップ0/4、独立フル復元0/4**。最初の暗号化ファイル作成が成功してもバックアップ完了扱いにせず、全量restore成功まで原本維持。Railway V4本番・4DB・旧CMS鍵・cronを変更/削除しない。BUY HARD HOLD。

**ConoHa状態**：2GBの購入・支払済、管理画面/SSHは本人による実機到達が未確認、サポート返信未確認。V5開発はGitHubの安全なオフライン作業を並行継続。料金目標Railway $10〜12、$15警戒、$20超回避。転送費、CPU/RAM、Network、復元用容量を確認するまでオンラインpreflight/execute禁止。

## Next ONE task

ConoHa返信/既存VPS管理画面が復旧したか先に確認。未復旧なら**旧CMS GitHub artifact残り2件の所在・サイズ・失効予定をread-onlyで特定する方法をGitHub側の現存コード/手順から最小限に調査**。ユーザーの認証操作なしにコピー・新規課金・Railway接続/DB wake・暗号鍵扱いを行わない。
