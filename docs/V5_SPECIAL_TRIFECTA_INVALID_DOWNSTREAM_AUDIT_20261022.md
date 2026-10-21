# V5 3連単不成立1R — 復旧後の下流ROI適用監査（2026-10-22）
対象: `20261008_14_05` 鳴門5R。GitHubコードのみ読取。**本番DB/購入/学習重みを変更しない。**

## 復旧確認済み
- 2026-10-22 00:20 JST のTermius証跡: `SPECIAL_RESULT_ONE_INSERT_VERIFIED_NO_EXISTING_UPDATES`, `ALL_FOUR_DAYS_OFFICIAL_RESULTS_ACCOUNTED_FOR`, `SPECIAL_RESULT_WRAPPER_COMPLETE`。
- 4表最新バックアップ `/root/boat-v5-backups/k_results_preinsert_20261022_002007.dump` 43MB、SHA256/TOC PASS（ローカルのみ、外部保存・復元試験は未確認）。
- 対象4日: 2026-10-08=144、10-15=156、10-16=156、10-17=168、計624/624レース結果。**V5全期間が完全になったこと、的中・収益性は示していない**。
- 10/08鳴門5R：公式K/HTMLで`result_status=trifecta_invalid`,`race_status=official`,`trifecta_ticket=NULL`,`trifecta_payout_yen=0`。3連単不成立であり**通常不的中ではない**。履歴取得は締切前証拠ではない。

## 2026-10-22現在の下流コード点検（ソース読取のみ）
| 実装 | 観測事実 | 判断 |
| --- | --- | --- |
| `v5/conoha_midnight_results_pg.py` | `resolved()`は`trifecta_invalid`を終端扱い。再取得候補から除外する。 | **再取得判定OK**。自動upsert経路の継続使用は別途運用範囲確認。 |
| `backtest_candidate_filter_rules_pg.py` | SQLに`trifecta_ticket IS NOT NULL`,`trifecta_payout_yen > 0`,`result_status='official'`,`race_status='official'`。 | **通常3連単結果として混入しない**。ただし元の選択母集団ごと後知恵除外するとROIが偏る。 |
| `backtest_n02_walkforward_pg.py` | 同じ正常3連単・正払戻・official statusフィルタ。 | **通常結果のロード除外を確認**。元選択母集団の欠損・返還は別管理が必要。 |
| `research/forward_economics.py` | `evaluation_status='invalid_result'`は`investment_yen=0`として計算。 | **実購入がある前提では未合格**。購入済み金額を消さず、真の返還額との照合が必須。 |
| `v5/offline_trifecta_cash_ledger.py` | モック注文と`MockTicketReturn(refund_yen)`により返還金を含む収支計算。 | 形はあるが**公式の艇番別返還原本/注文・発券証跡と未連結**。これだけで実ROIの証明不可。 |

## V5の合格条件（次の設計）
1. 結果の「不成立/欠場/返還」と「正常不的中」を区別し、決定時点で選んだ元の対象母集団から結果を後知恵で抹消しない。
2. **購入なし**は予測研究の「非成立」として分母対象外、**購入あり**は購入金額を記録し、公式に証明した券別返還額を収益側へ計上。不明なら`PENDING`。終了結果だけを見て0円損失・0円投資額を仮定しない。
3. 元の締切前予測、選択券・金額、当時のオッズ・発券証拠と事後公式結果・券別返還原本の照合が揃うまで**実V5 ROI未検証**。過去補完結果を締切前入力へ混入させない。

**Next ONE task**: V5の現在実際に呼び出される収支報告ルートと返還証拠の保存先をさらに確認し、誤算入がある場合は先に読み取り専用の警告テストを作る。削除・有料リソース追加・本番動作変更・自動購入はしない。
