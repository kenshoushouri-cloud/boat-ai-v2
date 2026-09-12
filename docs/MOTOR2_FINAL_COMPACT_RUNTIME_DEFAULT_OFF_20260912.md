# Motor2 FINAL compact runtime hook — default off

Date: 2026-09-12 JST
Status: Draft research implementation / not activated in Production

## Purpose

Prepare a low-risk runtime switch that can reduce future Motor2 FINAL shadow growth without changing Production prediction logic.

The current FINAL pipeline runs every 15 minutes and creates a time-qualified Motor2 snapshot key. When the same race remains inside adjacent FINAL windows, a new snapshot key creates another logical row for each saved sparse race/ticket observation.

## Runtime switch

New environment variable:

`MOTOR2_FINAL_SNAPSHOT_MODE`

Allowed values:

- `timestamped` — default; preserves current behavior exactly.
- `latest_per_race` — uses a stable `YYYYMMDD_final_latest` key so repeated writes for the same race/ticket update the existing FINAL row through the table's current unique key.

Unknown values fail closed before Motor2 FINAL collection.

## Isolation

The switch only changes the `MOTOR2_SHADOW_SNAPSHOT_KEY` passed to the existing Motor2 shadow collector. It does not change:

- realtime odds collection;
- v22 BUY/WATCH/SKIP scoring;
- selector mode;
- Racer Course or Opponent Pressure coefficients;
- N02 or exhibition shadows;
- LINE target logic;
- Forward decision persistence;
- purchase behavior.

No Railway variable is created by this PR. Therefore current Production continues to use the default `timestamped` behavior even if this Draft were reviewed.

## Production evidence

Read-only Railway inspection confirms:

- `cron-final-check` schedule: every 15 minutes during the live UTC window;
- `RUN_MOTOR2_FINAL_SHADOW` is present in the service configuration;
- no `MOTOR2_FINAL_SNAPSHOT_MODE` variable exists today.

Natural 2026-09-12 runs also showed the same race in adjacent runs under distinct keys, directly confirming repeated-window accumulation. Example: race `20260912_12_06` appeared under both `20260912_final_170200` and `20260912_final_171623`.

## Safety gate

Activation is NOT authorized by this Draft. Before any Railway variable is added or the implementation is merged for active use, require:

1. CI green and syntax/isolation checks;
2. review that protected Motor2 reports do not need multiple FINAL intra-window rows;
3. a projected savings estimate from recent natural runs/retention evidence;
4. explicit Production approval.

Current gate:

`DEFAULT_TIMESTAMPED / COMPACT_MODE_DORMANT / NO_RAILWAY_VARIABLE / NO_DB_DELETE / NO_VACUUM / NO_MODEL_CHANGE / NO_LINE_CHANGE / NO_PURCHASE / EXPLICIT_PRODUCTION_APPROVAL_REQUIRED`
