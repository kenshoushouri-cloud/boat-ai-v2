# Live Handoff — 2026-10-07 23:21 JST — COMPACT

## Purpose / protection
- 新競艇AI開発プロジェクトNo.2。
- Production prediction = **V4 only**.
- V5/V5.1 = research only.
- Formal backtest period = **2025-07-01 onward**.
- Railway Agent/AI禁止。
- Railway cost target: **<= USD20/month, ideally <= USD15; lower is better**.
- CPU/RAM/Networkを最小化。
- purchase / LINE / stake / Production model / plan / volume resize-delete は明示承認なしで変更禁止。
- Historical research DB: `postgres-hobby-fullhistory-candidate-v4`.
- 1回に1作業。長時間runは「起動」と「結果確認」を別ターンにする。

## Token / timeout prevention — MUST
- 次チャットで最初に読むのは3ファイルだけ:
  1. `docs/HANDOFF_LATEST.md`
  2. そこが指すこのcompact handoff全文
  3. `docs/NEXT_CHAT_START_HERE.md`
- 古いhandoff / PROJECT_HISTORY / 長いworkflow / 過去chat大量参照は禁止。
- 原則1〜3 tool call/turn。
- Issue #42は最新数件だけ取得。全comment取得や古いpage横断をしない。
- Actionsの全run列挙・全serviceログ取得・polling連打は禁止。
- SHA/run/count/capacityは固定値扱いしない。次の1作業に必要なものだけlive取得。
- タイムアウト時は同一作業を重複実行せず、次ターンで状態確認。

## Historical Exhibition Time — current method
For each date:
1. `/railway historical-exhibition-reuse-plan YYYY-MM-DD YYYY-MM-DD`
2. safeなら `/railway historical-exhibition-reuse YYYY-MM-DD YYYY-MM-DD CONFIRM`
3. `/railway historical-exhibition-plan-range YYYY-MM-DD YYYY-MM-DD`
4. true residualだけ fast HTTP.
- fast前に true missing count / required blocks / estimated time を必ず表示。
- 全144〜168件HTTP再取得は禁止。
- terminal unfillableは `research/historical_exhibition_terminal_unfillable.json` に記録。

## Completed through 2026-10-05
- 10/2 complete, final target=0.
- 10/3 complete, terminal partial `20261003_18_11`.
- 10/4 complete, final target=0.
- 10/5:
  - reuse 81 races / 486 rows.
  - plan true residual 63.
  - fast completed 62; terminal partial `20261005_05_09`.
  - terminal JSON updated.
  - final plan target=0.
- Terminal JSON after 10/5 update:
  - official_partial 118
  - official_absent 71
  - verified_terminal_unfillable 23
  - total 212.

## 2026-10-06 anomaly diagnosis
- candidate-v4 reuse-plan returned **races=0**.
- candidate-v4 label-coverage confirmed 10/6 = **0 races**.
- Production daily logs confirmed 10/6 = **156 races**.
- Production exhibition logs:
  - learning_all complete6 = 149
  - final_ab complete6 = 151
  - daily union complete = 151
  - true daily residual = 5:
    - `20261006_02_05`
    - `20261006_08_01`
    - `20261006_12_05`
    - `20261006_14_02`
    - `20261006_20_11`
- Therefore 10/6 failure is **not official-data absence**; candidate-v4 is missing the 10/6 base date entirely.

## Minimal sync design added
Workflow:
`.github/workflows/railway-hobby-v4-final-delta-sync.yml`

Added read-only command:
`/railway production-candidate-v4-date-sync-plan YYYY-MM-DD`

Plan checks only:
- Production source service `Postgres-EKp2`
- candidate-v4 target
- `v2_races`
- `v2_realtime_exhibition_snapshots`
- labels `learning_all` / `final_ab`
- schema fingerprints
- source date exists
- target date empty
- HTTP=0
- source write=0
- candidate write=0
- result/odds/payout read=0
- Production/LINE/buy change=0.

The plan-only workflow addition was committed earlier; **do not rely on stored SHA; live main only if needed**.

## Current pending operation
Issue #42 command already posted:
`/railway production-candidate-v4-date-sync-plan 2026-10-06`

Command comment id observed: `6040693286`.

At handoff time, **bot result had not yet been observed**.
Do **NOT** post the command again.

## Next ONE task
**Only fetch the newest Issue #42 comments needed to see the bot result for command id 6040693286.**

Then:
- if `DATE_SYNC_PLAN_RESULT=READY`, report source races / exhibition rows / complete counts / schema match / target races, and STOP.
- if BLOCKED/FAIL, report exact gate and STOP.
- do not perform sync write in the same turn.

## Important context
- Candidate DB size was recently reported around 4.2 GB, but capacity is live data; do not treat that as fixed.
- Do not bulk-read db-size output unless capacity is the current task.
- Production source must remain read-only for this date-sync work.
- Any actual Production→candidate-v4 write must be separately gated and limited to the explicitly approved minimal tables/date.

`COMPACT_ONLY / ONE_TASK_ONLY / NO_RERUN_PENDING_COMMAND / SOURCE_READ_ONLY / MINIMAL_DATE_SYNC / NO_RESULT_ODDS_PAYOUT / COST_MINIMIZE`
