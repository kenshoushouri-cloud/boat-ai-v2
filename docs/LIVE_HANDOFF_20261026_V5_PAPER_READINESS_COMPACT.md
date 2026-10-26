# V5 compact handoff — 2026-10-26 17:45 JST

## Priority / user's latest decisions
- V5 **早期安定稼働＋実データ予測/前向きバックテスト** を最優先。ConoHaとGitHubを使う。Railwayには現行データなし（ユーザー確認）・Railway接続は不要。
- **Google Drive再認証・新規バックアップ構築・Drive重複整理・ConoHaの旧dump削除は、V5運用が落ち着くまで保留**。既存バックアップを削除しない。ConoHa rootは10/26 16:58時点99G中32G使用/63G空き。
- BUY=OFF、本番writer cutover=NO_GO、V4旧原本と13 live VIEW/collectorの継続、取り返せない展示/odds/気象の事前captureを保護。OS再起動・収集中のコード置換・重複collector実行禁止。Railway Agent/AI禁止、低コスト優先。

## Verified current physical/data state
- ConoHa DB名 `railway` は**DBローカル名称**。Railwayサービス稼働の証拠ではない。
- 旧原本`public.v2_*`、その参照先の`boat_data.*` 13 VIEW、V5 stage`boat_data_stage.*` 13物理表。正式live writer切替0/13、常時CDCなし。
- 10/26 07:45:54 morning finished 288/288（success144, no_race144, failed0）。no_raceは不開催144の証明ではない。丸亀(15)の`ENTRY_STATS_PARSE_FAILED`による艇別13 stats一括NULL疑いは未解決。
- 10/26 10:12 stage `races` の限定差分同期成功、全期間74208=74208行。10:18 当日144/144 race IDs一致。**残る11種類は未同期**。
- ユーザー実機10/26 17:17: `boat-v5-stage11-delta-20261027-recovery.timer` は`ActiveState=active`、`NextElapseUSecRealtime=Tue 2026-10-27 03:05:00 JST`。当該timerは予定どおり予約済み、**再予約・変更・サーバー再起動しない**。17:40に翌日03:00からのjournalが`-- No entries --`なのは実行前なので正常。結果はまだ未確認。
- ConoHa 5分shadow監視は少なくとも10/26朝起動実績あり、LIVE VIEW read-only/sampled input only。**V5実DB特徴量adapter・実測asof検証・3連単本番予測/ROI・自動購入は未達**。

## Prediction/data-quality policy & new GitHub-only work
- 13項目全必須の一律除外は不採用。正規の公式未集計は高評価選手の強さを減点せず、根拠付きunknownとする。NULLだけを根拠に公式未集計とみなさない。parser失敗/原因不明NULL/6艇ID不一致はHOLD。ゼロ埋め、後日情報による過去予測の再構成を禁止。
- Existing pure `v5/entry_quality_policy.py`, `v5/offline_mainline_inference.py`; both not deployed for real live prediction.
- 10/26 GitHubに **`v5/offline_paper_quality_bridge.py`** (commit `327217e29cd4f77da53ff3d71a80de24464e8812`) と **`tests/test_v5_offline_paper_quality_bridge.py`** (commit `191c099351fbe4f19e87db808b30217373bc7b7d`) を追加。synthetic input only / fail-closed: completeなら合成1着確率演算のみ、official-unreportedはmissing-awareモデル未検証HOLD、unknown/parse failure/ID不整合もHOLD、全経路BUY=OFF。**GitHub commit確認済、ConoHaでsynthetic-only 18件ALL PASS（10/26 18:06スクリーンショット）、実モデルの収益性証明なし**。
- Backtestは2025-07以降の可能な全期間を採用し、締切前snapshot/asofの真正性・選手/モーター/気象の時期・データリークを検証してから評価。特徴量は検証前に恣意的に選別しない。

## 2026-10-26 synthetic-only test runner
- GitHub `deploy/conoha/v5_synthetic_quality_selftest_readonly_20261026.sh` (commit `37f54c4f67f64b8632281eb1c975a0cbde126ec5`) added. Fetches exactly six known Python files pinned to commit `690ab7beab6eb02e5d9b8dcddda22fb92f33fb18` into a temporary directory and runs two stdlib unittest files. It does not access PostgreSQL, systemd, collectors, or BUY; temporary files removed after completion.
- **User's ConoHa stdout screenshot 2026-10-26 18:06 JST confirmed**: `Ran 18 tests in 0.008s`, `OK`, `V5_SYNTHETIC_UNIT_TEST_PASS DB=NO DB_WRITES=NO COLLECTOR_UNTOUCHED=YES BUY=OFF`. This proves isolated synthetic test gates only; not actual model, real-data quality or ROI. No live deployment.

## 2026-10-26 18:11 read-only VIEW schema inspection (user screenshot)
- `information_schema.columns` on ConoHa `railway` for `boat_data.entries` and `boat_data.races` showed **metadata only**; terminal output used pager and paused at `:` before all races columns were visible. No row data and no DB write.
- `entries` has `race_id text`, `lane integer`, **both** `racer_no text` and `racer_number integer` (identity cross-check needed), 13 stat names used by `v5.entry_quality_policy.STATS` including `motor_no text`, `boat_no text` (type-safe conversion mandatory), `recent_form jsonb`, `raw jsonb`, `created_at`/`updated_at` timestamptz. Those timestamps must **never** be treated as immutable original first observation or deadline-before proof.
- Visible beginning of `races`: `race_id text`, `race_date date`, `venue_code text`, `venue_name text`, `race_no integer`, `race_title text`. Rest of columns **not yet seen**. No claim of a cutoff field until full read-only metadata result.
- 10/26 18:15追加のユーザースクリーンショット: `boat_data.races`は16列。`deadline_at timestamptz`, `race_date date`, `status text`, `data_quality_score integer`, `missing_count integer`, `deadline_time text`; `created_at` / `updated_at`は初観測証明に使えない。SQLはmetadataのみ・DB変更なし。

