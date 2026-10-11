# Value Candidate Shadow Storage Budget

Date: 2026-09-12 JST

Read-only Railway metrics at research start:

- Production PostgreSQL disk usage: about 4.18 GB current
- volume capacity: 5 GB
- free headroom is therefore too small for a new ticket-level persistent experiment

## Storage policy for this experiment

The experiment must consume effectively zero persistent Production DB growth.

### Production DB

Budget: **0 new persistent research tables / 0 new ticket-level shadow writes**.

### GitHub / CI artifacts

Preferred outputs:

- aggregate JSON summaries;
- optional CSV summaries containing aggregate rows only;
- focused logs.

Target: KB to low-MB scale per completed analysis, not raw ticket replicas.

### Historical extraction

Read existing rows in bounded batches. Do not persist duplicated historical odds or feature rows. If an analysis needs an intermediate dataset, create it outside Production DB and treat it as ephemeral.

## Stop condition

If a proposed extension requires meaningful persistent Railway growth, a new service, a new volume, or a new Production Cron, stop at an approval gate and redesign before implementation.
