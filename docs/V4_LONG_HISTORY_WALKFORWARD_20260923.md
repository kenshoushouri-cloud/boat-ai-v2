# V4 long historical walk-forward — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / PRE_RESULT_RANKING / RESULT_AFTER_FREEZE_ONLY / NO_PRODUCTION_CHANGE`

## Purpose

Extend the existing fixed-window V4 replay backward to **2025-07-01** and forward
through **2026-09-22** without changing Production behavior.

This run is for two questions only:

1. whether the current V4 race-selection ordering has stable long-history signal;
2. whether the formal 2-point policy versus a shadow 3rd ticket has consistent
   historical economics.

It is not a Production retune.

## Timing boundary

The replay preserves the same safety boundary as PR #376:

- build the V4 distribution only from race-card information;
- Course requires exact-date official snapshots created before 08:15 JST and deadline;
- Opponent v2 requires train_end before race date and timestamps before cutoff/deadline;
- Motor2 comes from the race-specific entry row;
- select the exact daily six and freeze Top5 before reading result/payout;
- if one selected result is not exact official, the entire day is unevaluable;
- no five-race shrink, replacement, later-date substitution, result-aware rerank, or odds/EV selection.

Missing historical Course/Opponent/Motor support remains fail-neutral exactly as
the current V4 contract, and coverage is reported explicitly by the replay.

## Long-window outputs

The sanitized artifact contains:

- overall Top1..Top5 economics;
- month-by-month economics;
- ten chronological blocks;
- evaluated/unevaluable day audit;
- feature-availability coverage;
- all pre-result frozen daily ranks / race scores / Top5 rankings plus official outcome.

A second pure/offline diagnostic reports:

- formal 2-point ROI by daily rank 1..6;
- rank1-3 versus rank4-6 formal 2-point economics;
- deterministic day-cluster bootstrap uncertainty;
- shadow third-ticket marginal economics overall and by month;
- largest-hit concentration for the third ticket.

## Interpretation guard

The long history may generate hypotheses, but it does not authorize:

- candidate-count changes;
- race_score gates;
- coefficient/temperature/threshold changes;
- reranking;
- Production point-count changes;
- purchase action.

Any such change remains a separate preregistered Forward/Production approval gate.

`READ_ONLY_TRANSACTION / NO_RESULT_BEFORE_FREEZE / NO_ODDS_SELECTION / NO_RETUNE / SIX_RACES_CONTROL / FORMAL_2_POINTS_CONTROL / THIRD_POINT_SHADOW / PURCHASE_FALSE`


## Approved read-only execution routes

The workflow fails closed unless one of these two routes is available:

1. dedicated GitHub secret `V4_BACKTEST_DATABASE_URL`; or
2. existing project-scoped `RAILWAY_TOKEN` used only for `railway run`.

The second route uses Railway CLI's documented local execution behavior:

`railway run --project <project> --environment production --service backtest-analysis <command>`

Railway CLI fetches the selected service environment and injects it only into
the local child process. The workflow does **not** call `railway variable list`,
does not write a variable-list JSON file, does not print the token or
`DATABASE_URL`, and does not deploy/redeploy/restart/change Railway state.

The Python replay still opens PostgreSQL with `SET TRANSACTION READ ONLY` and
rolls back before exit.
