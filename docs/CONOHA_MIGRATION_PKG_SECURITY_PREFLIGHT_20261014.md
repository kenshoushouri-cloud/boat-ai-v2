# ConoHa 2GB → Railway費用削減：OS保守と移行パッケージの導入前チェック（2026-10-14）

**モード：設計と公式資料照合のみ。ConoHaへの接続/コマンド実行、apt操作、再起動、Railway DB接続、転送、購入、認証設定は本作業では未実施。** 既存VPSは本人コンソール画像でUbuntu24.04.3 LTS、2GB/3Core/SSD100GB、rootログイン成功、ルート空き89G・MemAvailable約1.50GiB、JST・NTP同期済と確認。Python3.12.3/Git2.43.0は導入済。 `command -v` では `pg_dump/psql/age/rclone` がPATHから解決しない。PATH未発見はパッケージ未導入の確証ではない。

## 1. 最初のONE task：非通信・非変更のUbuntuパッケージ棚卸し

本人が既存VPSのConoHaブラウザーコンソールで、以下の**コマンド1つだけ**を実行する（秘密情報を表示しない）。

```bash
apt-cache policy postgresql-client-18 age rclone
```

- ローカルに保存済みのAPT索引とcandidate/installedを表示する。**ネットワーク通信・パッケージ更新・インストールをしない**。
- `postgresql-client-18` が`Candidate: (none)`でも異常断定せず、Ubuntu標準のAPTリストにPGDGがまだない可能性を確認する。**この段階ではリポジトリを追加しない**。
- `age`/`rclone`についても存在/版を確認するだけ。出力内にプライベートなrepo URL、host、tokenが混ざる場合はマスクしてから共有する。

## 1a. 2026-10-14 19:29 JST：本人VPSコンソール実測（read-only）

`apt-cache policy postgresql-client-18 age rclone`を本人が実行し、画面で以下を確認。

|パッケージ|Installed|Candidate（ローカルAPT索引）|
|---|---|---|
|`postgresql-client-18`|判定不可|**Unable to locate package**：現在のAPT索引で対象名が見つからない|
|`age`|none|`1.1.1-1ubuntu0.24.04.3`|
|`rclone`|none|`1.60.1+dfsg-3ubuntu0.24.04.6`|

この結果は**APTキャッシュ上の候補**で、導入済み・取得成功・オンラインPGDGの有無を保証しない。Ubuntu標準リポジトリにage/rclone候補がある一方、PG18は公式PGDG追加の要否を確認する必要がある。安易なOS 26.04更新・無断リポジトリ追加はしない。

**次の安全な1操作：** `apt-get -s install age` をrootコンソールで実行し、`Inst`予定/依存パッケージ/Unexpected Upgradeを確認する。`-s`は**simulate（非通信・非変更）**であり、**実インストールは行わない**。結果を評価してから実導入の別承認を求める。rclone・PG18・OS更新/再起動は別工程。

## 2. 導入時の必須条件（実施には別承認）

1. **Ubuntu24.04の保守を先に計画**：ログイン時「99件の更新、うち14件の標準セキュリティ更新」「system restart required」。最新版へのOSリリース更新（26.04）は不要で**禁止**。先に更新影響（SSH/コンソール復旧経路、ディスク空き、データ損失リスク、サービスの有無）、再起動時刻を本人承認。Ubuntu24.04では`unattended-upgrades`と`needrestart`によりサービスが自動再起動され得る。意図しない時間のOS更新/再起動を実行しない。
2. **PG18クライアントのみ先に用意**：既存バックアップ`ops/backup/railway_pg_to_drive_stream.sh`は`pg_dump --version`がmajor 18であることを要求。Ubuntu24.04の標準PG版と混同せず、公式PGDG（`noble-pgdg`）の`postgresql-client-18`を信頼済み署名鍵を検証した経路で導入。**`postgresql-18`（DBサーバー）はこの段階で追加しない**。自動起動・リソース競合・復元ディスク/メモリ要件を確認した後に別承認。複数pg_dumpのPATH/版の優先順位も照合。
3. **age**：使い捨てSSH Ed25519鍵による実際の暗号化→復号→改変拒否を、VPSの**秘密を表示しない環境**で検証。本人のV3復元鍵は携帯から持ち出さない/アップロードしない。archive/V4/V5の受取人公開鍵SHAピンは未設定。ダミーのオフラインテストPASSを本人鍵の実復元PASSと取り違えない。
4. **rclone**：本人のGoogle A/Bアカウントと専用非共有フォルダを一対一で確認。2026年中にrclone共有Google Drive client_idが停止予定のため、公式推奨は**所有者の独自Google OAuth client_id**（本人設定・秘密をGitHub/チャットへ貼らない）。iPhone Safari/iSHの過去localhost callback失敗があるため、VPSのブラウザー無しヘッドレスOAuth方式を別設計・本人承認。無断のOAuth作成/転送はしない。
5. **独立復元が最低ライン**：4DBの**実暗号化バックアップ0/4・隔離PG18全復元0/4**。1DBずつ、Railway source UUID/ホスト/接続先、Drive A/B専用folder、復号可能な本人鍵を一致確認し、費用（休止V3 wake、ネットワーク、Railway稼働）と個別承認後に実行。暗号化dump→Drive→再取得ZIP/age全体SHA→実復号→隔離PG18全復元/同時点整合まで元データを保護。V4本番とRailway4DB、旧CMS鍵・cronを停止/削除禁止。
6. **課金**：最終的にRailwayを月$10〜12以下へ近づけ、$15警戒・$20超回避。削減額は**実際のサービス停止時点**から。ConoHa2GBを増強せず、過去データ移行と2GB RAM・Swapの限界を区別。重い復元/バックテスト・リアルタイム収集は同時実行しない。

## 参照元・未検証事項

- PostgreSQL公式 Ubuntu: https://www.postgresql.org/download/linux/ubuntu/ （PGDG noble対応、`postgresql-client-18`）。
- Ubuntu公式 自動更新: https://ubuntu.com/server/docs/how-to/software/automatic-updates/ （unattended-upgrades、needrestart、再起動の条件）。
- rclone公式 Google Drive: https://rclone.org/drive/ （共有client_id廃止2026、独自client_id、ヘッドレス設定）。
- 本プロジェクト `ops/backup/BACKUP_SAFE_MODES_20261014.md`、`docs/LIVE_HANDOFF_20261013_CONOHA_LOGIN_COMPACT.md` を参照。
- 実VPSのAPTインデックス、利用可能バージョン、`unattended-upgrades`現設定、実backup鍵、接続・費用は**まだ未実測**。`apt-cache policy`後も更新・導入の承認は別途必要。

**Next ONE task：** 本人コンソールで`apt-get -s install age`だけを実行し、依存関係と意図しないアップグレードの有無を確認。実インストール・PGDG追加・更新・再起動は承認までHOLD。
