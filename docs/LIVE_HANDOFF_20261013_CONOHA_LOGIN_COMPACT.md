# 新競艇AI開発 No.2 — Current compact handoff（2026-10-15 JST）

## 最優先・引き継ぎ規則
- Repo: `kenshoushouri-cloud/boat-ai-v2`。**作業ブランチ `feature/v5-prior-day-counter-test-20261011` のみ**。main・現行V4本番保護。入口 `docs/HANDOFF_LATEST.md` →本書全文→ `docs/NEXT_CHAT_START_HERE.md` 以外は原則読まず、古いhandoff、PROJECT_HISTORY、過去チャット、大きなworkflowを大量参照しない。個別根拠だけ必要時に開く。
- **1ターン1作業／短い報告／想定時間を添える／tool call最小**。本人は今夜PCをシャットダウン済み、**iPhone SafariのConoHa Webコンソールを操作中**。画面は `root@vm-...:~#`（Ubuntu）；Windows PowerShellとは別。スマホでは長文貼付・先頭文字抜け・文字化けが起きた。短いコマンド、送信前の文字照合、継続プロンプト `>` ならCtrl+C。チャット容量を節約するため本書は追記せず要点差し替え。
- 数量・容量・commit SHA・最新run等を固定値と思わず、必要な次の作業に関する事実だけlive再取得。**保存したと確認できるまでGitHub更新を完了扱いしない**。パスワード、SSH鍵、復号秘密鍵、OAuth token、DB URL、回復キーは画面/チャット/GitHubに一切貼らない。

## 目的と判断基準
- **強化型V5を主力**に2025-07-01以降の全期間データで、出走/選手能力・級別・調子・コース/競艇場・モーター（交換直後は小標本）・展示/ST・気象・オッズなどを取得/評価。精度/ROIを悪化させる特徴量は採用せず、未採用の原データは将来用に保管。旧V4の判断基準をV5へ無検証転用しない。
- 正確な**締切前**のデータ証拠を凍結→V5予測/shadow→公式結果照合→2025-07以降のOOSバックテスト→Forward実証。後日取得の展示/オッズ、日付だけ一致した履歴を「締切前取得済」と偽らない。欠損/返還不明/NO_BUY/PENDINGを都合良く除外しない。
- 現時点で67週OOS実行**0/67**・実ROI未立証、7/2の180レースでオッズ238券不足/PENDING。収益目標「月+5万円」は未検証。**自動購入はシステム本体の検証完了後、別承認（BUY HARD HOLD）**。LINE仮候補通知不要。
- 最終的に**既存ConoHa VPS 2GB**へV5の公式収集、DB、予想、直列cron、監視、低負荷バックテストを集約し、GitHubをコード管理、外部へ暗号化バックアップ。旧Railway収集エラーの修正よりデータ保護・ConoHa移行優先。ただし移行と復元完了までRailway原本を消さない。

## インフラ現況（本人実機画像で確認）
- ConoHa VPS `boat-ai-v5-main`、Ubuntu24.04.3、2GB RAM/3Core/SSD100GB。直近参考：空きSSD約89GB、MemAvailable約1.5GiB、swap2Gi、NTP/JST同期。Python3.12.3、Git2.43.0。**PostgreSQL client 18.6（pg_dump/pg_restore）導入・版確認済。PGサーバーは未設置**。age1.1.1でダミー暗号化→復号→内容一致/一時鍵削除確認済。**独立実DB復元は未実施**。
- WindowsからVPSへのSSHログイン成功、ConoHa iPhoneブラウザコンソールも入力/コマンド実行可能（`pwd` `echo test/123`で確認）。SSHは許可接続元を制限。**VPSに「再起動必要」表示あり；無計画な再起動・OS更新/26.04へのアップグレード禁止**。
- **rcloneの新旧併用完了（10/15）**：旧Ubuntu APT `/usr/bin/rclone` = **v1.60.1-DEV** を維持し、通常 `rclone` も旧版。公式v1.75.2のKEYS指紋→`SHA256SUMS`のGPG Good signature→ZIPのSHA256一致（2回）→ZIP展開→ステージ動作確認。別名 `/usr/local/bin/rclone-v1.75.2`へ本人承認後配置し、**設置後`version` = v1.75.2**。旧版上書きなし。署名が旧DSA/SHA1の点は把握。約31.6MBのZIPはVPSに取得済。**新rclone `listremotes` 0件、`rclone.conf`未作成**。Google OAuthはまだ。
- 10/15最新写真で`install -d -m 700 /root/.config/rclone`成功、続く`stat -c '%a %U:%G %n' /root/.config/rclone`が**`700 root:root /root/.config/rclone`**と返答。Googleの認証情報を置くディレクトリの権限保護は確認済。トークンを表示する操作は不用意に撮影しない。

