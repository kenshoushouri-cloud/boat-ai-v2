# 地方競馬AI 採用判定ゲート — 2026-09-13

Status: `RESEARCH_ONLY / NO_BULK_DOWNLOAD / NO_PRODUCTION_DB / NO_PAID_DATA / RIGHTS_GATE_BLOCKING`

## 目的

競艇を最優先としつつ、競輪の代替候補として地方競馬を採用する価値があるかを、無料データだけで判定するための事前固定契約。

目標は「1レースあたりの賭け金を大きくせず、月数万円規模の安定した継続収益」。候補数やROIを良く見せるための後付け閾値調整は禁止する。

## 現時点の公式データ事実

地方競馬情報サイトの2026-05-21更新「データダウンロード機能説明書」により、以下が公式に提供されている。

- 当日ファイル: 約2分ごとに更新。
- 月次ファイル: 1日1回、午前2時頃更新。
- CSVをZIPで提供。
- レース情報: 出馬表、払戻金、レース一覧。
- オッズ情報: 中間オッズを含む当日ファイル、競走成績確定後の月次オッズ。
- レース情報の取得可能期間: 1998年1月以降。
- オッズ情報の取得可能期間: 2026年3月以降。
- 過去レース情報には欠損があり得る。
- データ仕様は事前予告なしに変更される場合がある。

Official sources:
- https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf
- https://www.keiba.go.jp/terms.html

## Rights gate — 最優先ブロッカー

公式説明書は利用規約への確認を明示している。現行利用規約では、サイト掲載情報の権利は原則として主催者等に帰属し、事前許諾のない転載・複製を禁止している。

この文言だけでは、以下が明確ではない。

- 自動・反復ダウンロード
- 長期保存
- 機械学習用データセットへの変換
- 商用/収益目的の予測モデル学習
- 派生特徴量・学習済みモデルの継続利用

したがって、現段階では次を禁止する。

- NAR CSVの大量/全期間ダウンロード
- Railway/PostgreSQLへの地方競馬raw data保存
- boat Production DBへの同居
- raw CSV/ZIPのGitHub保存
- 継続スクレイピング
- モデル学習用の恒久データセット構築

外部問い合わせ送信は別途ユーザー承認が必要。許諾または十分明確な利用条件が確認できるまでは `BLOCK_BULK_ARCHIVE_AND_TRAINING_PENDING_RIGHTS_CLARITY` とする。

## データリーク防止契約

公式CSVは「予測時点で利用可能な項目」と「レース後に確定する項目」が同じファイルに混在し得る。タイムスタンプ証拠がない項目を安易に特徴量へ入れない。

### 歴史バックテストで current-race feature として禁止

少なくとも以下は、当該レースの予測特徴量へ入れない。

- 着順
- タイム
- 着差
- 上がり3F
- コーナー通過順
- ハロンタイム
- 当該レースの払戻金
- 当該レースの確定人気
- 月次ファイルの確定オッズを「予測時点のオッズ」として使用すること

天候・馬場状態など、実際には発走前に利用可能になり得る項目でも、歴史ファイルだけでその時点性を証明できない場合は、最初の歴史モデルでは除外する。Prospective captureで発走前timestampを持てた後にのみ追加検証する。

### 初期モデルで利用候補

- 競馬場
- レース番号
- 距離
- 芝/ダート
- 回り
- 条件/クラス
- 頭数
- 枠番/馬番
- 馬の性・年齢
- 負担重量
- 騎手・所属
- 調教師・所属
- 馬体重・増減（発走前取得を確認できる範囲）
- 過去レースだけから算出した近走成績
- 過去レースだけから算出した距離/競馬場適性
- 過去レースだけから算出した騎手/調教師成績

馬識別は馬名だけに依存せず、利用可能なら `正規化馬名 + 生年月日` を基本キー候補とする。騎手・調教師は `正規化氏名 + 所属` を基本キー候補とする。

## オッズ利用契約

2026年3月以降の月次オッズは、原則「確定後」のデータであり、歴史検証では **実現価格/払戻評価用** として扱う。

禁止:
- 確定後オッズを、発走前に見えていたものとしてselection ruleへ入力する。
- 後から得た人気順位を用いてcandidateを選ぶ。

Prospectiveでは、権利ゲート通過後に当日ファイルを発走前にfreezeして初めてEV/value signalとして利用可能とする。

初期Prospective odds freeze候補:
- primary: 発走10分前を目標
- missing/late capture: fail-closed
- freeze時刻が発走後または発走時刻不明: evidence不採用

## 研究対象の賭式

安定収益目標を優先し、初期研究は低分散側から進める。

Primary:
1. 単勝
2. 馬複

Secondary diagnostic:
- 馬単
- 複勝（オッズレンジの扱いを固定できた後）

初期段階では3連単を主戦略にしない。3連単は高分散・単一高配当依存になりやすく、安定収益目標に合致する証拠が出た場合のみ後段で評価する。

## データ期間とOOS設計

