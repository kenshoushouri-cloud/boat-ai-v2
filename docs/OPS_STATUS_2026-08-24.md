# Operational status — 2026-08-24 JST

This note records the live operational findings from 2026-08-24. GitHub remains the code source of truth and Railway PostgreSQL remains the production-data source of truth.

## Bao Forward collection

Current reviewed design:
- market early: 20–30 minutes before deadline;
- exhibition mid: 8–15 minutes before deadline;
- market late: 0–7 minutes before deadline;
- exact 120-ticket gate for market snapshots;
- six-lane / six-time / rank-permutation completeness for dedicated exhibition snapshots;
- first valid capture is frozen;
- post-fetch phase/window drift is rejected;
- collectors write only isolated Bao Shadow tables.

GitHub scheduled events were observed arriving much less frequently than the nominal five-minute cron. PR #152 therefore changed a scheduled runner into a 2-minute capture loop, and PR #153 extended that loop from 40 to 60 minutes to bridge observed scheduler gaps. Scheduled/manual capture remains serialized and PR validation uses a separate concurrency group.

Verified live behavior:
- the 40-minute loop completed 18 iterations successfully;
- transient official-site timeouts and 119-ticket partial states were rejected and retried on later iterations;
- no exact/completeness gate was relaxed;
- genuine missed opportunities remain visible and are not reconstructed.

Known missed opportunities since tracking began:
- market early: `20260824_21_02`;
- paired market late: `20260824_18_03`, `20260824_21_04`.

At the 10:19 JST combined Shadow smoke:
- `20260824_18_05` late saved at 5.46 minutes before deadline with exact 120 tickets;
- `20260824_21_06` early saved at 29.33 minutes before deadline with exact 120 tickets;
- paired market races increased to 22.

Dedicated exhibition evidence:
- `20260824_18_05` was saved at 8.27 minutes before deadline with six lanes, six positive times and a complete rank permutation;
- the same smoke increased the safe exhibition-ready paired sample to 15.

Latest read-only paired audit at that point:
- market/Motor2-ready: 22;
- Motor2 improved distance to late market: 13/22;
- average Motor2 CE delta: `-0.002501`;
- dedicated exhibition-ready: 15;
- exhibition improved over Motor2 on late-market proxy: 14/15;
- average additional exhibition CE delta: `-0.007991`;
- realized-result Motor2 subset: 13, improved 4/13, average result logloss delta Motor2 vs early `+0.015048`;
- realized-result exhibition subset: 7, improved 3/7, average joint-vs-Motor2 result logloss delta `-0.000716`.

The Forward gates remain at 30 Motor2-ready pairs and separately 30 dedicated exhibition-ready pairs. Reaching 30 does not automatically promote anything. Realized-result evidence and formal manual review remain required before any Production change.

## Current-day production-data health

PR #154 added owner-only read-only command `/railway today-health`; PR #155 added exact incomplete-race samples.

10:16 JST read-only health snapshot:
- `v2_races`: 144 / deadline-ready 144;
- `v2_race_entries`: 864 rows / all 144 races have six lanes;
- `v2_odds_trifecta`: 8,991 rows across 76 races / 51 races dynamically complete;
- `v2_results`: 0 races at this daytime snapshot.

Window coverage at the same snapshot:
- morning: 12 races / entries 12 complete / base odds 5 complete;
- day: 67 races / entries 67 complete / base odds 49 complete;
- night: 70 races / entries 70 complete / base odds 2 complete.

Morning base-odds incomplete races were:
- `20260824_18_01@08:40`
- `20260824_21_02@08:58`
- `20260824_18_02@09:06`
- `20260824_10_02@09:14`
- `20260824_21_03@09:24`
- `20260824_18_03@09:32`
- `20260824_10_03@09:40`

The entries are complete; the issue is base trifecta-odds freshness/completeness.

Code review of `run_odds_window_pg.py` confirms that each Railway window invocation performs an initial fetch and only two retries separated by 30 seconds. `cron-window-morning` currently starts once at 08:15 JST. Several races that remained incomplete in `v2_odds_trifecta` were later observed with exact-120 market data in the Bao 20–30 minute window. This supports the hypothesis that a single early morning invocation is too early for some official odds pages, rather than an entries/race-preparation failure.

Do not simply make `cron-window-morning` repeat yet: `v24_pre_candidate_notifier_pg.py` has a daily/monthly LINE usage guard but no per-race/ticket duplicate-pre-notification guard. A repeat schedule therefore needs an idempotent PRE notification design first, then a reviewed Railway schedule change.

## Safety / next work

1. Continue collecting Bao Forward evidence without relaxing timing or completeness gates.
2. Verify the first scheduled runner that actually uses PR #153's 60-minute loop.
3. Keep genuine missed windows as missed evidence; never reconstruct them after deadline.
4. Design and review repeat-safe PRE notification deduplication before changing the morning Railway cron.
5. After repeat-safe PRE is proven, evaluate a multi-run morning schedule to refresh odds as they become officially available.
6. Do not change Production BUY/WATCH/SKIP, LINE behavior, Railway Variables/settings, model coefficients or promotion thresholds from Shadow evidence alone.
