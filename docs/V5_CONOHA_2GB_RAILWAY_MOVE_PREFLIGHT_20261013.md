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
