# entry_snapshots 独立stageの設計・オフライン検査計画（2026-10-23）

**DESIGN ONLY / NO-GO / NOT EXECUTED**。本書は後日の審査用。ConoHa実行コマンド、承認済みDDL、実COPY、差分同期、深夜予約、BUYではない。

## 既に観測した事実（23:10までのTermius画面）
- `railway.public.v2_realtime_entry_snapshots`: relkind=`r`、owner postgres、21列、PK=`id`、別UNIQUE btree=`(race_id,snapshot_label,lane)`。この3列はすべてNOT NULL。ユーザートリガー0、流入/流出FK0。
- `id`はidentityではなく、唯一の列DEFAULT=`nextval('v2_realtime_entry_snapshots_id_seq'::regclass)`。owned sequence=`public.v2_realtime_entry_snapshots_id_seq`。
- `boat_data.entry_snapshots`は既存非更新VIEW（relkind=`v`）。`boat_data_stage.entry_snapshots`は未作成（absent）。先行する`boat_data_stage.venues`は24行コピー済み、再CREATE/再COPY禁止。
- 旧entry原本は33MB（索引・TOAST込み）、統計上の`reltuples`推定124,631行（21:52時点）。真の行数・最新変化数ではない。
- `v5_data.raw_entry_snapshots`を含む新物理ルート候補6名は21:46時点で全absent。ここにテーブルを作ると`v5_legacy_ddl_guard.py`の存在チェックが旧collectorを停止し得る。新stageの置き場所は`boat_data_stage`に限る。
- 共通`boat_data`13個はVIEWのまま、本番物理正本切替 **0/13**。旧原本collector、systemd timers、既存バックアップは維持。独立外部保全・全writer/reader監査・実rollbackは未完了。

## A. 事前の停止ゲート：欠ければ初回複製もNO-GO
1. 別途ユーザーが**新stage作成と1表初回複製**を明示承認。GitHubでの設計承認とは区別。
2. 原本の最新整合バックアップをConoHa内に保持し、**VPS外独立新世代バックアップ＋隔離復元試験**を証明。以前のGoogle Drive世代は上書き禁止。
3. `boat_data_stage.entry_snapshots`の不存在、source/VIEWの現在のrelkind、21列と2インデックス/NULL/sequence/default/ACL、旧writer/DDL/子process・読込経路の再調査。重複作成を検知したらSTOP（`IF NOT EXISTS`で継続しない）。
4. CPU/RAM、PG disk/WAL、残空き、collector稼働、lock待ち/statement_timeoutを計測し、保守負荷予算を決める。33MBが小さいという推定だけで強行しない。
5. 今の`boat_data_stage.venues`、`boat_data.entry_snapshots`VIEW、`public.v2_*`、`v5_data.raw_*`を一切変更しない設計であること。

## B. DDL案（検討素材であり実行は禁止）
- ステージ候補`boat_data_stage.entry_snapshots`を新設する際の型・制約コピーは、PostgreSQLの`LIKE public.v2_realtime_entry_snapshots INCLUDING ALL EXCLUDING DEFAULTS`の使用を検討。**後置`EXCLUDING DEFAULTS`でserial DEFAULTを継承しないこと**を独立テストで実証し、生成後カタログでもstage `id`に`nextval`が無いこと、旧sequenceへの依存が無いことを確認する。検査が未完ならDDLを実行しない。
- `INCLUDING INDEXES`により新stage内でPK `id`・自然キーUNIQUE `(race_id,snapshot_label,lane)` を保持。元のインデックス名をそのまま再利用できるとは仮定しない。21列/データ型/NOT NULL/権限・OWNER・trigger/依存・defaultを個別検査する。
- 最初のstageは`id` **DEFAULT無し**にする。原本の`id`を列名明示で初回COPYするため、旧原本の`nextval`も`setval`も使用しない。stageへ将来新規行の独自採番が必要なら、別シーケンスと所有権・最大ID衝突防止を新たに設計・別承認。
- stageにPUBLIC書込権限を付けず、単一postgres所有を基本とする。既存VIEWの付け替え/物理ルートflag変更やcollector DDL guardの変更はこの工程の対象外。

