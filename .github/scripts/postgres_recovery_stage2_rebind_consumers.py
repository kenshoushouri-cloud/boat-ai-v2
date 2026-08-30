#!/usr/bin/env python3
"""Rebind Production consumers to the recovered Postgres compatibility namespace.

The Stage 2 compatibility service named "postgres" now resolves DATABASE_URL, but
existing consumer reference objects still point to the deleted original service.
This script re-saves the same logical reference expression,
${{postgres.DATABASE_URL}}, on every application service with skipDeploys=True.

No raw credential value is read or copied. No service is redeployed here.
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

ALIAS_SERVICE = "postgres"
REAL_DB_SERVICE = "postgres-recovery"
TARGET_VOLUME = "postgres-volume"
TARGET_REFERENCE = stage1.ref("postgres.DATABASE_URL")

CONSUMER_SERVICES = (
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


class RebindError(RuntimeError):
    pass


def write_summary(lines: list[str]) -> None:
    Path("stage2-rebind-result.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


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
        raise RebindError("Project/environment context unresolved")

    services = stage1.nodes(project.get("services"))
    by_name = {
        str(row.get("name")): row
        for row in services
        if row.get("name") and not row.get("deletedAt")
    }

    alias = by_name.get(ALIAS_SERVICE)
    real = by_name.get(REAL_DB_SERVICE)
    if not alias or not alias.get("id"):
        raise RebindError("Compatibility postgres service missing")
    if not real or not real.get("id"):
        raise RebindError("Real postgres-recovery service missing")

    missing = [name for name in CONSUMER_SERVICES if name not in by_name]
    if missing:
        raise RebindError("Required consumer services missing: " + ",".join(missing))

    real_id = str(real["id"])
    alias_id = str(alias["id"])
    if real_id == alias_id:
        raise RebindError("Compatibility service unexpectedly equals real DB service")

    preserved = None
    alias_has_volume = False
    for volume in stage1.nodes(project.get("volumes")):
        for inst in stage1.nodes(volume.get("volumeInstances")):
            if str(inst.get("serviceId") or "") == alias_id:
                alias_has_volume = True
            if (
                volume.get("name") == TARGET_VOLUME
                and str(inst.get("serviceId") or "") == real_id
            ):
                preserved = inst

    if alias_has_volume:
        raise RebindError("Compatibility postgres service must not own a volume")
    if not preserved:
        raise RebindError("Preserved volume is not attached to postgres-recovery")

    guards = {
        "volume_ready": preserved.get("state") == "READY",
        "not_pending_deletion": (
            preserved.get("isPendingDeletion") is False
            and not preserved.get("deletedAt")
        ),
        "mount_path": preserved.get("mountPath") == stage1.EXPECTED_MOUNT,
        "region": preserved.get("region") == stage1.EXPECTED_REGION,
        "configured_size": int(preserved.get("sizeMB") or 0) == stage1.EXPECTED_SIZE_MB,
        "data_size": float(preserved.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise RebindError("Preserved volume guard failed: " + ",".join(failed))

    # Re-use the exact Stage 1 safety evidence before touching consumer references.
    stage1.guard_known_backup(str(preserved.get("id")))

    return {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "alias_service_id": alias_id,
        "real_service_id": real_id,
        "consumer_ids": {
            name: str(by_name[name]["id"])
            for name in CONSUMER_SERVICES
        },
        "volume_instance_id": str(preserved.get("id")),
        "volume_current_size_mb": preserved.get("currentSizeMB"),
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
                "value": TARGET_REFERENCE,
                "skipDeploys": True,
            }
        },
    )
    if data.get("variableUpsert") is not True:
        raise RebindError("DATABASE_URL reference upsert failed")


def main() -> int:
    lines = [
        "## Railway Postgres Stage 2 consumer reference rebind",
        "",
        "The target expression remains postgres.DATABASE_URL; only the stale Railway reference binding is refreshed.",
        "No credential value is read, copied, or published.",
        "",
    ]
    updated: list[str] = []

    try:
        context = resolve_context()
        lines += [
            "### Safety preflight",
            "",
            "- compatibility postgres service present: PASS",
            "- real postgres-recovery service present: PASS",
            "- compatibility service owns no volume: PASS",
            "- postgres-volume remains on postgres-recovery: PASS",
            "- preserved backup guard: PASS",
            f"- preserved volume current size MB: {context['volume_current_size_mb']}",
            "- required consumer services: 13/13",
            "",
        ]

        for name in CONSUMER_SERVICES:
            upsert_database_reference(
                context["project_id"],
                context["environment_id"],
                context["consumer_ids"][name],
            )
            updated.append(name)

        post = resolve_context()
        if post["real_service_id"] != context["real_service_id"]:
            raise RebindError("Real DB service identity changed during rebind")
        if post["alias_service_id"] != context["alias_service_id"]:
            raise RebindError("Compatibility service identity changed during rebind")
        if post["volume_instance_id"] != context["volume_instance_id"]:
            raise RebindError("Preserved volume identity changed during rebind")

        lines += [
            "### Rebind result",
            "",
            f"- consumer DATABASE_URL references refreshed: {len(updated)}/{len(CONSUMER_SERVICES)}",
            "- target namespace: postgres.DATABASE_URL",
            "- skipDeploys=True for all updates: YES",
            "- consumer redeploys started: NO",
            "- raw credentials copied: NO",
            "- DB service/volume mutation: NO",
            "",
            "**STAGE2_CONSUMER_REBIND_PASS_VERIFY_REFERENCES**",
            "",
            "- Read-only reference verification is required before any consumer redeploy.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        safe_error = (
            str(exc)
            if isinstance(exc, (RebindError, stage1.RecoveryError))
            else type(exc).__name__
        )
        lines += [
            "",
            "### Rebind failure",
            "",
            f"- Error class: {type(exc).__name__}",
            f"- Safe error: {safe_error}",
            f"- Successfully refreshed before failure: {len(updated)}/{len(CONSUMER_SERVICES)}",
            "",
            "**STAGE2_CONSUMER_REBIND_BLOCK_REVIEW_REQUIRED**",
            "",
            "- No consumer redeploy was started.",
            "- A partial reference refresh is safe because skipDeploys=True; verify states before retrying.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
