# V5 current compact pointer — 2026-10-27 00:31 JST
Active detailed handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Next chat should read only this pointer + active compact handoff + `docs/NEXT_CHAT_START_HERE.md`; do not bulk-read old handoffs.

## User-approved target
- **V5 PRIMARY** independent BOAT RACE official acquisition to physical `boat_data_stage.*`. Old system is temporary fallback with writes to `public.v2_*` only.
- **Once V5 truly running end-to-end**, stop OLD collector/services, preserve rollback unit definitions briefly, and decommission duplicate old→stage nightly sync. **Only after full historic/ongoing data parity, stage-only V5 backtest/read verification and an independently restorable backup may original old tables be deleted.** Do not maintain unneeded old system indefinitely; cost savings and move to V5 backtesting are user's priority.
- BUY OFF; Railway cloud unused; ConoHa local PostgreSQL database is `railway`.

## Verified evidence (screenshots 2026-10-26/27)
- 22:00 V5 fixed stage offline 10/10 PASS; physical 13 old→stage table pairs distinct; canonical `boat_data.*` is currently VIEWs, not stage physical write destination.
- Oct26 old-source → stage entry gap 144 races/864 rows. **2026-10-27 00:23 JST repaired in stage via INSERT-only COMMITTED 864 rows**, old source untouched.
- 2026-10-26 23:44 JST official 2026-10-27 index 14 venues + Omura 1R 6 valid entrants direct HTTPS; no legacy database. Native core tests 14/14, official-index 9/9, stage core 11/11 PASS offline.
- 2026-10-27 00:23 JST new V5 native realtime 6-family offline tests 15/15 PASS; **NOT proof of native stage live writer or scheduled production operation.**
- **2026-10-27 00:31 JST six-family read-only Oct26 audit:** all 6 families stage 0 vs legacy source: entry snapshots 1,800 / 144 races; exhibition 816 / 136; odds 35,160 / 142; weather 300 / 144; race condition 300 / 144; racer condition 1,800 / 144. **Total 40,176 source rows, 0 stage rows**. Source snapshot_at labels all earlier than source race deadline but this is NOT independent capture proof. Old data NOT fully replicated, so do not delete or stop old now.

## Code created (not production-deployed)
- Native direct official 1R core to stage races/entries gated single canary `v5/native_stage_race_entries_pg.py` (offline tests PASS); direct official index orchestration `v5/native_official_stage_canary.py`.
- Native direct official `beforeinfo` + `odds3t` to stage 6-family snapshots `v5/native_official_realtime_stage_pg.py` @ `09dbb8658f1d7ff6d1065cc0386737863b332219`. Fail closed on missing odds 120/exhibition six/weather, 3m cutoff, BUY, staged delta conflicts. Only tests run; **no V5 native realtime systemd service/timer yet**.
- Source→stage real-time exact **Oct26 one-day** read-only parity: `deploy/conoha/v5_oct26_realtime_exact_parity_readonly_20261027.py` @ `f7479904dbcb6de74874217cf9b56241b853d2a3`, not run. Uses bounded indexed key/JSON row compare, **not whole-history deletion authorization**.
- Production native status read-only: `deploy/conoha/v5_native_cutover_status_readonly_20261027.sh` @ `3d85399998ecadce51182d376d4f9c3599e58ac2`, not run.
- Existing one-time stage11 old→stage 11-family delta **scheduled 2026-10-27 03:05 JST**, and 00:45 result catchup. Keep pending unless truly replaced; stage reconciliation can UPDATE/DELETE stage-only rows. Existing `boat-v5-forward-window.service` invokes v21 legacy collector (`--max-races 2`, five minute 07:00–23:55), not an independent V5 writer.
- Post-03:05 journal + monthly stage read-only checker `deploy/conoha/v5_after_stage11_20261027_readonly_checkpoint.sh` @ `99fa89a46cdd7657b6c50e9187948c578c526408`.

**2026-10-27 00:43 JST user terminal:** ran `deploy/conoha/v5_post_sync_parity_checkpoint_20261027.sh` before intended start; exact output `HOLD_CHECKPOINT_ONLY_AFTER_20261027_0600_JST`. This is a correct preflight hold, **NO journal/QA/parity queries executed**, no writes/stop/deletes. Rerun same command AFTER 06:00 JST; do not treat this HOLD as stage sync failure. Existing 00:45 result catchup and 03:05 stage delta were still upcoming at screenshot time.

## Next ONE task
After the existing 03:05 one-time stage delta completes, run **one paste AFTER 2026-10-27 06:00 JST**: `deploy/conoha/v5_post_sync_parity_checkpoint_20261027.sh` @ `938be58502357cae438eaeeb59902b87b4b8e755` to check stage journal/Oct race-entry QA and **indexed exact six-family 2026-10-26 snapshot key+JSON parity**. This determines whether 40,176 source snapshot rows were fully copied. Read-only; cannot itself authorize historic old-data deletion. Do NOT run concurrent extra sync before scheduled timer.
In parallel implement + validate V5-native all-races morning/day/night core collector, predeadline bounded multi-venue realtime scheduler with shared provider throttle/isolated staging, native result catchup, stage-only V5 forecast/backtest reader. Confirm stable V5 actual writes/capture/evaluation + backup, then stop old services/timers, test rollback; finally delete old data only after full historical + current content parity verified. Never turn on BUY or erase provenance/historic original data prematurely.

**2026-10-27 00:46 JST operator request:** user believes gaps already filled and asks to cease the overnight sync and use normal daily collection schedule only. Important correction: the committed 864 rows covered **Oct26 core entries only**; as of 00:31, 6 realtime families had **40,176 source rows and ZERO stage rows**. The 03:05 stage11 recovery is a **one-time transient systemd timer**, NOT an ongoing nightly recurring cron. Screenshot 00:46 repeats the after-06:00 guard HOLD; it did not run parity nor prove stage data present. **Do not cancel the one-time recovery or stop old collectors**, and do not claim V5 independently live: its current 5-min timer still invokes v21 legacy writer. Retire the one-time sync after execution/parity, and do not install any new recurring copy job. The target steady-state should run only self-contained V5 official core/realtime/result schedules, with old data deletion only after full content parity and backup.