## GitHub-only real VIEW shape adapter, 10/26 evening
- `v5/offline_entry_view_adapter.py` (commit `e05a821a758122adfd2a985e04fcd7d9e2af8df8`): pure input mappings->strict six-entry diagnostic, catches mismatched `racer_no text` and `racer_number int`, parses motor/boat IDs only when digit text, requires timezone-aware JST deadline and same-day race_id, rejects missing/unknown numbers, **all paths hard-HOLD for real selection/forward/BUY**. No DB read/write or feature scoring, no first-seen evidence claim.
- `tests/test_v5_offline_entry_view_adapter.py` (commit `ad8e8a1b3297ae0392929b69bef83fd50f4fe476`): 13 synthetic cases for malformed values, identity, cutoff/timezones, invalid/missing, and immutable HOLD flags. **2026-10-26 18:23 JST ConoHa screenshot confirmed 13/13 PASS**: `Ran 13 tests in 0.006s`, `OK`, `V5_VIEW_ADAPTER_TEST_PASS DB=NO DB_WRITES=NO LIVE_COLLECTOR=UNTOUCHED BUY=OFF` (synthetic-only, no actual DB rows or model scoring).
- `deploy/conoha/v5_offline_view_adapter_selftest_readonly_20261026.sh` (commit `547b83fd7e6dd7ad793f2754e72fe6a29f4bb6c5`): pinned 3-file temp-folder unittest test-runner. No DB, service, timers or BUY.

## 2026-10-26 18:28 JST — actual VIEW diagnostic (user terminal screenshot)
- READ ONLY + 5s timeout on `boat_data.entries` limited to `race_id='20261026_10_01'` executed and rolled back successfully. Output: `entry_rows=6 | lanes=6 | racers=6 | identity_holds=6 | basic_missing_rows=0` (basic missing only checks `avg_st, motor_no, boat_no`, not all 13 stats). No writes or timer changes.
- IMPORTANT: all six rows fail `racer_no text` vs `racer_number integer` canonical identity comparison, but the reason is **unproven**; may be schema semantics or formatting, not necessarily data corruption. DO NOT change data, loosen guard or declare six-player identity valid. Existing pure adapter must HOLD until verified.
- The first Bash `-c` query with `!~` failed history expansion; the corrected single-quoted HEREDOC SQL succeeded.

## 2026-10-26 18:35 JST — six actual racer identities (user screenshot)
- Read-only six rows for `race_id=20261026_10_01`: 1=4189,2=4872,3=3441,4=4442,5=4113,6=4273 in `racer_number` (integer); legacy `racer_no` displayed blank in all rows; `racer_name` also displayed blank. **psql blank display alone cannot distinguish SQL NULL from empty string.** Data not corrupted on this evidence; six distinct canonical candidates exist but independent source provenance and deadline-asof still unverified. Do not fill `racer_name` with guessed names.
- GitHub-only update `v5/offline_entry_view_adapter.py` commit `830563fcbafa5534d89e5433cb31418a5e7e7856`: treat NULL or empty legacy alias as absent, keep canonical `racer_number` int shape validation and all real scoring/forward/BUY hard HOLD, track `legacy_identity_absent_lanes`. Malformed present legacy values, mismatching numbers, invalid integer, duplicate racer/lanes remain HOLD.
- `tests/test_v5_offline_entry_view_adapter.py` commit `61d5d2a4918b9ea10526af87dd817f92817beb48`: added four tests (17 tests total) for sparse legacy, malformed/missing canonical, conflicts. Existing historic 13/13 PASS applies **only to old code**, new 17 tests NOT RUN yet.
- Pinned `deploy/conoha/v5_offline_view_adapter_selftest_readonly_20261026.sh` updated commit `3e234cf0415f89d5d7d2ffbdae4ff9060d640309`; fetches three Python files from immutable test commit and runs pure synthetic 17-case unittest in /tmp. Never deploy into running collector/DB.

## 2026-10-26 18:44 JST — updated synthetic unit result
- User's ConoHa terminal screenshot explicitly shows `Ran 17 tests in 0.010s`, `OK`, `V5_VIEW_ADAPTER_SPARSE_IDENTITY_TEST_PASS DB=NO DB_WRITES=NO LIVE_COLLECTOR=UNTOUCHED BUY=OFF`. Revised adapter's 17/17 tests confirmed, old 13-case run superseded; other 18 synthetic quality cases passed separately = **35 currently checked tests** (not 48 distinct).
- No real race-model scoring/profit backtest, no immutable original as-of evidence, no real-data BUY authorization proven; old legacy `racer_no` shown blank (NULL vs empty string not yet distinguished), `racer_number` populated for all six.
- No production DB/collector/timer changes associated with these synthetic tests.

## Next ONE task
- In a **READ ONLY** transaction limited to `race_id='20261026_10_01'` and 5-second statement_timeout, inspect 6 rows' `racer_no` actual SQL NULL vs empty and per-lane missing field names over all 13 statistical columns; don't conflate previously checked basic 3 fields with full completeness.
- 2026-10-27 03:05 JST one-time stage11 sync still untouched; afterward check service journal read-only. No V5 live cutover, no BUY, no backup work, no Railway access.
