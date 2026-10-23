# venues 差分反映・切り戻し安全プロトコル（2026-10-23 / 設計のみ）

**状態：DESIGN_ONLY / NO-GO。実行SQL・本番コード・cronは追加しない。**
対象は唯一の原本 `railway.public.v2_venues` → 既に24行初回複製した隔離物理表 `railway.boat_data_stage.venues`。既存の `v5_data.venues` は別の古いstageで保持。 `boat_data.venues` は `public.v2_venues` 依存の非更新VIEWで、ステージではない。残り12共有表もVIEWであり変更しない。

## 現在までに実証済み（根拠：10/23 Termius画像）
- 19:32 ローカル新世代 `railway` dump約375MB、venues限定の隔離DB復元24件PASS、後に一時DB残存0。**railway全体の復元・別DBの復元・VPS独立バックアップは未実証**。初回stageより前のバックアップ。
- 19:50 ユーザー承認のもとstageを1回だけ作成して24行物理複製/全列同値をCOMMIT、19:51再監査も双方向差0、19:52 read-onlyでSAME24/INSERT0/UPDATE0/DELETE0。
- 20:01 Python合成テスト17/17 PASS（`deploy/conoha/boat_shared_venues_delta_plan_offline_20261023.py`）。**これは継続差分同期・実書込の証明ではない**。
- 現行 `repair_month_all_pg.py` の `ensure_venues` は起動時に全会場を生成し `ON CONFLICT(venue_id)` でUPSERT、`updated_at` を更新。stageの物理PRIMARY KEYは `venue_code`、別UNIQUEは `venue_id`。原本→旧 `v5_data.venues` に24件の更新時刻差あり。現行 `v5_daily_table_routes.py` の `shared_venues_v1` は **書けない `boat_data.venues` VIEW** に向いており、有効化禁止。

## 1. ライフサイクルと実際のGO条件
| 段階 | 状態 | 許可されること |
|---|---|---|
| S0 構造確認・バックアップ | venues限定のみ確認 | read-only監査 |
| S1 隔離stage初回作成 | **24件完了** | **再CREATE/再COPY/削除禁止** |
| S2 オフライン全PK全列diff | 合成17/17 PASS、実DB一時点差0 | 差分計画の静的検証 |
| S3 stage差分DML試験 | **未実施・別承認必要** | 承認後にのみ、限定・ロールバック可能な試験 |
| S4 13表の旧writer→新物理正本切替 | **0/13、全面NO-GO** | 一体監査・独立保全・再現試験・別承認なしでは不可 |
| S5 深夜無人切替/旧原本削除/BUY | **未承認** | スケジュールだけではGOにならない |

## 2. 完全性と同一時点の証明（必須）
1. `public.v2_venues` と `boat_data_stage.venues` それぞれが意図した物理表であること、`boat_data.venues` が旧原本を読むVIEWのままであることをlive catalogで確認。既存stageの上書き禁止。
2. `venue_code` は必須・一意なPK、`venue_id` はNULLを許すUNIQUE（そのままコピーするので意味を変えない）。6列 `venue_code, venue_name, created_at, updated_at, venue_id, is_active` の型/NULL/デフォルト/索引/権限/トリガ/ビュー依存を確認。列順ではなく列名で比較。 `timestamptz` は値の同一性を評価し、文字列表現だけで誤UPDATEしない。
3. **両表を同じ一貫した読み取り点**で観測する。単独の `SELECT count(*)` や異なるトランザクションのスナップショットを寄せ合わせない。全PK（期間・updated_atフィルタなし）と6列の双方向 `EXCEPT ALL` /完全列比較により INSERT・UPDATE・DELETE を求める。
4. 片方だけ範囲欠落・途中打切り・スキャンの失敗・NULLキー・重複PK/UNIQUE・スキーマ不一致・不一致の時点トークンがあれば**STOP**。特に0行の「原本」は障害の可能性として**DELETE一斉適用を禁止**。予想外の高いDELETE/総変更率にも閾値と人間の判断が必須。
5. 直近比較0件は**その瞬間だけ**の整合性であり、翌朝の `updated_at` 更新・他writerによるINSERT/DELETEを保証しない。日付watermarkだけではDELETEを拾えず、連続運用には全キー再照合または変更履歴捕捉の独立検証が必要。

