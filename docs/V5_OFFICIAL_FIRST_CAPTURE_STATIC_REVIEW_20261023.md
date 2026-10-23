# V5初回取得保存経路：静的接続レビュー（2026-10-23）

**状態：GitHubコードと既存テストの静的確認のみ。ConoHa未配備、DB変更0、公式HTTP実行0、予想0、購入0。**

## 目的と現在地

- ConoHaの`boat-v5-forward-window.service`は`v5/conoha_realtime_window_pg.py`を介して`v21_realtime_collector_pg_safe.py`を実行し、現在の旧`public.v2_realtime_*`実表へ書き込む。共有`boat_data.*`13VIEWはそのまま読むだけで、物理移動・writer切替ではない。
- 2026-10-23実レース`20261023_21_02`で、同一ラベル`conoha_forward_20261023_090502`の出走6/展示6/オッズ120、K直近5走を確認した。しかし`snapshot_at`/ラベルはUPSERT可能なため**初回取得時点を証明しない**。V5公式事前決定・モデルの本番適合・BUYの根拠にしない。
- 研究用`public.v2_bao_exhibition_shadow_snapshots`と`public.v2_bao_market_shadow_snapshots`は現行forwardの書込先ではなく、当該レースは各0件。Bao向けschemaにあるからといってV5初回証拠として使わない。

## コード経路と阻害条件

| 経路 | GitHub現状 | 安全上の制限 |
|---|---|---|
| `v5/official_http_transport.py` | 注入されたHTTPセッションの実レスポンス**生バイト**・開始/受信完了時刻・sha256から提案のみ作る | 自ら接続/cronしない。記録提案は公式公開時刻や最初の観測の証明ではない |
| `v5/official_first_write_storage.py` | 専用`v5_official_source_first_capture`表の未配備DDL、`ON CONFLICT DO NOTHING`、readback照合契約 | `stored_at DEFAULT now()`はトランザクション開始時刻。commit/first-seenの証明ではない |
| `v5/official_first_write_executor.py` | 明示注入されたDB接続でINSERT/SELECT、重複内容不一致なら中止 | 同じトランザクションの自己照合。独立監査、権限制限、原本性を証明しない |
| `v5/official_capture_pipeline.py` | HTTP→保存提案→DB readbackをオプトインで合成 | `official_beforeinfo`は**PRE-HTTP HARD HOLD**（正式な6艇active出走証拠が未確定）。解除・回避禁止 |
| `v5/conoha_realtime_window_pg.py`＋`v21_realtime_collector_pg_safe.py` | 実運用の旧snapshot upsert、期限9～24分前などの保護 | V5専用official first-write経路を呼び出していない。収集済みのmutableレコードを後からfirst-write原本に変換不可 |

**結論**：最初の設計ゲートは新テーブル設置ではなく、公式HTTPが受信した**元のバイト列と時刻を一度だけ捕捉**する安全な境界を定義すること。既存後処理済みテーブルや`snapshot_at`は原本の代用にしない。現行稼働経路に安易に横付けしても、`beforeinfo`保護制限を解除したことにはならない。

## 接続案（今後の別審査・未実装）

1. **事前HTTP/read-only経路図**：既存collectorの公式GET地点（racelist、beforeinfo、odds）を確認し、原本を改変しない分岐が可能か静的に特定。API/HTML取得を二重化せず、CPU/Network/遅延の見積りを先に出す。オッズは専用source-kind/契約が未定義であり、既存first-writeテーブルの列挙に無理に押し込まない。
2. **独立した安全な保存境界**：source URL、race/resource、HTTP response bytes/hash、req start・body end、サーバー側保存受領、writer権限、競合時の挙動、DB commit、監査者の別トランザクション読取を定義。元の`now()`や同一tx読戻しを独立証明にしない。限定容量、拒否時のコレクターへの非干渉、情報保護、時刻同期、ロール分離、rollbackをレビュー。
3. **after-the-fact認定禁止**：10/23対象レースのimmutable初回原本は未証明。あとで古いmutable snapshotから作る場合は研究用`retrospective/unverified`と明示し、当時のpredeadline proofには採用しない。
4. **正規モデルへ渡す入口を別途整備**：read-only 6艇/展示/120票/K5走の実データ橋は成功。前日までに固定された全5特徴量カウンタ、正規選手6艇開始状態、学習係数の版/日付を独立に検証するまで確率・券順位は本番を名乗らない。結果や払戻を予測前の入力へ混入させない。
5. **物理データ移行は別工程**：旧writerを継続、共有13VIEWを通して読み、バックアップ・最終差分同期・サービス静止・writer切替・復旧証明後に共通`boat_data`を物理正本へ。旧原本削除なし。

## 最小オフライン検査計画（既存テスト再利用、実行未確認）

既存テスト：
- `tests/test_v5_capture_pre_http_hard_hold.py`: beforeinfoのPRE-HTTP拒否、偽の6艇active状態を渡してもHTTP GET/DBが**0件**、storage opt-in前にもIO0。
- `tests/test_v5_official_http_transport.py`: 公式URL限定、リダイレクト/非200/バイトサイズ/clock異常の拒否、body完了時刻と保存提案の分離。
- `tests/test_v5_official_first_write_executor.py`: INSERT→SELECT同tx、同一初回を保全、別バイト衝突・readback/commit失敗のロールバック、eligibleは常に偽。
- `tests/test_v5_official_capture_pipeline.py`: 合成HTTPと合成DBによる接続、beforeinfo HARD HOLD、first-observed/forward flagsは偽。

開発・CIに限り（`sudo`・ConoHa DB・Railway・公式HTTPを使わない）、1ファイルずつ実行して成否を記録：

```bash
python -m unittest discover -s tests -p 'test_v5_capture_pre_http_hard_hold.py' -v
python -m unittest discover -s tests -p 'test_v5_official_http_transport.py' -v
python -m unittest discover -s tests -p 'test_v5_official_first_write_executor.py' -v
python -m unittest discover -s tests -p 'test_v5_official_capture_pipeline.py' -v
```

**合格条件**：実GET=0、実DB=0、デプロイ/タイマー変更0、HARD HOLD=維持、重複/不一致や時刻異常がfail-closed、検証済みでない状態を`forward_eligible`や`buy_eligible`へ昇格しない。GitHubにテストファイルがあるだけではPASS扱いにしない。必要なら次工程で既存テストを実行し、個別の結果に従って最小修正する。

## 次のONE task

**GitHubの安全なオフライン環境で既存`test_v5_capture_pre_http_hard_hold.py`のみを実行**して、現在の静的結論が回帰テストでも成立するか確認する。ConoHaの稼働環境をテストで停止・変更しない。テスト結果が確認できてから他の最小検査へ進む。V5初回取得の本番配備・新DDL/権限・モデル昇格・購入は別承認。