## 秘密鍵・外部保管（保全済と未完を区別）
- **Windows11 Pro**（OSディスクはBitLocker無効、TPMなし）：無料age v1.3.2。Sony USB（I:、約8GB）を**BitLocker To Go 100%暗号化、保護ON**にし、本人用age秘密鍵 `boat-ai-age-identity.txt` を保存。個別ACLは本人・SYSTEM・Administratorsのみ。公開鍵を`age-keygen -y`で再取得、一致確認、ダミー暗号化→秘密鍵で復号して同一内容を確認済。
- 秘密鍵の**パスフレーズ暗号化予備** `boat-ai-age-identity-backup.age`（371B）をWindows D:に保存、`age -d -o NUL`で復号動作検査。Google Drive Aの**非共有領域**へ予備コピーをアップロード→本人がダウンロード→D:とのSHA256完全一致を確認。**Google上の秘密鍵は暗号化済み予備のみ**。BitLocker回復キーは紙に控え照合済み。回復キーPDFについてD:の平文ファイルは削除済（他媒体の残存は必要時確認）。**10/15 USBを安全に取り外してPCシャットダウン済**。USB・パスワード・回復キーは別々に保管。USBそのものをConoHaにアップロードしない。
- **Google Drive AへのChatGPT/ブラウザ操作実績 ≠ VPSのrclone OAuth完了**。A/B両方のVPS上の認証はまだ。新規登録時は最小必要権限・非共有フォルダ・token非表示・設定ファイル600を守る。iPhoneのOAuth localhost callbackは過去失敗したため、方法を安全に検討してから操作。Google Drive Bは別アカウント。
- 旧CMSの暗号化ZIP：GitHub側有効4件、Google A非共有V3領域へ約303MB 1件の存在確認、残り3件約907MBは未転送候補。**実ZIPの再取得SHA/復元は0件**。旧CMSとRailway4DBの現行フルバックアップは別案件、取り違えない。

## 保護対象Railway 4DB（外部実バックアップ0/4・独立フル復元0/4）
|対象|原本（サービス名）|予定暗号化コピー先|
|---|---|---|
|旧V3（休止/wake課金注意）|`postgres-hobby-fullhistory-candidate-v3`|Google A・V3専用|
|歴史archive（公開TCPなし）|`postgres-history-archive`|Google A・archive専用|
|**V4 LIVE（公開TCPなし）**|`Postgres-EKp2`|Google A・V4専用|
|**V5研究（名称はv4）**|`postgres-hobby-fullhistory-candidate-v4`|Google B・V5専用|

1DBずつPG18の**全量ダンプをage公開鍵で暗号化**→非共有Drive保管→Driveから再取得SHA256一致→本人所有秘密鍵で全復号→**隔離PostgreSQL18に全復元・同時点照合**→Railway停止/容量削減は別途ユーザー承認。保護前に原本DB・cron・Railwayサービス・鍵を削除/停止しない。必要なアーカイブ/V4/V5の公開鍵ピン/復号鍵対応、原本への安全なアクセス方法は実行前に個別検証。現時点はモック試験PASSであって実DBコピーは**0/4**。

## コード側：済／未完
- featureのConoHaオフラインDAG **20/20 PASS**、直列資源ガード **9/9＋11/11 PASS**。writer/cronは静的監査済（11ファイル/28根拠）、V5凍結entryの模擬検証 **16/16 PASS**、readback模擬 **19/19 PASS**。バックアップ/復元ガードは模擬75件＋中断11件＋ローカル成果物21件PASS、別の鍵ガード16件PASS。**全て実本番DB操作・実Forward・実収益の証明ではない**。
- GitHub Actionsの旧scheduled writer 2経路はDRY_RUN=0・共通flockなし。直近main schedule10件failure、DB URL取得失敗等。実際の稼働と影響範囲未立証。**本番cron/旧収集writerを勝手に再始動・配線しない**。

## タイムスケジュール・費用（見積もり、ゲート優先）
- 当初**2026年10月中旬の運用開始目標は未達**。バックアップ0/4・V5 OOS0/67につき、安全な本運用の日付は確約できない。早期完成を優先するがBUYはHOLD。
- **10/15現在**：VPS到達/PG18 client/age/新rcloneの準備完了。次にDrive A→B OAuth（方法次第、数時間〜数日）。
- **OAuthと接続許可の後 数日〜**：原本4DBを1つずつ暗号化保管、再取得SHA、隔離PG18フル復元を確認。容量/認証/原本アクセスが律速。未確認のままRailway削減は禁止。
- **保管成功後 数日〜数週間**：V5公式収集と締切前freeze/オッズ保存の実接続、shadow、2025-07以降67週OOS、実Forward/ROI評価、資源測定（2GBで予想・バックテスト同時実行しない）。費用/復元/精度を見てRailway段階縮退・必要時のみ別承認で増強。自動購入は最後に別承認。
- **費用**：Railway目標月$10〜12以下、$15警戒、$20回避。ChatGPT+Railwayの理想月5,000円以下、目安上限6,000円、**ConoHa等含め総額評価**。CPU/RAM/Network/WAL/CIの無駄を抑え、Railway Agent/AIは禁止。課金増・DB wake/接続・データ転送・サービス変更は無断実施しない。

## Next ONE task
**10/15 22:40頃、画像で`700 root:root /root/.config/rclone`確認済。** 次の1作業はiPhoneのConoHa rootコンソールで**新版の設定ファイルの所在のみ**を読み取り確認：
`/usr/local/bin/rclone-v1.75.2 config file`
（認証情報の内容は表示しない）。結果を確認してから**Google Drive AのOAuthをiPhoneで安全に通す方式**を1作業ずつ決める。秘密tokenが画面に出る可能性のある操作はスクショ/共有前に必ず注意。**現時点でA/B remote 0件、OAuth未実施、4DB実バックアップ/復元0/4。** 既存rclone変更・VPS再起動・OS更新・Railway原本接続はしない。

## 個別資料（必要時だけ）
`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`, `docs/V5_PREDEADLINE_FREEZE_ENTRY_STATIC_AUDIT_20261014.md`, `docs/V5_CONOHA_2GB_RAILWAY_MOVE_PREFLIGHT_20261013.md`, `ops/backup/BACKUP_SAFE_MODES_20261014.md`, `ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`, `docs/LEGACY_CMS_ARTIFACT_TRANSFER_PREFLIGHT_20261014.md`.