## C. 初回COPY・検証方式（実SQLは作らず未実施）
- 今後承認があれば、原本から同じMVCC snapshotの**全21列・既存idを明示**して1表だけ複製。想定列名：
  `id,race_id,race_date,venue_id,venue_code,race_no,snapshot_label,snapshot_at,source,lane,racer_number,racer_name,racer_class,original_course,exhibition_course,is_course_changed,motor_no,boat_no,tilt,raw,updated_at`。GitHubの列リストは参考で、実際の列順・型を実行直前live catalogで再照合する。
- 短いタイムアウトとWAL/CPU/ディスク保護のもと、**作成・COPY・双方向照合・例外時ROLLBACK**を同じ制御されたトランザクションで設計。NULL・jsonb・timestamptzも含めて全列値とPK id、自然キー集合の一致を確認。片方向のみ・概算行数との一致だけではPASSにしない。
- コピー中の旧writerのINSERT/UPDATE/DELETEは通常どおり続くため、**コピー時点の一致と現在時点の追い付きは別**。snapshot境界を保持し、最終的に全自然キーの再走査または独立実証済みの欠落無しCDCが必要。`updated_at`単独のwatermarkではDELETEやタイムスタンプ不変更新を取りこぼす。
- 差分照合キーはNOT NULLの3列`(race_id,snapshot_label,lane)`。PK `id`との対応も保持し、自然キー変更・ID変化・UNIQUE競合はSTOP。原本欠損・不完全scan・閾値超DELETEでは物理削除しない。
- 大規模分割COPYを行う場合、異なるMVCC時点の単純バッチ寄せ集めでは同期完了としない。各snapshotの整合と最終全キー再照合、欠損/重複/DELETEを検証するまでNO-GO。
- COPYが成功しても**ステージ同期は未完成、本番切替0/13のまま**。全writer静止、正本1系統・readers・短い非購入canary・原子的戻しの実証と別承認が必要。

## D. オフラインfail-closed試験計画（12ケース実装・23:24修正後のConoHa隔離実行12/12 PASS）
| ケース | 故障/入力 | 期待 |
|---|---|---|
| E01 | 21列・PK・UNIQUE・NOT NULL定義の差異 | STOP |
| E02 | source serial defaultをstageへ継承したDDL模型 | STOP（旧sequence絶対不参照） |
| E03 | stage id defaultなし・明示IDの合成コピー | 値一致のみオフライン候補PASS |
| E04 | stage既存・誤った`v5_data.raw_*`・venues再COPY | STOP |
| E05 | 同一snapshotで双方向21列・全キー一致 | 差0を判定、実同期成功とはしない |
| E06 | 異なるsnapshot・途中欠落・推定件数の確定値誤用 | STOP |
| E07 | INSERT・UPDATE・DELETE混在、更新時刻不変変更 | 全自然キー比較で検出 |
| E08 | 自然キー変更、`id`入替、PK/UNIQUE衝突 | STOP、勝手にUPSERTしない |
| E09 | source空/不完全・大量DELETE | STOP（誤DELETE防止） |
| E10 | COPY中の並行writer更新 | 初回同値だけでCDC/追い付き認定しない |
| E11 | COPY途中の失敗・timeout・ディスク不足 | 模擬トランザクション全体ROLLBACK |
| E12 | 新世代独立保全/復元、全writer確認、別承認の欠落 | **常時NO-GO** |

**現況**：entry stage作成=0、entry実COPY=0、venues初回隔離コピー=1/13、本番切替=0/13。E01～E12は`deploy/conoha/boat_entry_stage_guard_offline_20261023.py`に定義済み。GitHub上のreadbackと8静的項目PASS。**23:22初回E11が3 subTest失敗したが、tuple/list比較ミスをGitHubで修正し、23:24にConoHa隔離`/tmp`で12 tests / 0.025s / OK、成功マーカーを確認済み。合成テスト12/12 PASS。**実DBのCOPY・rollback・差分適用を検証したものではない。次は外部独立保全の設定をread-onlyで確認。ConoHaへのDDL/DMLは別の明示承認まで禁止。
