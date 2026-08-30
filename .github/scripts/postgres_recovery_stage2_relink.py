#!/usr/bin/env python3
"""Stage 2 consumer DATABASE_URL relink.

The real database remains postgres-recovery with the preserved volume.
This script changes ONLY DATABASE_URL on a fixed allowlist of application services,
using a Railway Reference Variable to postgres-recovery.DATABASE_URL.

Changes are staged with skipDeploys=True. No service is redeployed here.
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

TARGET_SERVICES = (
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


class RelinkError(RuntimeError):
    pass


def service_ref(service: str, variable: str) -> str:
    return "$" + "{{" + service + "." + variable + "}}"


def safe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_summary(lines: list[str]) -> None:
    Path("stage2-relink-result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
                    name
                    volumeInstances(first:100) {
                      edges {
                        node {
                          id serviceId state mountPath region sizeMB currentSizeMB
                          deletedAt isPendingDeletion
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
        raise RelinkError("Project/environment context unresolved")

    services = stage1.nodes(project.get("services"))
    by_name = {
        str(row.get("name")): row
        for row in services
        if row.get("name") and not row.get("deletedAt")
    }
    for required in (REAL_DB_SERVICE, COMPAT_SERVICE, *TARGET_SERVICES):
        if required not in by_name or not by_name[required].get("id"):
            raise RelinkError("Required service missing: " + required)

    real_id = str(by_name[REAL_DB_SERVICE]["id"])
    compat_id = str(by_name[COMPAT_SERVICE]["id"])
    if real_id == compat_id:
        raise RelinkError("Compatibility service unexpectedly matches real DB service")

    volume_instance = None
    for volume in stage1.nodes(project.get("volumes")):
        if volume.get("name") != TARGET_VOLUME:
            continue
        for inst in stage1.nodes(volume.get("volumeInstances")):
            if str(inst.get("serviceId") or "") == real_id:
                volume_instance = inst
                break

    if not volume_instance:
        raise RelinkError("Preserved postgres volume not attached to postgres-recovery")

    guards = {
        "volume_ready": volume_instance.get("state") == "READY",
        "not_pending_deletion": (
            volume_instance.get("isPendingDeletion") is False
            and not volume_instance.get("deletedAt")
        ),
        "mount_path": volume_instance.get("mountPath") == stage1.EXPECTED_MOUNT,
        "region": volume_instance.get("region") == stage1.EXPECTED_REGION,
        "size": int(volume_instance.get("sizeMB") or 0) == stage1.EXPECTED_SIZE_MB,
        "data_size": float(volume_instance.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise RelinkError("Volume guard failed: " + ",".join(failed))

    stage1.guard_known_backup(str(volume_instance.get("id")))

    return {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "real_service_id": real_id,
        "volume_instance_id": str(volume_instance.get("id")),
        "volume_current_size_mb": volume_instance.get("currentSizeMB"),
        "service_ids": {name: str(by_name[name]["id"]) for name in TARGET_SERVICES},
    }


def relink_database_url(
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
                "value": service_ref(REAL_DB_SERVICE, "DATABASE_URL"),
                "skipDeploys": True,
            }
        },
    )
    if data.get("variableUpsert") is not True:
        raise RelinkError("DATABASE_URL relink mutation failed")


def main() -> int:
    lines = [
        "## Railway Postgres Stage 2 consumer relink",
        "",
        "Only DATABASE_URL is changed, using a Railway Reference Variable.",
        "No secret value is copied or published and no deployment is started here.",
        "",
    ]
    try:
        context = resolve_context()
        lines += [
            "### Preflight",
            "",
            "- postgres-recovery real DB service: PRESENT",
            "- postgres compatibility service: PRESENT",
            "- preserved volume still attached to postgres-recovery: PASS",
            "- preserved backup guard: PASS",
            f"- volume current size MB: {safe(context['volume_current_size_mb'])}",
            "",
        ]

        changed = []
        for name in TARGET_SERVICES:
            relink_database_url(
                context["project_id"],
                context["environment_id"],
                context["service_ids"][name],
            )
            changed.append(name)

        lines += [
            "### Staged relink",
            "",
            f"- Services staged: {len(changed)}",
            "- DATABASE_URL target: postgres-recovery.DATABASE_URL reference",
            "- skipDeploys: TRUE",
            "- No other Variable changed: YES",
            "- No service redeployed: YES",
            "",
        ]
        for name in changed:
            lines.append(f"- {name}")

        lines += [
            "",
            "**STAGE2_RELINK_STAGED_VERIFY_BEFORE_REDEPLOY**",
            "",
            "- Run read-only DB reference diagnostics next.",
            "- Redeploy consumers only after verification.",
        ]
        write_summary(lines)
        return 0
    except Exception as exc:
        safe_error = str(exc) if isinstance(exc, (RelinkError, stage1.RecoveryError)) else type(exc).__name__
        lines += [
            "",
            "### Relink failure",
            "",
            f"- Error class: {safe(type(exc).__name__)}",
            f"- Safe error: {safe(safe_error)}",
            "",
            "**STAGE2_RELINK_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- No automatic redeploy is performed by this script.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
