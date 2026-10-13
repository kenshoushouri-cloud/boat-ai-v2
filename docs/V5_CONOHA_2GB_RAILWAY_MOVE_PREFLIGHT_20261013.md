# V5 ConoHa 2GB 移行・事前設計（2026-10-13）

**段階**: 設計のみ。契約・購入・デプロイ・DB変更・データ移動・Railway停止は未実行。
**基本線**: ConoHa VPS 2GB/SSD100GB（1か月払い、決済はユーザーが申込画面で確認）。自宅PC常時稼働なし。まずRailwayの容量・料金・稼働不安を解消し、その後にB2/R2等の定常的な外部保存を整える。ただし**初回データ移行前の安全コピーと復元検証は省略しない**。

## 既知の実測と限界

Railway boat-v2-postgres / production の直近24h計測（以前の会話時点、毎回liveを再取得）：
- postgres-hobby-fullhistory-candidate-v4: Disk 約4.898GB、RAM 最大約0.879GB
- Postgres-EKp2: Disk 約3.806GB
- postgres-history-archive: Disk 約2.340GB
- postgres-hobby-fullhistory-candidate-v3: Disk 約4.553GB (sleeping)
- 物理ディスク使用合計約15.6GB。**pg_dumpサイズ・圧縮率・移行後DBサイズ・VPS RAMピークの予測値ではない**。
- V5実収益検証0/67窓、BUY/ForwardはHOLD。主力V5、V4本番保護を優先。すべてのDBを常時稼働する必要があるかは未判断。

## OS 選択（2026-10-13）

**ConoHa VPS 3.0: OSテンプレート `Ubuntu 24.04 LTS (64bit)` のServer版**を推奨。24.04は標準サポート2029年まで、ConoHa公式テンプレートあり。Ubuntu 26.04も提供されるが、既存V5 Python/PostgreSQL/Docker依存関係の安定性を優先し24.04から開始。アプリケーションテンプレート(DockerやWordPress等)ではなく素のOSイメージを選び、DB版数確認後に必要な環境だけ導入。2GBではGUI不要、SSH公開鍵・最低限ポートだけ許可、DBポート5432公開禁止、swapは必要性を測って設定。秘密鍵/パスワード共有禁止。OS選択と本番切替・課金契約は別判断。

### 取得経路の確認（2026-10-13・設計確定、未実行）
- Railway live設定: **V4本番 `Postgres-EKp2` はprivate endpointあり・公開TCP proxyなし**。**V5研究 `postgres-hobby-fullhistory-candidate-v4` は公開TCP proxyあり**。両者ともPostgreSQL 18系イメージ。V4のポートを新たに公開して取得することは禁止。
- 候補: Railway内の**一時的な単発転送ジョブ**からprivate networkでV4/V5へ接続し、PG18系`pg_dump -Fc`をストリーム圧縮・暗号化してGoogle Driveへ転送。Railway DB volumeへ巨大ファイルを出力しない。Google OAuth/権限は秘密情報として安全に設定し、実行後撤去。iPhoneのみでの初回Drive認証経路、ワーカーRAM/一時領域、転送料金は未確認。
- Google A: V4本番、Google B: V5研究用を第一案とし、各容量と暗号化バックアップ実サイズで確定する。**独立コピーの確認と復元検証まではRailwayを縮退・削除しない**。
- 現時点で実施したのはDB接続経路の**read-only確認と本書更新のみ**。サービス作成・OAuth連携・dump・転送・DB/cron変更・購入はまだしない。作成・転送・費用発生はユーザー明示承認後。

## ConoHa復旧待ちの一時バックアップ方針（2026-10-13確定）

