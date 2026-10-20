# V5 専用データ保存・参照先の再編成計画 — 2026-10-21

Status: **DESIGN ONLY / CONOHA未適用 / 原本移動・削除なし**  
User direction: V5本体・バックテスト・Forward稼働を進める前に、保存先の体系を整理する。費用・容量・既存データ保全を優先。

## 目的・重要な分離
- V5の **正本データ/現場で観測された締切前スナップショット/事後結果/モデル予測と仮想収支/古い研究・原本アーカイブ** を混同しない。
- バージョン差による収集元の食い違いを隠すのではなく、ソースの責任と更新予定を台帳化する。
- ConoHa 2GBでの容量・RAM/CPU負荷を抑える。不要な全表複製、新たなDB常駐サービス、新規課金、サービス停止はしない。
- 歴史原本は`boat_history_archive`と暗号化外部バックアップを保存し、V4復旧資産を保全。歴史データを締切前に取得済みだったかのように扱わない。

## 実測（ConoHaローカル `railway` DB、2026-10-21のread-only確認）
- 2026-10-07〜10-20：`v2_races`=1,860レース、`v2_results`結果1,570件。1,570件全部が`v2_race_entries`の6艇と結合可。
- 同期間`v2_result_entries`には0件。公式Kファイル由来の同テーブル結果は2026-10-06まで、422,544行。
- 2026-10-20 出走表864件中`recent_form`非空0件。原因候補は`repair_month_all_pg.py`（`v2_results`）と`save_k_day_results_pg.py`（`v2_result_entries`）が別収集経路で、ConoHa日次は前者のみを呼ぶこと。
- 2026-10-21 朝収集156レース/936艇で07:46に成功。締切前収集は共有ロックと競合。衝突時のExit75をsystemd正常扱いにする修正が導入されたが修正後の実再現は未検証。

## 目標アーキテクチャ（論理的な名前。物理CREATEは監査後）
| V5公開論理名 | 現行候補元 | 保存・検証規則 |
|---|---|---|
| `v5_data.races` | `public.v2_races` | race_id主キー、race_date、deadline_at、開催中止 |
| `v5_data.entries` | `public.v2_race_entries` | (race_id,lane)単位、racer_number/racer_class等 |
| `v5_data.racer_results` | `public.v2_result_entries` | 全6艇着順・事故・取得元。歴史K欠落は欠落として表示、偽補完しない |
| `v5_data.results` | `public.v2_results` | 正式3連単払戻・結果。選手6艇着順テーブルとは別 |
| `v5_data.exhibition_snapshots` | `public.v2_realtime_exhibition_snapshots` | 取得時刻、snapshot_label、完全性、締切前判定 |
| `v5_data.odds_snapshots` | `public.v2_realtime_odds_snapshots` | 120点・取得時刻・公式出所・締切前判定 |
| `v5_data.weather_snapshots` | 実表名要再確認 | 場/レース/取得時刻、締切前性を明示 |
| `v5_data.motor_stats` | 実表名要再確認 | モーター交換日・標本数・時系列を保持 |
| `v5_data.racer_history_asof` | 公式K全着順＋必要なら歴史保管庫 | レース日より前の成績のみ；利用可能時刻の証明とは区別 |
| `v5_research.predictions` | 新設候補 | V5 version、判断時刻、入力証拠ハッシュ、3連単120通り/選択、BUY不可がデフォルト |
| `v5_research.settlements` | 新設候補 | 成績/返還の公式証拠、PENDING/VOID/返還、試算と実購入を別集計 |

`v5_data`/ `v5_research` は構想上の schema 名。既存同名schema確認後に作成する。 **初回はVIEW/読み取り用のアクセス層を基本**とし、旧テーブルから大量にCOPYしない。既存のV5 Pythonモジュール名とは別管理。

## 移行の5段階（各段階で独立承認・検証）
1. **棚卸し（READ ONLY）**：DB/schema/table/行数推定/実容量/索引/参照先/更新プログラム/日時・source項目/過去原本の有無、欠落日を記録。行数の完全性を`pg_class.reltuples`推定値で主張しない。
2. **参照層（最小DDL、別承認）**：`v5_data`を既存テーブルの限定VIEWから構築。既存スキーマと既存アプリに影響しない。実表名/型を確認したものだけ作る。UPDATE権限は与えない。
3. **収集経路の統一（別承認）**：ライブ毎日`v2_races`/`v2_results`、公式Kファイルの選手別詳細結果、5分前展示/オッズを業務別に監督。競合ロックの分離は独断でせず、タイマー実負荷と欠落時間帯を確認。重複取得・不必要なHTTP連打を避ける。
4. **V5入力統合と予想原本（別承認）**：使用時点の条件を満たすスナップショットのみ入力。欠落・事後の情報はHOLD。固定V5モデルの重みは不変。研究用予想記録は不可逆性/再現性を別確認、過去の再実行を事前予想実績に算入しない。
5. **旧保存データの縮退（別明示承認）**：件数と識別子・ハッシュ監査、DBリストア試験、Google Drive暗号化バックアップ照合、V5依存解消を完了してから。削除対象を列挙し最終承認。Railwayクラウド削除予約状態と混同しない。

## 禁止・成功条件
- 元`public.v2_*`の無断UPDATE/DELETE/DROP、V3/V4の消去、無断データ重複COPY、秘密値のチャット/GitHub流出、無断BUY/LINE/Telegram実送信、V5モデル重み変更禁止。
- 新設VIEWを作っても、未来情報漏洩対策・Forward一次取得証拠・真正の3連単ROIが完成したことにはならない。
- 移行成功は「**欠落と出所が分かり、V5が日時条件付きで参照でき、旧系を残したまま同じ結果を再現できる**」状態。ファイル名の統一だけで成功とはみなさない。

## Next ONE task
ConoHa Termiusで **DB内既存schemaの有無と主要テーブルの容量見積りをread-onlyで確認**。結果を見て、次回はV5アクセス層を重複データなしで実装する具体DDLを作る。リソース上限/他timerとの共存を優先する。
