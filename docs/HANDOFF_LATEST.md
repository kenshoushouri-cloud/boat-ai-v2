# V5 current compact pointer — 2026-10-26 22:02 JST
Active handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Design: `docs/V5_DIRECT_PRIMARY_LEGACY_FALLBACK_PARALLEL_DESIGN_20261026.md`
New chat: read this + active handoff + `docs/NEXT_CHAT_START_HERE.md`; do not bulk-load old handoffs.

Decision: V5 PRIMARY direct official collection to physical `boat_data_stage.*`, existing legacy SECONDARY only to distinct `public.v2_*` until proved safe. No duplicate writers, blind backfill, BUY, collector stop or cutover. Current V5 realtime forward script still invokes legacy v21; no independent V5 stage live writer installed. Railway cloud unused; ConoHa local database is named `railway`.

**Confirmed 2026-10-26 ConoHa tests:**
- 22:00 JST `v5_direct_primary_stage_routes_offline_test_20261026.sh` ran 10/10 PASS; route-contract unit tests only, NOT live collector readiness.
- 22:02 JST 5s READ ONLY `v5_today_entries_source_vs_stage_readonly_20261026.sql`: stage entries missing for 144 race IDs; old physical source had 6 valid entries for each (144/144; 864 rows), 0 absent and 0 incomplete. Current-state **source→stage lag** only. Not proof entries existed before cutoff or that V5 made predictions.

**Next ONE task (evening):** small READ ONLY ConoHa systemd collector/service/timer inventory; identify actual writer ownership and destinations before native V5 code/writer/reader isolation changes. Do not manually sync or activate V5 direct writer.
**Scheduled checkpoint:** existing one-time `boat-v5-stage11-delta-20261027-recovery.timer` at 2026-10-27 03:05 JST unchanged. After run, verify journal first, then monthly stage QA `2026-10 1`; no success claim in advance.
Retain existing collectors incl. odds/exhibition/weather and historical records, BUY OFF, backup work deferred; cost discipline. Main handoff carries detailed constraints.