- **V4本番 `Postgres-EKp2` とV5研究用 `postgres-hobby-fullhistory-candidate-v4` の両方を保全**。名称candidate-v4はV4本番を指さない。履歴アーカイブと旧V3も削除せず、依存関係・固有データを確認して保存範囲を確定する。
- ユーザー保有の**未使用Googleアカウント2個**を一時保管候補とする。利用中の別アカウントは使わない。各アカウントの15GBはDrive/Gmail/Photos共用であり、空き容量と圧縮後サイズは未検証。容量を合算した単一ドライブとは扱わない。原則V4・V5を各独立保存、余裕があれば予備コピー。
- **本格的な定常バックアップは移行後に設計・構築**するが、Railway縮退/削除の前にVPS外の保存コピーと**独立環境での完全復元検証**が必須。一時Google保存も復元検証まで削除しない。
- Postgresの互換クライアントで一貫性ある`pg_dump -Fc`等の論理バックアップを計画し、**Railway DBボリューム内にはダンプを書かない**（V5は容量逼迫）。取得先は安全な外部実行環境を別途確定し、暗号化、SHA-256、スキーマ/件数照合、復元試験を行う。公開TCPプロキシを使う場合は転送量・料金・秘密情報漏えい防止に注意。**まだ転送・dumpは未実施**。
- Railway連携機能からは**既存Backupsの有無・保持状況を直接閲覧不可**。Railway画面の各DBサービス > Backupsでユーザーが別途確認し、結果を記録する。バックアップの存在を推測しない。
- **ConoHa障害中はV4本番/必要cronを停止せず**、一時バックアップの取得・整合性確認を先行。不要な旧V3・試験サービスの停止は依存・課金効果をread-only確認した後に個別承認。データ削除・停止・新規課金・本番切替・BUY禁止。

## 安全な移行ゲート（順守順）

1. **契約はユーザー自身**: ConoHa VPS 2GB/SSD100GB、1か月・請求額・残高自動通知・更新条件を申込画面で確認。申込完了まで移行操作不可。契約資格情報をGitHub/チャットに貼らない。
2. **VPSのみ初期設定**: 対応OS/SSH公開鍵認証・ファイアウォール・セキュリティ更新・時間同期・監視。DBをインターネットへ直接公開しない。CPU/RAM/ディスクの低負荷ベースラインを記録。
3. **Railway read-only台帳**: PostgreSQLメジャーバージョン・使用拡張/所有権・各DBのlive容量/テーブルと行数（重い全表scanは避ける）・接続先サービスとcron依存関係・保存に必要なソースを最小量で確認。V4本番とV5候補を取り違えない。
4. **最小データから試験復元**: DBをRailway側で削除/上書きせず、互換するpg_dump/pg_restoreクライアントによる**論理バックアップ**を作成。2GB VPSでは複数のDB・復元ジョブを同時に動かさない。まず小さな検証DB→V5候補DBの順。復元前後の件数/スキーマ/制約/重要レース・オッズ・特徴量を比較。RAM/ディスク/WAL余裕を確認。
5. **V5のVPS上での実行試験**: data-prepare、展示・公式K履歴、予想、研究バックテストを個別に計測し、同時負荷も検証。OOM、swap多用、締切遅延の場合は4GB増強を検討。未確認で2GB正式採用としない。
6. **独立した外部バックアップ**: Railwayを停止/削除する**前**にVPS外のB2/R2等へ暗号化バックアップを保存し、完全復元を実地確認。原本相当の歴史データ(2025-07以降)とモデル/再現記録はROI実施後も長期保存し、日次運用バックアップとは別の保持期間を設定。圧縮サイズと世代数で請求予測。
7. **安全な切替**: 本番V4/購入は別承認。定期cronと通知の重複実行を防ぎ、RailwayとVPSの予測一致・接続/障害復旧・復元成功後、ユーザーの明示承認を経て不要なRailwayサービスを段階縮退。元データ削除はさらに別承認。

## 移行の「簡単さ」の位置づけ

- PostgreSQLの**データ複製**は標準機能で可能。Railway公式 https://docs.railway.com/guides/postgres-backups-restores / PostgreSQL公式 https://www.postgresql.org/docs/current/app-pgdump.html
- **本体システム全機能の移管は自動ではない**。Railway cron・環境変数・ボリューム設定・秘密情報・通知・バックアップ・ログ監視・認証・ポート・OS管理をVPS用に再構築する必要がある。
- Railway public TCP proxyで大量データを転送すればネットワーク転送料金の可能性。https://docs.railway.com/databases/postgresql
- 実費が安くなるかは、ConoHa本体+独立バックアップ+移行中の二重稼働+保守の総額で判断。

**Next ONE task (契約前後共通)**: 各Railway DBのPostgreSQLメジャーバージョン・必須拡張・実DB容量・V5が依存するDB名を、既存の安全なread-only経路で最小限確認し、2GB試験移行に必要な対象を1つに絞る。重いdump/復元/本番切替は行わない。
