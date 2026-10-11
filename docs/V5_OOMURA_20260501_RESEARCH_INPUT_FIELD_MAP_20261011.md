# V5大村12R：保存済み1レースと研究用バックテスト入力の対応（2026-10-11）

**対象レース** `20260501_24_12`（2026-05-01・大村12R）。GitHub開発ブランチのコードと既存証拠資料のみ照合。**Railway/DBの再照会なし、公式原本/予測凍結の再取得なし。実V5の収益・購入可能性は一切証明していない。**

参照：`docs/V5_OOMURA_20260501_24_12_EVIDENCE_GAPS_20261011.md`、`docs/V5_PREDECISION_FEATURE_LINEAGE_TO_REAL_ROI_20261011.md`、`ops/v5_one_race_six_lane_feature_lineage_readonly_20260501.sql`、`v5/offline_archived_six_lane_bridge.py`、`v5/offline_mainline_inference.py`、`v5/offline_retrospective_result_adapter.py`。

**区分**：値確認＝既存保存結果で値または個数が分かること、形のみ＝ソース列/集計だけで完全な入力は未取得、未証明＝過去の意思決定または原本の真正性が確認できないこと。「値確認」は**締切前に取得済み**を意味しない。

## A. `ArchivedRaceFactors` / 6×`ArchivedLane` の入力項目

| 必須項目 | 保存された事実と不足 | 区分・扱い |
|---|---|---|
| `race_id` | `20260501_24_12` | **値確認**、対象レース限定 |
| `deadline_at` | 2026-05-01 17:41（現地時刻として参照） | **値確認**。厳密なタイムゾーン付き元レコードは今回未再読 |
| `decision_cutoff_at` | 当時のV5意思決定時刻・凍結記録なし | **未証明・入力不可**。締切から機械的に減算しない |
| `model_fitted_through` | 研究全体の学習上限日は別資料に存在するが、**このレースの当時固定された模型インスタンス**の最終学習日・識別子は未接続 | **未証明**。一般研究の最終日で原本を代用しない |
| `base_probabilities`（6要素） | 6艇の「対象日までの」艇番×級別実績Counterからの出力6値が未保存/未照合 | **未取得**、推定値の捏造不可 |
| `factors["recent_form"]`（6要素） | 6艇×5走=30走、各履歴日が4/30以前と確認。**個々の原履歴・計算値・取得時刻は未照合** | **日付境界のみ値確認**。ベクトル6数値は未取得 |
| `factors["exhibition_rank"]`（6要素） | 展示順位 `[3,1,4,2,6,5]` 保存済み。補正倍率の前日学習Counter未接続 | **順位値のみ確認**。6補正値は未取得 |
| `factors["racer_course"]`（6要素） | 前日までの公式Kコース別Counterを作るコードは存在。対象日用学習状態の実値・原本は未照合 | **未取得** |
| `factors["opponent"]`（6要素） | 6艇の級別と対戦相手相性Counterが必要。元の出走6艇級別具体値・前日学習状態は未照合 | **未取得** |
| `factors["venue_lane"]`（6要素） | 場 `24` はレースIDから確定。場×艇番の過去実績6値は未照合 | **場の識別値のみ確認** |
| `lanes[].lane` | lane1～6の6行存在・直近5走の歴史レコードを既存UIで確認 | **形のみ確認**。各行の完全な固定オブジェクトではない |
| `lanes[].racer_number / racer_class` | 6行に列の存在フラグがあるが、6艇それぞれの**実際の登録番号/級別値・締切前肯定出走原本**は監査資料に未保存 | **未取得/未証明** |
| `lanes[].recent_form` | 5行ずつarrayという形と前日以前の日付のみ確認。元の各dict内容は未取得 | **形のみ** |
| `lanes[].exhibition_time_rank` | lane順で `(3,1,4,2,6,5)` | **値確認（事後取得）** |
| `lanes[].exhibition_source / snapshot_at` | `official_beforeinfo_historical`・`2026-08-15 13:54:54`。既存DB列のタイムゾーン型/初回観測根拠は今回未再照合 | **保存値確認**、明確に5/1締切より後、締切前証拠ではない |
| `ticket_count` / `stake_per_ticket_yen` | V5として当時固定した点数・1点金額の記録なし | **未決定**。V4点数・金額を転用しない |

**判定**：`ArchivedRaceFactors`を実保存値で合法に完成できず、`build_archived_rank`へ渡して実V5予測/仮想券を算出したとは主張できない。保存展示6艇が事後である点は、研究上の特徴量再構築として明示し、`original_first_observation_verified=False`を維持。

## B. `StoredResultRow` と全レース台帳

| 必須項目 | 既存保存値 / 根拠 | 判定 |
|---|---|---|
| `race_id` | `20260501_24_12` | 値確認 |
| `result_status` / `race_status` | レースごとの公式確定ステータス原本を今回未照合 | **未証明**。勝ち券と払戻の存在だけで`official`に昇格させない |
| `winning_ticket` | `2-1-5` | 保存値確認、公式原本照合とは別 |
| `payout_per_100_yen` | 6,180円（保存最終オッズ61.8倍×100円との内部整合） | 保存値確認。実V5の利益ではない |
| `refund_boats` | 返還欄の原本未確認 | **`None`維持**。空tuple（返還なし確定）に置換禁止 |
| `refund_section_verified` | 公式返還欄の独立照合未実施 | **False** |
| `whole_race_void_verified` | レース全額返還の原本/ステータス未照合 | **False/未証明** |
| `FrozenDay`と全レースInventory | 大村12Rの当時固定`race_id+ticket+stake`不在、同日の全候補・NO_BUY・PENDING網羅は未証明 | **PENDINGとして保持**。結果の良い1レースだけで分母を定義しない |

`StoredResultRow`は**結果原本と返還確認がない限りPENDING扱い**とする。 `v5/offline_retrospective_result_adapter.py:_stored_to_official`は結果・レース状態双方が`official`でない限りPENDING、確認済み返還欄なしは`refund_boats=None`となる。既存払戻関数は、その場合の全候補仮想ROIを公開せず保留する。

## C. 結論と次ONE作業

- **既存保存値のみで安全に表示できるもの**：レースID、締切参照、6艇の前日以前5走という日付境界、事後展示順位/保存日、保存3連単結果と払戻の数値内部一致。
- **実データ入力の欠損**：6艇の具体的選手/級別とrecent_form原レコード、対象日以前で固定した6要素×（基本確率＋5因子）、モデル最終日、意思決定cutoff、仮想買い目の点数/額、結果ステータス/返還原本、対象日全レースinventory。
- **仮想V5勝利の捏造は禁止**：`2-1-5`を後知恵で選択せず、オッズ61.8を意思決定時の市場価格と扱わず、報酬6,180円をV5利益としない。`20260501_24_12`は`PENDING/HARD HOLD`、`v5_real_roi_verified=False`、`forward_eligible=False`、`buy_eligible=False`。

**次ONE作業（別ターン）**：この表に基づき、必要なときに1レース×6艇だけ読める最小限のread-only抽出仕様を既存`ops/v5_one_race_six_lane_feature_lineage_readonly_20260501.sql`へ照合し、6艇生値と「未取得はnull」とする安全な入力検査契約を設計。新規Railway SQL実行・有料Actionsはまだ行わない。

**未実施**：新DB問い合わせ、HTTP取得、本番変更、テスト実行、BUY。
