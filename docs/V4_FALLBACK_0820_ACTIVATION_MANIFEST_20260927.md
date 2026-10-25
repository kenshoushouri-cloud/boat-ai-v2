# V4 fallback 08:20 activation manifest — design only

This is a no-op manifest for the separately-approved future Production action.

Exact target:
- project: `268a5b17-0712-440a-884d-27f7fa887a2d`
- environment: Production `5ffb02f6-5ec8-4268-9bda-8e30431ff625`
- service: `candidate-discovery-v4-fallback-dispatcher`
- service ID: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`

Only intended field change:
- current: `cronSchedule = 25 23 * * *` (08:25 JST)
- proposed: `cronSchedule = 20 23 * * *` (08:20 JST)

Everything else must remain unchanged.

Preconditions before any future activation:
1. explicit user approval for this exact Production Cron change;
2. re-read service config and confirm current Cron is still 08:25;
3. staged changes = none;
4. pending work = none;
5. latest dispatcher deployment = SUCCESS.

Post-change checks:
1. Cron exactly 08:20;
2. deployment SUCCESS;
3. staged changes = none;
4. pending work = none;
5. no other service-config field changed.

Rollback target:
- restore `25 23 * * *` (08:25 JST).

This file authorizes nothing by itself.

`ONE_FIELD_CRON_ONLY / EXPLICIT_APPROVAL_REQUIRED / ROLLBACK_0825 / NOT_ACTIVATED`
