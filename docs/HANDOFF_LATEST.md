# V5 current compact pointer — 2026-10-26 22:24 JST
Active handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Design: `docs/V5_DIRECT_PRIMARY_LEGACY_FALLBACK_PARALLEL_DESIGN_20261026.md`
New chat: read this + active handoff + `docs/NEXT_CHAT_START_HERE.md`; avoid old handoff bulk.

User urgent target: V5 official PRIMARY writes ONLY to physical `boat_data_stage.*`; independent legacy SECONDARY writes only `public.v2_*`, temporary until reliability + rollback. Existing V5 forward wrapper still calls v21; legacy-only active writer by default. **NO PRODUCTION SWITCH YET**, BUY OFF; preserve old acquisition incl. odds/exhibition/weather. Railway cloud unused; ConoHa local DB name `railway`.

**ConoHa verified 2026-10-26**:
- 22:00 offline direct stage route contracts 10/10 PASS.
- 22:02 source vs stage entry discrepancy: 144 missing stage races, all 144 have six valid source rows in public (864); *current-state sync lag only*, no cutoff-time proof.
- 22:10 six scheduled timers confirmed. Stage11 one-time sync still scheduled 10/27 03:05.
- 22:13 static writer audit confirms V5 wrapper invokes v21 collector, public writer paths/DDL hints, routing uncertified.
- 22:24 physical catalog preflight on ConoHa: 13 source-stage physical pairs, snapshot unique keys reported KEY_OK, no missing legacy columns to stage in shown results, canonical `boat_data.*` sampled names are VIEW; ROLLBACK/no changes. This does NOT prove writes.

**New GitHub-only code:** `v5/native_stage_race_entries_pg.py` @ `dcd04325f594d56c4226ce7abbb12260f803a9b8`: independent official HTTP (shares tested legacy *parser functions only*), single-race stage physical `races`+ `entries` INSERT-only writer, default preview, gated apply; 14 tests ran at 23:14 JST: 11 PASS, 3 ERROR from premature psycopg import under system Python. Fix is committed; retest pending. Stage delta write collision guard blocks live apply before 10/27 06:00, requires completed journal verification. No direct realtime odds/exhibition/weather V5 code yet. No installed V5 native service/timer.

**Next ONE task:** ConoHa rerun corrected offline runner `deploy/conoha/v5_native_stage_core_offline_test_20261026.sh` @ commit `a07af635b6598768438cfe1c0d9fb3671017f6cb`; fixed native source at `431655ae77ab592b0a4aecba781a1b3f56ad61e4`. Check 14/14, do not claim pass in advance. Then target read-only future-race official parser preview and proceed with separate native snapshot collector before safely switching live V5 read/write and leaving legacy on public.

Never prematurely cancel 03:05 stage sync, stop legacy, enable old `v5_data.raw_*` route flags, or BUY. CPU/RAM/WAL cost discipline; backups deferred, no deletion.
