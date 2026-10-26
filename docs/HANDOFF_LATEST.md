# V5 current compact pointer — 2026-10-27 00:15 JST
Active detailed handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Design: `docs/V5_DIRECT_PRIMARY_LEGACY_FALLBACK_PARALLEL_DESIGN_20261026.md`
Next chat: read ONLY this pointer, active compact handoff, and `docs/NEXT_CHAT_START_HERE.md`. Do not bulk-read past handoffs.

## Decision (user priority)
V5 must collect OFFICIAL data directly, write ONLY physical common `boat_data_stage.*` (primary). Existing legacy collector temporarily continues ONLY `public.v2_*` (secondary) until validated V5. No same-table dual writers. User proposes finishing V5 realtime and restoring Oct26 gaps to eliminate overnight old→stage sync. **Only the copy/sync can be retired upon full parity; postrace results catchup still needed.** BUY OFF. ConoHa local PG `railway`, Railway cloud unused.

## Verified evidence
- Oct26 22:00 V5 fixed stage routes 10/10 PASS offline.
- 22:02 144 Oct26 stage entry-races missing vs old physical source complete 144/144 (864 rows). Current-state availability, NOT proof of before-deadline capture.
- 22:24 all 13 old/stage pairs are distinct physical tables; six stage snapshot indexes reported KEY_OK; canonical `boat_data.*` sampled names are legacy VIEWs, NOT writable physical targets.
- 23:31 V5 native core offline tests 14/14 PASS. 23:44 direct official discovery: 14 next-day venues, official race `20261027_01_01` with 6 entries, capture 23:44:08, cutoff 15:22 JST, NO DB writes. 23:59 core stage-canary offline tests 11/11 PASS.
- Existing V5 forward-window STILL invokes v21 old writer to public. **No V5 production physical-stage native collector installed or running.** No live stage insert verified.

## New GitHub-only work 2026-10-27
- `v5/native_official_realtime_stage_pg.py` @ `a1f7c469516d278dd5555b4ecb46bacce3bd322c`: independent OFFICIAL racelist+beforeinfo+odds3t HTTP, reuses legacy parser FUNCTIONS only (never old fetch/collect/save/DDL), constructs six physical stage snapshot families (6 entries+6 exhibition+120 odds+1 weather+1 race condition+6 racer conditions=140). Fail closed on missing/incomplete data, >3m before deadline, stage keys, BUY ON, night delta, legacy overlap; disabled by default. **Not integrated with all-race 5-min service; no ConoHa execution or DB write proven.**
- 15 new offline tests `tests/test_v5_native_official_realtime_stage_pg.py`; ConoHa pinned tmp-only runner `deploy/conoha/v5_native_realtime_offline_test_20261027.sh` @ `317e793237eb2ea380a8fa948528e420ab4c5105`. **Not yet run.**
- Date-scoped 26 missing-entries INSERT-only recovery `deploy/conoha/v5_oct26_entries_targeted_recovery_20261027.py` @ `cd85c71dde624008ca5adacdd5f0b39db7b01ac6`; guarded script `deploy/conoha/v5_oct26_entries_recovery_guarded_20261027.sh` @ `3f6370cf05605bbe18cc5b39cbbb293e8acea306` (preview default; `V5_APPLY_OCT26_REPAIR=YES` requires approval explicitly from operator), scoped <=144 missing Oct26 races; six lanes, only missing full races, all columns/physical checks, atomic INSERT only, no deletes/overwrites, stage advisory lock and HOLD 03:00-05:59. **Not run on ConoHa. Does NOT restore other 11 table families or certify as-of time.**

## Next ONE task
ConoHa run 15 new V5 independent realtime offline tests, review PASS/FAIL. Then guarded Oct26 entries preview/apply can proceed, if schema & source are verified. Protect postrace catchup 00:45 and stage11 scheduled 03:05 recovery until all-family parity (including results/odds/exhibition/weather) is proven; 26 entries alone never authorizes cancellation. After 06:00 inspect journal and October QA with existing read-only checker `deploy/conoha/v5_after_stage11_20261027_readonly_checkpoint.sh` @ `99fa89a46cdd7657b6c50e9187948c578c526408`.

Remaining before "FULLY LIVE": native full-day race/entry scheduler, five-minute independent native realtime scheduler, postrace results stage writer, deployment/systemd rollout, production capture proof, stage reader parity, restore/rollback proof, conditional old sync decommission. Do not set old `v5_data.raw_*` route flags, prematurely stop legacy, change BUY, or start duplicate V5 physical writers. Costs CPU/RAM/WAL minimum.
