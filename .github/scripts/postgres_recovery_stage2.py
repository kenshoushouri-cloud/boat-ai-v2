#!/usr/bin/env python3
"""Guarded Railway Postgres recovery Stage 2 compatibility promotion.

Railway Project Tokens cannot rename the recovered service (serviceUpdate is rejected
as not_authorized). Stage 2 therefore restores the original variable namespace without
moving or restarting the database:
1. Verify postgres is absent and postgres-recovery is the audited real DB service.
2. Re-check preserved volume, backup, deployment digest, and credentials.
3. Create a persistent TCP proxy on postgres-recovery.
4. Restore DATABASE_PUBLIC_URL on postgres-recovery using Railway dynamic references.
5. Re-run the read-only DB integrity audit.
6. Create an empty compatibility service named postgres whose DB variables are only
   Railway references to postgres-recovery.
7. Verify the real DB service, volume identity, pinned digest, backup, and alias isolation.

No Production consumer Variable is edited here. Existing ${{postgres.DATABASE_URL}}
references can resolve through the compatibility namespace. Consumer redeploys remain
separate and occur only after post-promotion read-only reference verification.
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
STAGING_SERVICE = "postgres-recovery"
TARGET_VOLUME = "postgres-volume"


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
    if str(latest.get("status") or "") != "SUCCESS":
        raise PromotionError(
            "Recovery service latest deployment is not SUCCESS: "
            + str(latest.get("status") or "-")
        )
    if not stage1.find_string(latest.get("meta"), stage1.EXPECTED_DIGEST):
        raise PromotionError("Recovery service deployment digest mismatch")
    return latest


def resolve_context(expected_name: str, forbidden_name: str) -> dict[str, Any]:
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
    by_name = {str(row.get("name")): row for row in services if row.get("name")}
    if forbidden_name in by_name:
        raise PromotionError(f"Forbidden service already exists: {forbidden_name}")
    service = by_name.get(expected_name)
    if not service or not service.get("id"):
        raise PromotionError(f"Expected service missing: {expected_name}")
    service_id = str(service["id"])

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
        "same_service_attachment": str(volume_instance.get("serviceId") or "") == service_id,
        "mount_path": volume_instance.get("mountPath") == stage1.EXPECTED_MOUNT,
        "region": volume_instance.get("region") == stage1.EXPECTED_REGION,
        "configured_size": int(volume_instance.get("sizeMB") or 0) == stage1.EXPECTED_SIZE_MB,
        "data_size": float(volume_instance.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise PromotionError("Promotion volume guard failed: " + ",".join(failed))

    latest_deployment(service_id)
    stage1.guard_known_backup(str(volume_instance.get("id")))

    return {
        "project_id": str(project_id),
        "environment_id": str(environment_id),
        "service_id": service_id,
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
                "name": "DATABASE_PUBLIC_URL",
                "value": value,
                "skipDeploys": True,
            }
        },
    )
    if data.get("variableUpsert") is not True:
        raise PromotionError("DATABASE_PUBLIC_URL restore failed")


def service_ref(service: str, variable: str) -> str:
    return "$" + "{{" + service + "." + variable + "}}"


def create_compat_alias(
    project_id: str,
    environment_id: str,
) -> str:
    keys = (
        "DATABASE_URL",
        "DATABASE_PUBLIC_URL",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "PGDATA",
        "SSL_CERT_DAYS",
    )
    variables = {key: service_ref(STAGING_SERVICE, key) for key in keys}
    data = stage1.gql(
        """
        mutation Q($input:ServiceCreateInput!) {
          serviceCreate(input:$input) { id name }
        }
        """,
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "name": TARGET_SERVICE,
                "variables": variables,
            }
        },
    )
    service = data.get("serviceCreate")
    if not isinstance(service, dict):
        raise PromotionError("Compatibility postgres service creation failed")
    if service.get("name") != TARGET_SERVICE or not service.get("id"):
        raise PromotionError("Compatibility postgres service metadata invalid")
    return str(service["id"])


def verify_compat_alias(
    real_service_id: str,
    alias_service_id: str,
    volume_instance_id: str,
) -> None:
    data = stage1.gql(
        """
        query Q {
          projectToken {
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
    project = ((data.get("projectToken") or {}).get("project") or {})
    services = stage1.nodes(project.get("services"))
    by_name = {str(row.get("name")): row for row in services if row.get("name")}
    real = by_name.get(STAGING_SERVICE)
    alias = by_name.get(TARGET_SERVICE)
    if not real or str(real.get("id") or "") != real_service_id:
        raise PromotionError("Real postgres-recovery service identity mismatch")
    if not alias or str(alias.get("id") or "") != alias_service_id:
        raise PromotionError("Compatibility postgres service identity mismatch")
    if real_service_id == alias_service_id:
        raise PromotionError("Compatibility service unexpectedly reused real DB service ID")

    found_volume = None
    alias_has_volume = False
    for volume in stage1.nodes(project.get("volumes")):
        for inst in stage1.nodes(volume.get("volumeInstances")):
            if str(inst.get("serviceId") or "") == alias_service_id:
                alias_has_volume = True
            if str(inst.get("id") or "") == volume_instance_id:
                found_volume = inst

    if alias_has_volume:
        raise PromotionError("Compatibility postgres service must not own a volume")
    if not found_volume:
        raise PromotionError("Preserved postgres volume instance missing after alias creation")
    if str(found_volume.get("serviceId") or "") != real_service_id:
        raise PromotionError("Preserved postgres volume moved away from real DB service")
    if found_volume.get("state") != "READY":
        raise PromotionError("Preserved postgres volume is not READY")
    if found_volume.get("mountPath") != stage1.EXPECTED_MOUNT:
        raise PromotionError("Preserved postgres mount path changed")

    latest_deployment(real_service_id)
    stage1.guard_known_backup(volume_instance_id)


def main() -> int:
    lines = [
        "## Railway Postgres recovery Stage 2",
        "",
        "Promotion scope: compatibility namespace plus public endpoint restoration.",
        "No Production consumer Variable is edited by this command.",
        "",
    ]
    proxy_id: str | None = None
    alias_created = False

    try:
        context = resolve_context(STAGING_SERVICE, TARGET_SERVICE)
        _, snapshot = stage1.resolve_deleted_deployment_and_snapshot(
            context["project_id"],
            context["environment_id"],
        )
        lines += [
            "### Promotion preflight",
            "",
            "- postgres absent: PASS",
            "- postgres-recovery present: PASS",
            "- postgres-volume attached to recovery service: PASS",
            "- preserved backup: PASS",
            "- exact deleted PostgreSQL 18 digest: PASS",
            f"- volume current size MB: {safe(context['volume_current_size_mb'])}",
            "",
        ]

        proxy = create_tcp_proxy(context["environment_id"], context["service_id"])
        proxy_id = str(proxy["id"])
        restore_public_url(
            context["project_id"],
            context["environment_id"],
            context["service_id"],
        )
        lines += [
            "### Public endpoint restoration",
            "",
            "- TCP proxy created for recovered Postgres: YES",
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

        # Project Tokens cannot rename services. Restore the historical "postgres"
        # variable namespace with an empty service whose values are references to the
        # still-running real DB service. No DB process or volume is moved/restarted.
        alias_service_id = create_compat_alias(
            context["project_id"],
            context["environment_id"],
        )
        alias_created = True
        verify_compat_alias(
            context["service_id"],
            alias_service_id,
            context["volume_instance_id"],
        )

        lines += [
            "### Promotion result",
            "",
            "- Real DB service postgres-recovery remained unchanged: YES",
            "- Compatibility service name postgres created: YES",
            "- Compatibility service owns no volume: YES",
            "- postgres-volume remained on postgres-recovery: YES",
            "- PostgreSQL deployment remained SUCCESS on pinned digest: YES",
            "- Existing backup guard after alias creation: PASS",
            "- Compatibility DB variables are Railway references only: YES",
            "- Production consumer Variable values: NOT EDITED",
            "",
            "**STAGE2_PROMOTION_PASS_VERIFY_CONSUMERS**",
            "",
            "- Keep the restored TCP proxy; it provides the recovered public Postgres endpoint.",
            "- Next required step is read-only DATABASE_URL resolution and operational health checks.",
            "- Do not change model/LINE/BUY-WATCH-SKIP/N01/N02/Bao/thresholds or PR #169.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        cleanup = "NOT_NEEDED"
        if proxy_id and not alias_created:
            try:
                stage1.delete_tcp_proxy(proxy_id)
                cleanup = "SUCCESS"
            except Exception:
                cleanup = "FAILED"

        safe_error = str(exc) if isinstance(exc, (PromotionError, stage1.RecoveryError)) else type(exc).__name__
        lines += [
            "",
            "### Stage 2 failure",
            "",
            f"- Error class: {safe(type(exc).__name__)}",
            f"- Safe error: {safe(safe_error)}",
            f"- Compatibility postgres service already created: {'YES' if alias_created else 'NO'}",
            f"- Pre-alias TCP proxy cleanup: {cleanup}",
            "",
            "**STAGE2_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- No automatic deletion of a created compatibility service is attempted.",
            "- Do not redeploy Production consumers until read-only reference checks pass.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
