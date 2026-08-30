#!/usr/bin/env python3
"""Guarded Railway Postgres recovery Stage 2 reference promotion.

Railway Project Tokens can operate the recovered database service but are not
authorized to rename it. Stage 2 therefore restores Production connectivity
without moving or restarting the database:

1. Verify postgres is absent and postgres-recovery is the audited DB service.
2. Re-check preserved volume, backup, pinned PostgreSQL 18 digest and credentials.
3. Create the production TCP proxy and restore DATABASE_PUBLIC_URL by Railway refs.
4. Re-run the read-only DB integrity audit.
5. Change each application service DATABASE_URL to
   ${{postgres-recovery.DATABASE_URL}} with skipDeploys=True.
6. Leave consumer redeploys for a separate postcondition-gated step.

No secret value is copied. The preserved volume is never moved, remounted, restored,
deleted, or wiped. The recovered DB service is never redeployed by this script.
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

TARGET_SERVICE = "postgres"
RECOVERY_SERVICE = "postgres-recovery"
TARGET_VOLUME = "postgres-volume"

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

RECOVERY_DATABASE_REF = stage1.ref("postgres-recovery.DATABASE_URL")
LEGACY_DATABASE_REF = stage1.ref("postgres.DATABASE_URL")


class PromotionError(RuntimeError):
    pass


def safe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_summary(lines: list[str]) -> None:
    Path("stage2-result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def latest_deployment(service_id: str) -> dict[str, Any]:
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
        raise PromotionError("Recovery service deployment missing")
    latest = sorted(
        deployments,
        key=lambda row: row.get("createdAt") or "",
        reverse=True,
    )[0]
    status = str(latest.get("status") or "")
    if status != "SUCCESS":
        raise PromotionError("Recovery service latest deployment is not SUCCESS: " + status)
    if not stage1.find_string(latest.get("meta"), stage1.EXPECTED_DIGEST):
        raise PromotionError("Recovery service deployment digest mismatch")
    return latest


def resolve_context() -> dict[str, Any]:
    data = stage1.gql(
        """
        query PromotionContext {
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
    token_obj = data.get("projectToken") or {}
    project_id = token_obj.get("projectId")
    environment_id = token_obj.get("environmentId")
    project = token_obj.get("project") or {}
    if not project_id or not environment_id:
        raise PromotionError("Project/environment context unresolved")

    services = stage1.nodes(project.get("services"))
    by_name = {
        str(row.get("name")): row
        for row in services
        if row.get("name") and not row.get("deletedAt")
    }
    if TARGET_SERVICE in by_name:
        raise PromotionError("Unexpected postgres service already exists")

    recovery = by_name.get(RECOVERY_SERVICE)
    if not recovery or not recovery.get("id"):
        raise PromotionError("postgres-recovery service missing")
    recovery_id = str(recovery["id"])

    missing_consumers = [name for name in CONSUMER_SERVICES if name not in by_name]
    if missing_consumers:
        raise PromotionError(
            "Required consumer services missing: " + ",".join(missing_consumers)
        )
    consumer_ids = {
        name: str(by_name[name]["id"])
        for name in CONSUMER_SERVICES
    }

    volume = None
    volume_instance = None
    for item in stage1.nodes(project.get("volumes")):
        if item.get("name") != TARGET_VOLUME:
            continue
        volume = item
        instances = stage1.nodes(item.get("volumeInstances"))
        if instances:
            volume_instance = sorted(
                instances,
                key=lambda row: row.get("createdAt") or "",
                reverse=True,
            )[0]
        break

    if not volume or not volume_instance:
        raise PromotionError("Preserved postgres-volume unresolved")

    guards = {
        "volume_ready": volume_instance.get("state") == "READY",
        "not_pending_deletion": (
            volume_instance.get("isPendingDeletion") is False
            and not volume_instance.get("deletedAt")
        ),
        "same_service_attachment": (
            str(volume_instance.get("serviceId") or "") == recovery_id
        ),
        "mount_path": volume_instance.get("mountPath") == stage1.EXPECTED_MOUNT,
        "region": volume_instance.get("region") == stage1.EXPECTED_REGION,
        "configured_size": (
            int(volume_instance.get("sizeMB") or 0) == stage1.EXPECTED_SIZE_MB
        ),
        "data_size": float(volume_instance.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise PromotionError("Promotion volume guard failed: " + ",".join(failed))

    latest_deployment(recovery_id)
    stage1.guard_known_backup(str(volume_instance.get("id")))

    return {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "recovery_service_id": recovery_id,
        "consumer_ids": consumer_ids,
        "volume_instance_id": str(volume_instance.get("id")),
        "volume_current_size_mb": volume_instance.get("currentSizeMB"),
    }


def create_tcp_proxy(environment_id: str, service_id: str) -> dict[str, Any]:
    data = stage1.gql(
        """
        mutation Q($input:TCPProxyCreateInput!) {
          tcpProxyCreate(input:$input) {
            id applicationPort domain proxyPort syncStatus
          }
        }
        """,
        {
            "input": {
                "applicationPort": 5432,
                "environmentId": environment_id,
                "serviceId": service_id,
            }
        },
    )
    proxy = data.get("tcpProxyCreate")
    if not isinstance(proxy, dict):
        raise PromotionError("TCP proxy creation failed")
    if not proxy.get("id") or not proxy.get("domain") or not proxy.get("proxyPort"):
        raise PromotionError("TCP proxy metadata incomplete")
    return proxy


def upsert_variable(
    project_id: str,
    environment_id: str,
    service_id: str,
    name: str,
    value: str,
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
                "name": name,
                "value": value,
                "skipDeploys": True,
            }
        },
    )
    if data.get("variableUpsert") is not True:
        raise PromotionError(f"{name} upsert failed")


def restore_public_url(
    project_id: str,
    environment_id: str,
    service_id: str,
) -> None:
    value = (
        "postgresql://"
        + stage1.ref("PGUSER")
        + ":"
        + stage1.ref("POSTGRES_PASSWORD")
        + "@"
        + stage1.ref("RAILWAY_TCP_PROXY_DOMAIN")
        + ":"
        + stage1.ref("RAILWAY_TCP_PROXY_PORT")
        + "/"
        + stage1.ref("PGDATABASE")
    )
    upsert_variable(
        project_id,
        environment_id,
        service_id,
        "DATABASE_PUBLIC_URL",
        value,
    )


def promote_consumer_references(context: dict[str, Any]) -> list[str]:
    updated: list[str] = []
    try:
        for name in CONSUMER_SERVICES:
            upsert_variable(
                context["project_id"],
                context["environment_id"],
                context["consumer_ids"][name],
                "DATABASE_URL",
                RECOVERY_DATABASE_REF,
            )
            updated.append(name)
        return updated
    except Exception:
        rollback_failed: list[str] = []
        for name in reversed(updated):
            try:
                upsert_variable(
                    context["project_id"],
                    context["environment_id"],
                    context["consumer_ids"][name],
                    "DATABASE_URL",
                    LEGACY_DATABASE_REF,
                )
            except Exception:
                rollback_failed.append(name)
        if rollback_failed:
            raise PromotionError(
                "Consumer reference promotion failed; rollback incomplete: "
                + ",".join(sorted(rollback_failed))
            ) from None
        raise PromotionError(
            "Consumer reference promotion failed; updated references rolled back"
        ) from None


def main() -> int:
    lines = [
        "## Railway Postgres recovery Stage 2",
        "",
        "Promotion mode: Railway dynamic-reference promotion to postgres-recovery.",
        "The database service and preserved volume are not moved or restarted.",
        "",
    ]
    proxy_id: str | None = None
    references_promoted = False

    try:
        context = resolve_context()
        _, snapshot = stage1.resolve_deleted_deployment_and_snapshot(
            context["project_id"],
            context["environment_id"],
        )
        lines += [
            "### Promotion preflight",
            "",
            "- postgres absent: PASS",
            "- postgres-recovery present: PASS",
            "- all 13 consumer services present: PASS",
            "- postgres-volume attached to postgres-recovery: PASS",
            "- preserved backup: PASS",
            "- exact deleted PostgreSQL 18 digest: PASS",
            f"- volume current size MB: {safe(context['volume_current_size_mb'])}",
            "",
        ]

        proxy = create_tcp_proxy(
            context["environment_id"],
            context["recovery_service_id"],
        )
        proxy_id = str(proxy["id"])
        restore_public_url(
            context["project_id"],
            context["environment_id"],
            context["recovery_service_id"],
        )
        lines += [
            "### Public endpoint restoration",
            "",
            "- TCP proxy created for postgres-recovery: YES",
            "- DATABASE_PUBLIC_URL restored using Railway dynamic references: YES",
            "- Proxy host/port: NOT PUBLISHED",
            "",
        ]

        audit = stage1.run_db_integrity_audit(proxy, snapshot)
        lines += [
            "### Pre-promotion read-only DB integrity",
            "",
            f"- PostgreSQL version: {safe(audit['server_version'])}",
            f"- Database size bytes: {safe(audit['database_size_bytes'])}",
            f"- v2_races rows: {safe(audit['races'])}",
            f"- v2_race_entries rows: {safe(audit['entries'])}",
            f"- v2_results rows: {safe(audit['results'])}",
            f"- v2_odds_trifecta estimated rows: {safe(audit['odds_estimate'])}",
            f"- v2_odds_trifecta total bytes: {safe(audit['odds_size_bytes'])}",
            f"- Latest race_date: {safe(audit['max_race_date'])}",
            "",
        ]

        updated = promote_consumer_references(context)
        references_promoted = True

        post = resolve_context()
        if post["recovery_service_id"] != context["recovery_service_id"]:
            raise PromotionError("Recovery service identity changed")
        if post["volume_instance_id"] != context["volume_instance_id"]:
            raise PromotionError("Preserved volume identity changed")

        lines += [
            "### Reference promotion result",
            "",
            f"- Consumer DATABASE_URL references updated: {len(updated)}/{len(CONSUMER_SERVICES)}",
            "- Target reference: postgres-recovery.DATABASE_URL (value not published)",
            "- skipDeploys used for every consumer update: YES",
            "- Raw DB credentials copied: NO",
            "- postgres-recovery service identity unchanged: YES",
            "- postgres-volume identity/attachment unchanged: YES",
            "- PostgreSQL deployment remained SUCCESS on pinned digest: YES",
            "- Existing backup guard after promotion: PASS",
            "",
            "**STAGE2_REFERENCE_PROMOTION_PASS_VERIFY_CONSUMERS**",
            "",
            "- The restored TCP proxy is intentionally retained as the production public DB endpoint.",
            "- Consumer redeploys must wait for read-only DATABASE_URL resolution checks.",
            "- Do not change model/LINE/BUY-WATCH-SKIP/N01/N02/Bao/thresholds or PR #169.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        cleanup = "NOT_NEEDED"
        if proxy_id and not references_promoted:
            try:
                stage1.delete_tcp_proxy(proxy_id)
                cleanup = "SUCCESS"
            except Exception:
                cleanup = "FAILED"

        safe_error = (
            str(exc)
            if isinstance(exc, (PromotionError, stage1.RecoveryError))
            else type(exc).__name__
        )
        lines += [
            "",
            "### Stage 2 failure",
            "",
            f"- Error class: {safe(type(exc).__name__)}",
            f"- Safe error: {safe(safe_error)}",
            f"- Consumer reference promotion completed: {'YES' if references_promoted else 'NO'}",
            f"- Pre-promotion TCP proxy cleanup: {cleanup}",
            "",
            "**STAGE2_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- Do not redeploy Production consumers until read-only reference checks pass.",
            "- No volume move, DB service redeploy, restore, PITR, delete, or wipe was attempted.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
