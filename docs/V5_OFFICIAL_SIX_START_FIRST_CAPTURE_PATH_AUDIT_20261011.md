# V5公式6艇肯定証拠・初観測保存経路のコード監査（2026-10-11）

**対象：GitHub開発ブランチの限定的read-onlyソース監査。DB/Railway稼働・取得原本・本番初回保存の実行確認ではない。既存の大村12R実レコードを再照会していない。変更はこの監査文書とcompact handoffのみ。**

## 判定：Beforeinfo Forward/BUY HARD HOLDを維持

| 経路・コード | コードで確認した動作 | まだ成立していない条件 |
| --- | --- | --- |
| `backfill_historical_beforeinfo_pg.py` | 旧日付の公式`beforeinfo` HTMLを取るバックフィル。保存する`snapshot_at`は`now_iso()`、`source=official_beforeinfo_historical` | 後日収集した過去レースを**当日の実初観測**と認定できない。値がレース前の情報を再現していても、締切前に実際に取得していた根拠にはならない |
| `research/historical_exhibition_reuse_pg.py` | `learning_all/final_ab`から`historical`へ再利用し、`raw.source_snapshot_label`と`raw.source_snapshot_at`を写す。元の値がある場合はcoalesceで保持 | `source_snapshot_at`は参照元保存時刻の連鎖であり、公式原本の**独立した初回書込・締切前観測証拠**ではない |
| `v5/official_http_transport.py` | URL/HTTP原文/レスポンス完了時刻を記録したprovisional receiptを組立。`HTTP_OBSERVED_STORAGE_NOT_EXECUTED`、`first_observed_at=None`、`forward_eligible=False`を返す | HTTPを1回観測したことと、公式公開時刻・真正なfirst-write・締切前の原本保存の成立は異なる |
| `v5/official_first_write_storage.py` / `v5/official_first_write_executor.py` | raw SHA-256、原本保存用INSERTと読み返し一致の設計。executorは接続を呼出元から受けて取引し、readbackを確認しても`first_observed_at=None`・`first_write_confirmed=False`・`forward_eligible=False` | リポジトリ上の設計・処理成功は公式ソースの真正性、初観測、独立監査証拠ではない。コードには「NOT deployed / NOT scheduled」と記載されるが、**今回は実Railway状態を検証していない** |
| `v5/official_racelist_readback.py` | 出走表の元バイト列を読み返し、6艇のlane/racer identityとタイミングを検査 | 出走表の掲載＝締切時点の**6艇全員出走確定**ではない。返す`all_active_verified=False` |
| `v5/official_start_status_provenance.py` | 展示行の構造・取消/欠場表示など**否定証拠**を検出 | 公式6艇出走**肯定フィールドのソース契約が未発見**。`all_six_active_confirmed=False`で固定。展示参加や取消表示なしを肯定証拠にしない |
| `v5/beforeinfo_prewrite_gate.py` | beforeinfo原文と出走表データの一致を検査するが、最後は`ACTIVE_START_STATUS_NOT_PROVEN`で拒否 | 公式肯定ステータスの独立証拠が必要 |
| `v5/official_capture_pipeline.py` | `storage_enabled=True`が必要。beforeinfoは**HTTP前に無条件**`BEFOREINFO_PRE_HTTP_HARD_HOLD_NO_AUTHENTICATED_POSITIVE_START`で停止。caller申告だけでは解禁しない | 肯定証拠の独立検証・ソース定義・安全審査なしにガードを緩めない。V4本番とは切り離す |
| `v5/offline_day_evidence_coverage.py`（開発ブランチ） | `APPROVED_POSITIVE_SOURCE_SCHEMAS=frozenset()`。形式チェック成功でも独立認証/BUYはfalse | 公式肯定ソースの許可契約は未定義 |

## 大村12Rへの限定適用（既存結果の再分類のみ）

`20260501_24_12`（2026-05-01、大村12R、締切17:41）：直近5走×6艇の日付が前日以前でも、`official_beforeinfo_historical`展示の保存`snapshot_at=2026-08-15 13:54:54`、120件の保存オッズ取込は2026-08-03。両方ともレースより後。展示の真の`first_observed_at`は未証明、6艇の独立した公式肯定出走証拠はなし。`source_snapshot_at`が存在しても、再利用保存からの時刻伝播は本物の初観測証明ではない。予測/NO_BUY/決済の完全台帳と返還原本も不足。**PENDING/HOLD**。保存払戻6,180円はV5実利益ではない。

## 解決の順序（提案のみ、未実施）

1. **コード調査**で、公式出走状態の「6艇全員が確定して出走可能」と肯定できるrace_id+lane別**公式明示項目**を発見し、原本HTML/JSONとパーサの実フィールド対応を第三者的に検証。存在不明なら**HOLDを維持**し、「展示6艇」や否定表示なしを代用しない。
2. 肯定証拠が確立して初めて、隔離されたV5環境・必要最小限の権限・原本保存/再読出し・初観測監査を**別承認の下で**検討。DBやRailwayのProduction V4接続、購入処理を触らない。
3. 独立したfirst-write・全日網羅・締切前観測まで確認できたレースだけ、オフラインの正式な時系列実績候補とする。事後再構築の研究サンプルは別区分のまま残す。

**未実施：** 公開公式サイトの追加検索、公式原本の再取得、DB読み、Railway稼働確認、既存テストの追加実行、本番/BUY変更。

**次ONE作業候補：** 開発ブランチの大村12R模擬テスト（追加済み・未実行）をオフライン実行し、`cutoff=None`でも「8月のsnapshot保存は5月締切後」を検出できるか検証。変更は開発ブランチのみ。
