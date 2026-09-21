# V4 fresh restore post-rehearsal acceptance gate — 2026-09-21

Status: `RESEARCH_ONLY / PURE_OFFLINE / NO_PRODUCTION_MIGRATION / HOBBY_CAPACITY_PROOF_CONTRACT`

## Purpose

The prerequisite manifest gate controls when a decision-grade non-Production restore rehearsal may start.

This second gate defines what must be true **after** that restore finishes before the result can count as evidence that a Hobby 5 GB volume is technically large enough.

A restore merely reporting `pg_database_size() < 5GB` is insufficient.

## Required measured evidence

The target must be:

- non-Production;
- a completed fresh retained-set restore.

The acceptance gate requires both:

- observed PostgreSQL database bytes;
- **physically observed target filesystem/volume bytes**.

The physical target measurement is mandatory and may not be replaced by tuple payload estimates or current Production disk usage.

## Frozen headroom policy

The same frozen headroom policy must provide:

- conservative Hobby volume ceiling `5,000,000,000` bytes;
- required reserve bytes;
- measured daily growth bytes;
- growth horizon days.

The reserve must cover at least the measured growth horizon.

Capacity condition:

`OBSERVED_TARGET_FILESYSTEM_BYTES + REQUIRED_RESERVE_BYTES <= 5,000,000,000 bytes`

If this fails, the decision is:

`FAIL_FRESH_RESTORE_CAPACITY_HEADROOM`

The response is **not** to silently delete more required evidence or shrink the retained set after seeing the result. Any retained-set revision requires a separately reviewed retention/archive decision and a new rehearsal.

## Equivalence gates

All must PASS:

- schema equivalent;
- indexes/constraints/extensions equivalent;
- retained row counts equivalent;
- representative retained-data digests equivalent;
- application read-only smoke;
- archive-backed historical consumer smoke.

A smaller restore that omits required indexes or evidence does not count as Hobby proof.

## Non-implication

Even:

`PASS_FRESH_RESTORE_CAPACITY_AND_EQUIVALENCE`

does **not** authorize Railway Pro -> Hobby.

Production plan/service/volume migration remains a separate explicit-approval action, followed by a fresh Production dependency/config recheck.

## Current state

No real retained-set fresh restore has yet satisfied these inputs, so:

`HOBBY_CAPACITY_PROOF_NOT_YET_AVAILABLE / OCT03_REMAINS_GO_NO_GO_CHECKPOINT`

## Safety

`NO_CAPACITY_DRIVEN_DELETE / NO_AUTO_PLAN_CHANGE / NO_PRODUCTION_MUTATION / PURCHASE_FALSE`
