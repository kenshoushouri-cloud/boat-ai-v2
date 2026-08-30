#!/usr/bin/env python3
"""Guarded Stage 2 consumer DATABASE_URL rewire.

The real recovered database remains on the postgres-recovery service. Railway Project
Tokens cannot rename that service, and the compatibility postgres service does not
resolve transitively for existing consumers. This step makes the smallest possible
Production configuration change:

- verify postgres-recovery is still the audited DB service;
- verify postgres is only the compatibility service and owns no volume;
- verify the preserved postgres-volume, backup, and pinned digest;
- update ONLY DATABASE_URL for the 13 known application services;
- set each value to a Railway reference to postgres-recovery.DATABASE_URL;
- use skipDeploys=True so no application is restarted by this step.

Deployment/restart is intentionally a separate step after read-only reference
verification.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STAGE1_PATH = HERE / "postgres_recovery_stage1.py"
spec = importlib.util.spec_from_file_location("postgres_recovery_stage1", STAGE1_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Stage 1 helper module unavailable")
stage1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage1)

REAL_DB_SERVICE = "postgres-recovery"
COMPAT_SERVICE = "postgres"
TARGET_VOLUME = "postgres-volume"
EXPECTED_REFERENCE = "${{postgres-recovery.DATABASE_URL}}"

CONSUMERS = (
    "backtest-analysis",
    "cron-daily-report",
    "cron-data-prepare",
    "cron-final-check",
    "cron-learning-all",
    "cron-monthly-report",
    "cron-nightly-results",
    "cron-racer-course-stats",
    "cron-window-day",
    "cron-window-morning",
    "cron-window-night",
    "historical-backfill",
    "test-beforeinfo-extra",
)


class RewireError(RuntimeError):
    pass


def safe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_summary(lines: list[str]) -> None:
    Path("consumer-rewire-result.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def latest_recovery_deployment(service_id: str) -> None:
    data = stage1.gql(
        """
        query Q($id:String!) {
          service(id:$id) {
            id
            name
            deployments(first:20) {
              edges { node { id createdAt status meta } }
            }
          }
        }
        """,
        {"id": service_id},
    )
    service = data.get("service") or {}
    deployments = stage1.nodes(service.get("deployments"))
    if not deployments:
        raise RewireError("postgres-recovery deployment missing")
    latest = sorted(
        deployments,
        key=lambda row: row.get("createdAt") or "",
        reverse=True,
    )[0]
    if str(latest.get("status") or "") != "SUCCESS":
        raise RewireError(
            "postgres-recovery latest deployment is not SUCCESS: "
            + str(latest.get("status") or "-")
        )
    if not stage1.find_string(latest.get("meta"), stage1.EXPECTED_DIGEST):
        raise RewireError("postgres-recovery deployment digest mismatch")


def resolve_context() -> dict[str, Any]:
    data = stage1.gql(
        """
        query Q {
          projectToken {
            projectId
            environmentId
            project {
              services(first:100) {
                edges { node { id name deletedAt } }
              }
              volumes(first:100) {
                edges {
                  node {
                    id
                    name
                    volumeInstances(first:100) {
                      edges {
                        node {
                          id
                          createdAt
                          deletedAt
                          currentSizeMB
                          sizeMB
                          mountPath
                          region
                          state
                          isPendingDeletion
                          serviceId
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
    )

    token = data.get("projectToken") or {}
    project_id = token.get("projectId")
    environment_id = token.get("environmentId")
    project = token.get("project") or {}
    if not project_id or not environment_id:
        raise RewireError("Project/environment context unresolved")

    services = stage1.nodes(project.get("services"))
    by_name = {
        str(row.get("name")): row
        for row in services
        if row.get("name") and not row.get("deletedAt")
    }

    real = by_name.get(REAL_DB_SERVICE)
    compat = by_name.get(COMPAT_SERVICE)
    if not real or not real.get("id"):
        raise RewireError("postgres-recovery service missing")
    if not compat or not compat.get("id"):
        raise RewireError("compatibility postgres service missing")

    real_id = str(real["id"])
    compat_id = str(compat["id"])
    if real_id == compat_id:
        raise RewireError("postgres compatibility service identity is invalid")

    missing_consumers = [name for name in CONSUMERS if name not in by_name]
    if missing_consumers:
        raise RewireError(
            "Required consumer services missing: " + ",".join(missing_consumers)
        )

    volume_instance = None
    compat_has_volume = False
    for volume in stage1.nodes(project.get("volumes")):
        for inst in stage1.nodes(volume.get("volumeInstances")):
            sid = str(inst.get("serviceId") or "")
            if sid == compat_id:
                compat_has_volume = True
            if (
                volume.get("name") == TARGET_VOLUME
                and sid == real_id
            ):
                volume_instance = inst

    if compat_has_volume:
        raise RewireError("Compatibility postgres service unexpectedly owns a volume")
    if not volume_instance:
        raise RewireError("Preserved postgres-volume is not attached to postgres-recovery")

    guards = {
        "volume_ready": volume_instance.get("state") == "READY",
        "not_pending_deletion": (
            volume_instance.get("isPendingDeletion") is False
            and not volume_instance.get("deletedAt")
        ),
        "mount_path": volume_instance.get("mountPath") == stage1.EXPECTED_MOUNT,
        "region": volume_instance.get("region") == stage1.EXPECTED_REGION,
        "configured_size": int(volume_instance.get("sizeMB") or 0)
        == stage1.EXPECTED_SIZE_MB,
        "data_size": float(volume_instance.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise RewireError("Preserved volume guard failed: " + ",".join(failed))

    latest_recovery_deployment(real_id)
    stage1.guard_known_backup(str(volume_instance.get("id")))

    service_ids = {
        name: str(by_name[name]["id"])
        for name in CONSUMERS
    }

    return {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "real_service_id": real_id,
        "compat_service_id": compat_id,
        "volume_instance_id": str(volume_instance.get("id")),
        "volume_current_size_mb": volume_instance.get("currentSizeMB"),
        "service_ids": service_ids,
    }


def upsert_database_reference(
    project_id: str,
    environment_id: str,
    service_id: str,
) -> None:
    data = stage1.gql(
        """
        mutation Q($input:VariableUpsertInput!) {
          variableUpsert(input:$input)
        }
        """,
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": service_id,
                "name": "DATABASE_URL",
                "value": EXPECTED_REFERENCE,
                "skipDeploys": True,
            }
        },
    )
    if data.get("variableUpsert") is not True:
        raise RewireError("DATABASE_URL reference upsert failed")


def main() -> int:
    lines = [
        "## Railway Postgres Stage 2 consumer rewire",
        "",
        "This step changes only DATABASE_URL on the hardcoded consumer allowlist.",
        "No deploy/redeploy is triggered by this step.",
        "",
    ]
    changed: list[str] = []

    try:
        context = resolve_context()
        lines += [
            "### Preflight",
            "",
            "- postgres-recovery real DB service: PASS",
            "- compatibility postgres service: PASS",
            "- compatibility postgres owns no volume: PASS",
            "- postgres-volume remains on postgres-recovery: PASS",
            "- pinned PostgreSQL 18 deployment digest: PASS",
            "- preserved backup guard: PASS",
            f"- volume current size MB: {safe(context['volume_current_size_mb'])}",
            f"- consumer allowlist count: {len(CONSUMERS)}",
            "",
        ]

        for service in CONSUMERS:
            upsert_database_reference(
                context["project_id"],
                context["environment_id"],
                context["service_ids"][service],
            )
            changed.append(service)

        lines += [
            "### Rewire result",
            "",
            f"- DATABASE_URL reference updated with skipDeploys: **{len(changed)}/{len(CONSUMERS)}**",
            "- New reference target: postgres-recovery.DATABASE_URL",
            "- Secret/credential values copied: NO",
            "- Other Variables changed: NO",
            "- Application deploy/redeploy triggered: NO",
            "- Volume/service/database mutation: NO",
            "",
            "**CONSUMER_REWIRE_WRITES_PASS_VERIFY_REFERENCES**",
            "",
            "Next step: verify all 13 rendered DATABASE_URL values are non-empty before any redeploy.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        safe_error = (
            str(exc)
            if isinstance(exc, (RewireError, stage1.RecoveryError))
            else type(exc).__name__
        )
        lines += [
            "",
            "### Consumer rewire failure",
            "",
            f"- Safe error: {safe(safe_error)}",
            f"- Successfully updated before failure: {len(changed)}/{len(CONSUMERS)}",
            "",
            "**CONSUMER_REWIRE_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- Do not redeploy consumers until the read-only reference audit passes.",
            "- Re-running this operation is idempotent for already-updated DATABASE_URL references.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