権利ゲート通過後も、最初から1998年以降を全取得しない。

Phase A — outcome model pilot:
- 直近2〜3年のレース情報から開始。
- 過去 -> 未来のchronological splitのみ。
- 同じ未来期間を繰り返し見てfeature/閾値を調整しない。

Phase B — market/economic historical diagnostic:
- オッズ利用可能な2026-03以降のみ。
- 月次確定オッズはrealized price評価用。
- price-aware selectionの利益性を確定扱いしない。

Phase C — prospective value evidence:
- 発走前freezeのみ。
- selection ruleをfreeze後に変更しない。
- 30/50/100/300/500 bet milestonesで評価。

## モデル評価

利益より先に確率品質を評価する。

必須:
- multiclass winner probability calibration
- LogLoss
- Brier score
- calibration/reliability table
- venue別、距離帯別、頭数別の崩れ
- walk-forwardのみ

単純baseline（例: 一様確率/過去勝率ベース）を安定して上回らない場合は、ROI探索へ進まない。

## 経済性評価

100円を1 unitとして評価し、実際の払戻金を使う。

必須指標:
- bets
- hit rate
- investment
- return
- profit
- ROI
- max losing streak
- max drawdown in units
- positive day ratio
- positive month ratio
- venue concentration
- max single-hit return share
- top-3 hit return share

高ROIでも、少数高配当への依存が大きい場合は不採用。

## 事前固定 milestone gate

### 30 bets
- smoke/sanity only
- 昇格判断禁止

### 50 bets
- preliminary only
- 昇格判断禁止

### 100 bets
研究継続の最低条件。全て満たすこと:
- ROI > 100%
- max single-hit return share < 25%
- purchase rule / odds window / bet typeを後付け変更していない
- timing-clean = 100%

### 300 bets / >= 60 calendar days
Research-adopt候補。全て満たすこと:
- ROI >= 105%
- bootstrap 95% CIの下限が著しく100%を下回らない
- max single-hit return share < 15%
- top-3 hit return share < 35%
- max drawdown <= 20 units
- 少なくとも3競馬場にまたがる
- 1競馬場だけで総profitの過半を作らない

### 500 bets / >= 90 calendar days / >= 3 calendar months
Production review候補。全て満たすこと:
- ROI >= 105%
- 95% bootstrap ROI lower bound >= 100%
- positive months >= 2/3
- max single-hit return share < 10%
- max drawdown <= 20 units
- candidate volumeを増やすための後付け閾値緩和なし
- 権利条件がProduction利用まで明確

条件を満たしても自動Production昇格は禁止。別途明示承認が必要。

## 月数万円目標のunit economics gate

ROIだけで採用しない。

各固定戦略について、実際の月間candidate数から以下を計算する。

`expected_monthly_profit = median_monthly_bets × stake_per_bet × (ROI - 1)`

さらに、1レースあたりの総賭け金上限を低く保つシミュレーションを行う。

Production review時の目標:
- 1レース総額: 原則500円以下を第一評価
- それでmedian monthly profitが月2万円未満なら、ROIが良くても本プロジェクトの主目標には弱い
- 賭け金を大きくしないと月数万円に届かない戦略は不採用寄り
- 25th percentile monthが大幅赤字の戦略は「安定収益」要件に不適合

## 容量契約

地方競馬データを `boat-ai-v2` Production DBへ入れない。

権利ゲート通過後のpilotでも:
- 最初はローカル/一時研究のみ
- raw ZIPを永続保存しない設計を優先
- 正規化研究データ + metadata/hash中心
- pilot hard cap: 合計500 MBを目安
- Railwayへ移す場合は別project/別DBを原則
- 競艇の5GB volume headroomを地方競馬のために消費しない

Full historical 1998+ ingestionは、pilotで利益性が見えた後にのみ再検討する。

## 採用/不採用判定

### 採用方向
以下を全て満たす場合のみ次段階へ進む。
- 利用権利が明確
- timing-safeデータ収集が可能
- leakage-free modelがbaselineを上回る
- prospective ROI/安定性gateを通る
- 低い1レース賭け金で月間unit economicsが目標に近づく
- Railway容量を競艇から奪わない

### 不採用
以下のどれかで停止。
- 権利が不明確なまま
- timing-safe odds capture不可
- データ欠損/仕様変更で再現性が低い
- 300〜500 betでROI/安定性gateを通らない
- 利益が1〜2件の高配当に集中
- 月数万円には大きな賭け金が必要
- 維持コストが競艇/TOTOの価値を下回る

## 現在の判断

`LOCAL_HORSE = TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`

技術面では、公式CSVに出馬表・レース情報・払戻・オッズが揃っており、候補として十分強い。一方、オッズ履歴は2026-03以降に限られ、かつ利用規約上の長期保存・ML利用・収益目的利用の明確性が不足している。

したがって、現時点では「採用」でも「不採用」でもなく、**権利確認前の研究設計完了状態**とする。
