# V5 current compact pointer — 2026-10-26 23:36 JST
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

**New GitHub-only code:** `v5/native_stage_race_entries_pg.py` @ `dcd04325f594d56c4226ce7abbb12260f803a9b8`: independent official HTTP (shares tested legacy *parser functions only*), single-race stage physical `races`+ `entries` INSERT-only writer, default preview, gated apply; ConoHa original 23:14 run had 3 psycopg import-order errors; fixed version at `431655ae77ab592b0a4aecba781a1b3f56ad61e4` PASSED 14/14 offline tests at 23:31 JST per user screenshot. No DB/official site in unit tests. Stage delta write collision guard blocks live apply before 10/27 06:00, requires completed journal verification. No direct realtime odds/exhibition/weather V5 code yet. No installed V5 native service/timer.

**23:36 JST:** user's single official-race preview stopped at `HOLD_NO_FUTURE_RACE_IN_LEGACY_METADATA_NO_HTTP_NO_WRITES`; next-day race IDs were absent from `public.v2_races`, thus ZERO official HTTP requests. No evidence official site lacks races. This was an incorrect old-data prerequisite for V5 independence.
**Next ONE task:** user run GitHub-pinned `deploy/conoha/v5_direct_official_index_preview_20261026.sh` @ `14a811a92ea3e835e58b2e4e1372debf24bbe33b`. It performs nine offline parser tests and then one official day-index request plus at most 3 single-race official racelist attempts, using `v5/native_official_index_preview.py` @ `fee96ead0c46031eb699e5058c35e75067802c7e`, no legacy PostgreSQL queries, DB writes, timers or BUY. **Tests/live preview not yet run on ConoHa.** If official venue links or racelist not available, HOLD without fallback to legacy. Proceed with independent realtime writer after proof; pending Oct27 03:05 sync remains unchanged.

Never prematurely cancel 03:05 stage sync, stop legacy, enable old `v5_data.raw_*` route flags, or BUY. CPU/RAM/WAL cost discipline; backups deferred, no deletion.
