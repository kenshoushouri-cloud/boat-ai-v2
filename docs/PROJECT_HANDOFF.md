# boat-ai-v2 Project Handoff

更新: 2026-09-13 JST

この文書は次チャットが安全に再開するための CURRENT / HOLD / NEXT を残します。SHA・PR・CI・Railway状態は再開時に必ず再取得してください。

## 再開時

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/CHATGPT_BOOTSTRAP.md` と本書を読み、current `main`、open PR、PR #351の最新head/Actions、Railway Production read-only healthを確認してから続行してください。GitHub `main`をProduction codeのSource of Truth、Railway PostgreSQLをProduction dataのSource of Truthとします。安全なread-only監査・研究・Draft PR・CI・文書整理は連続して進めてよいですが、Production変更は明示承認まで実施しないでください。

## CURRENT — Source of Truth

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Production code: GitHub `main`
- 2026-09-13 checkpoint main: `8abbb0186852969129175848ee106118031f97e4`
- Production DB: Railway project `boat-v2-postgres` / `postgres-recovery`
- Candidate Discovery primary research: Draft PR #351
- Branch: `research/candidate-discovery-v1-20260913`
- PR headは必ず再取得し、本書のSHAを固定値として扱わない。
- `purchase_action=false` / fail-closed。

### 最重要訂正: 2026-09-13 artifact identity

2026-09-13 08:44 JSTのofficial freeze（run `34726186753`, artifact `10308110102`）は **V1/V2 main-feed baseline** です。統合V4 artifactではありません。

これは結果評価前に確認・訂正済みです。`docs/CANDIDATE_DISCOVERY_V4_CONTRACT_20260913.md`も元から「V4 was not retroactively substituted」と明記しています。

9/13 freezeは改変せずbaseline Forwardとして評価します。9/13をV4 Forwardや`MKT_LATE07_TOP2_SUPPORT_V1`のProspective実績へ後付け算入してはいけません。

詳細: `docs/CANDIDATE_DISCOVERY_FORWARD_IDENTITY_CORRECTION_20260913.md`

### 2026-09-13 immutable baseline freeze

- Actions run: `34726186753`
- Artifact: `10308110102`
- ZIP SHA-256: `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`
- JSON SHA-256: `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`
- scheduled/evaluable: 180/180
- baseline core: 6 races / 12 tickets
- legacy carryover: 2 races / 2 tickets
- total: 8 races / 14 tickets

結果評価はこのexact artifactだけを使い、結果後の再生成・追加・変更は禁止です。

## CURRENT — True V4 Stage 1

Frozen V4 contract:

- TOP6 races/day × TOP2 trifecta tickets/race
- Course coefficient `0.50`, missing lane neutral
- Opponent Pressure `adj_win - base_win` coefficient `1.0`, first-place only
- Motor2 beta `0.06`, position weights `1.0 / 0.6 / 0.3`
- four structural metrics equal-weight daily ranking
- EV gateなし
- absolute odds min/max gateなし
- legacy S01-S05 carryoverは比較用に保持
- `purchase_action=false`

Pure contract:
- `research/candidate_discovery_v4_contract.py`
- `tests/test_candidate_discovery_v4_contract.py`

Integrated read-only generator:
- `.github/scripts/candidate_discovery_v4_main_feed_pg.py`

このrunnerはrace card / exact-date Course / timing-clean Opponent Pressure v2 / Motor2 / legacy carryoverだけを読み、結果・払戻・historical odds・realtime marketを読まず、DB write/LINE/BUY/Production変更を行いません。

**True V4 Forward evidenceは、結果前にこのV4 chainからimmutable artifactを実際にfreezeできた日だけ数えます。** 取り損ねた日はunavailableとして後付け再構築しません。

## CURRENT — Stage 2 / market corroboration

Hypothesis: `MKT_LATE07_TOP2_SUPPORT_V1`

- hypothesis start: 2026-09-14 JST
- late window: 0.0..7.0 minutes before deadline
- support: frozen V4 trifecta TOP1 in market trifecta TOP2
- marketはStage-1候補を削除しない
- TOP3/TOP4、EV、odds-band、venue/race/tier carveout、時間窓の途中変更禁止
- exact V4 milestones: 30 / 50 / 100 supported evaluated cases
- 9/13 wiring-only annotationはProspective count 0
- exacta/trioはhistorical proxy diagnosticであり、V4 Forwardへ後付けしない

関連:
- `docs/CANDIDATE_DISCOVERY_MARKET_CORROBORATION_FORWARD_20260914.md`
- `docs/CANDIDATE_DISCOVERY_MARKET_FORWARD_EVAL_CONTRACT_20260913.md`
- `research/candidate_discovery_market_annotation_contract.py`
- `research/candidate_discovery_market_forward_annotate_pg.py`
- `research/candidate_discovery_market_forward_metrics.py`
- `research/candidate_discovery_forward_stability_metrics.py`

Historical late-window proxyは小標本ながら:
- trifecta TOP2 support: n=34, ROI 107.941%, +270 JPY, max losing streak 15, max DD 1,500 JPY
- trio TOP2 support: n=47, ROI 109.149%, +430 JPY, max losing streak 7, max DD 870 JPY
- exacta TOP2 support: negative

proxyはProduction promotion根拠ではありません。

## CURRENT — Historical conclusions

- V1: ROI ~66–71%; broad feedとして候補量は出るがbuy ruleではない
- V2: small formationでhit rate ~16–24%だがROI <100%
- V3: ~8 candidates/day, ROI ~63.7%
- long predeclared tier × bet-type grid: ROI>100% cellなし
- 30-day A+B × trio TOP1 ~102%はlong 1,733 racesでROI 83.012%, -29,440 JPYへ低下。採用しない
- generic market agreementはprofitability solutionではない
- 結果を見た後のtier/券種/点数/時間窓retuneは禁止

## CURRENT — Railway / capacity

- `postgres-recovery`はread-only監査時SUCCESS
- 5GB volume; 直近24h diskは約4.125GB current / 約4.186GB max
- 7日summaryはcurrent約4.125GB / min約3.989GB / max約4.212GB
- `v2_odds_trifecta`は大容量だが研究/backtest価値があり単純削除しない
- DELETE/VACUUM/VACUUM FULLは未承認
- `cron-opponent-pressure-v2-runner`のFAILED表示は9/10の旧start-command build failure。実scheduled path `cron-opponent-pressure-v2-live`は9/13朝に180/180でPASS_WRITE。設定変更はしていない

## HOLD — 明示承認まで実施しない

- Production反映を伴うPR merge
- Railway Production Variables / Cron / service / volume変更
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Productionモデル・係数・閾値・候補判定変更
- LINE実送信に関わる変更
- Production Forward persistence新規変更
- 自動購入
- 有料データ契約
- 外部問い合わせ送信

安全なread-only GitHub/Railway/DB監査、Candidate Discovery研究、過去backtest、Forward評価、Draft PR、CI、Artifact確認、docs整理、Production非影響研究コードは確認なしで継続可です。

## NEXT

1. PR #351 latest head / Actionsを再取得。古いfailureを現障害と決めつけない。
2. 2026-09-13 nightly result import後、official baseline freeze `34726186753` / `10308110102`をexact artifactのまま評価する。**V4実績として数えない。**
3. 2026-09-14以降、true V4 integrated artifactを結果前にfreezeできた日だけV4 Prospectiveへ積む。取り損ねた日はunavailable。
4. 同じpre-result V4 artifactへ0..7m market TOP2 tagを付け、`MKT_LATE07_TOP2_SUPPORT_V1`を30/50/100件まで固定条件で蓄積する。
5. V4 core / legacy carryover / total feedについて、candidate volume、hit rate、ROI、profit、max losing streak、max DD、day/month stability、single/top3-hit dependency、legacy containmentを比較する。
6. 十分なForward証拠が得られるまでProduction promotionしない。実promotionは別途明示承認。

## Safety reminder

- no-future-leakage
- pre-result artifactを結果後に作り直さない
- market disagreementでcandidate feedを削除しない
- odds/EVで候補をほぼゼロへ戻さない
- CI/PRがgreenという理由だけでmerge/deployしない
- `purchase_action=false`