## 3. writer静止と一貫性（将来の承認作業の方式候補）
- まず全writer/reader/DDL、systemd timer、wrapper、子プロセス、手動/backfillジョブを列挙して現物と照合。morning07:00/night23:00/forward5分/midnight01:20の候補に加え、その他のroot/psql/サービス書込みを監査。**現在の収集は停止しない**。
- 初回stageの差分反映を実証する場合は、**別の明示承認を得た限定保守枠のみ**で、実行中writer終了を確認した上で新規書込みが入らない状態を保証する。提案方式は同一DBトランザクション内で原本・stageのDMLと競合するロックを獲得し、その**後で**同一スナップショットを作る。ロック取得後のREAD COMMITTED明示スナップショットまたは適切なトランザクション順序をレビューする。ロック取得前にREPEATABLE READのスナップショットを確立すると古い視点を固定し得るので禁止。
- 原本側の `ROW EXCLUSIVE` 書込みを遮断できる適切な表ロック（例：`SHARE ROW EXCLUSIVE`、具体的ロック設計はDB実行前レビュー）を短時間保持し、`lock_timeout` と全体 `statement_timeout` を上限設定。待機中writerの溜まりや長期停止を避ける。単にtimerを無効化しても既存子プロセスを止めた保証にはならない。
- ロック/静止期間外に先に全件diffを計算しても、その結果を無条件に適用しない。新規変更を捕捉していない限り再計算し直す。stageへの同期を実施しても旧writerは旧原本のまま継続。**stageの同期成功 ≠ 正本切替許可**。

## 4. INSERT / UPDATE / DELETEの反映順序（実行手順ではなく候補）
- **INSERT**：旧原本にのみ存在する `venue_code` を計画。作成時には `venue_id` UNIQUE競合の可能性を別途検査する。既存レコードの `venue_id` 移動/入替は一度に片方ずつUPSERTすると一時UNIQUE違反が出るため、全グラフ衝突解決/制約温存の設計が確定しない限りSTOP。
- **UPDATE**：同一 `venue_code` だが6列が異なる行のみ。 `updated_at` のみ更新も含む。PKや `venue_id` の変更・交換・移動、NULLの意味が未解決なら停止。 `ON CONFLICT(venue_id)`（現行collector）と `ON CONFLICT(venue_code)`（物理PK）を同一のものとして扱わない。
- **DELETE**：stageにのみあるPKを候補扱い。原本が完全に検証済みで、削除が真の原本削除であること・下流参照の影響・削除閾値・戻し用before-imageが確保されたことを個別承認するまで**実DELETEをしない**。落ちた一部のページや欠損readから削除しない。
- 同一原子的トランザクション内で制約・INDEX・triggerの影響を保ち、反映後は**件数、双方向全PK/全列照合、VIEW旧原本一致、権限維持**まで確認。いずれか不一致なら例外として全面ROLLBACK。COMMIT前に再取得したスナップショットで「最終ゼロ差」を検査する。
- これは**設計順序**であり、SQLファイル、DB書込、実適用CLI、cron、切替スイッチは作らない。孤立stageの同期でも実DBへのDMLは別の明示承認を要する。

## 5. 復旧と監視
- COMMIT前失敗：**ROLLBACK**、stageと原本の両方向差をread-only再検査し、エラー分類と独立ログを保全。旧writerルートは一切変更しない。
- COMMIT後にstage異常：原本を正本として継続。stage上書き・再作成による修復は禁止。まず差分と原因を調査し、バックアップ新世代＋段階的復旧を別承認。
- 本番切替で異常：13系統を通じて**単一正本writer・reader・VIEW依存**の原子的戻しが実証済みでなければNO-GO。旧/新両方への並行書込み（split-brain）禁止。
- 非購入canary：監視対象は読み書き経路、件数、エラー、初回取得時点・証拠の整合、collector再開。**実予測ROI、投票・BUY可否とは別審査**。失敗時は即座にNO-GO、勝手に深夜予約しない。

## 6. 決裁の未充足項目（どれか1つ欠けてもNO-GO）
- [ ] 現在時点の独立（VPS外）新世代バックアップの整合性と隔離復元PASS。古いGoogle Drive8ファイルを保護し上書きしない。
- [ ] 全 writer・reader・子process・DDL・timer/cron/手動タスクの実行経路を確証。
- [ ] 現行/提案stageの権限、依存、連鎖変更、`venue_id` UNIQUE競合とDELETEの解決・実DB限定復元試験。
- [ ] 一貫snapshot＋writer静止＋全キー最終差0＋失敗ROLLBACKの演習（実適用は別承認）。
- [ ] 予想外差分・lock待ち・CPU/RAM/WAL/ディスク・取得失敗時のNO-GO自動失効条件。
- [ ] 13表を同時に適切に切り替えるwriter/readers/VIEW/rollback検証と短い非購入canary。
- [ ] **ステージ差分DML・本番切替の各操作に対するユーザーの個別明示承認**。

## 7. 運用の絶対禁止
`boat_data_stage.venues`の再CREATE/無条件再COPY/DROP、`v5_data.venues`の上書き、旧 `public.v2_*` のDELETE/rename、`boat_data.*` VIEW置換、`shared_venues_v1`有効化、勝手なwriter/collector/timer/cron変更、`deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh`・`boat_shared_bulk_stage_20261023.py --apply`の実行、Git pull、無断費用、Railway Agent/AI、BUY。13種類中**初回隔離stageコピー1/13、物理正本への本番切替0/13**を維持する。

**次の現実的な検証：GitHubだけで本プロトコルのfail-closed条件を合成テスト化する。DB実行は別承認が出るまで不可。**
