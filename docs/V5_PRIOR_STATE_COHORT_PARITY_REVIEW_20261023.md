# V5前日Counter構築：母集団・数式互換性レビュー（2026-10-23）

## 今回確定した実DBの接続事実
- 2026-10-20、ConoHa `boat_data`共通VIEW＋公式Kへの日付限定read-only照会で、**144レース／出走6艇144／公式Kの正常6艇132／展示同ラベル6艇29／Kと展示双方27**を確認。以前のSQLとPythonアダプターの件数が一致。
- `--counter-shape-preview`も14:24 JSTに正常終了。13Counter**種類ごとの行数計算だけ**成功：`lw=27,lcs=162,lcw=27,rks=162,rkw=27,ps=810,pw=135,vc=27,vn=27,cs=792,ct=396,rcs=792,rct=396`。
- この形状値は `fit=27` と `Kコース候補=132` から算術的に求まる**構造チェック**で、選手別/級別別/場別の学習済みCounterでも、原本認証済みの研究fit適格レース数でもない。`PRIOR_STATE_FITTED=0/FORWARD_ELIGIBLE=0/BUY_ELIGIBLE=0` が正常。

## 実モデルへの接続を阻む3つの数学・証拠ゲート

1. **2系統母集団**：研究元 `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` は、日次の展示込みfit母集団とは別に `hday[day]` の公式K進入歴で`cs/ct/rcs/rct`を追加する。現行の `v5/offline_prior_day_counter_update.py` は `FrozenDay` に含まれるレースのうちfit適格なものに限ってK進入歴を増やす。そのまま使うと展示欠損の正常K（今回は最大105レースの差）が学習から落ち、研究モデルとの母集団一致を保証できない。`v5/offline_research_two_population_day.py` は2母集団を分離済みだが、まだ一日分・厳格HOLDの研究版。研究元がfitレースのある日付だけ `hday`を適用する動作も含め、日付網羅性とパリティをテストする必要がある。
2. **級別キーの一致**：既存結果 `public.v2_race_entries.racer_class` は数値コード（1 B2, 2 B1, 3 A2, 4 A1）。研究元 `clean(e["racer_class"])` は数字の**文字列**をキーにし得るが、現行新アダプターは `A1/A2/B1/B2` に正規化。双方向変換は1対1であり数学的なクラス分割を保持できるものの、**既存保存済みCounterと新Counterをキー変換せず混在させてはならない**。訓練側・推論側は同一キー規約を契約・バージョン固定する。
3. **事故/返還・初回取得時点**：公式Kの6艇形状や `v2_results.result_status='official'` だけでは「返還なし」を証明できない。10/20の `v2_results.raw` は144件とも返還の個別証明を含まず、展示の `snapshot_at` もUPSERT可。現在のreal source adapterは `incident_free_verified=None`/`refund_boats=None` を保ち **学習承認0**。後から事故なしフラグを推定・自動昇格させない。研究で仮説検証する場合は**未認証のretrospective exploration**と別ラベルにし、Forward適格証明・ROI・自動購入を認めない。

## GitHub合成回帰（追加実施）
- `tests/test_v5_offline_research_two_population_day.py` の検査を8件→10件に拡張。**10/10 PASS**（Issue #581 `6358139490`）。追加：13Counter全キーの級別`A1/A2/B1/B2`同一規約、1レースに対するclass/winner/exrank/opponent/venue/進入の実際のCounterキー照合、日付Dの結果Counterを日付Dの予測へ入れると `PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED` で拒否すること。
- これは**合成1日・一部キーのユニット試験のみ**。旧研究全期間の数学的再計算パリティ、実Kの事故返還証拠、前日Counter全期間の保存、初回観測証明は依然未完了。先行のsource shape 144/132/29/27 と混同しない。

## 次に実装するべき最小単位
- **GitHub上のみで、前日までのCounter更新が使う級別キー規約と2母集団（日次K履歴は展示有無と独立）の一致条件をテストする**。対象日/選手6艇/欠測・事故ラベルの合成入力で先に検証する。実DBの全期間COPY・モデル学習実行・出走前選別で事後事故を使うことは禁止。
- 実データ再取得や前日までの全期間ローリングは、この静的/オフラインパリティが成立してから軽量・日付単位で設計。収集サービスと共有13VIEWは継続、BUYはOFF。
