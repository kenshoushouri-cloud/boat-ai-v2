#!/usr/bin/env python3
"""Guarded Railway Postgres recovery Stage 2 promotion.

Stage 2 promotes the already-audited isolated service without moving the volume:
1. Verify postgres is absent and postgres-recovery is the audited service.
2. Re-check preserved volume, backup, deployment digest, and credentials.
3. Create a TCP proxy on postgres-recovery.
4. Restore DATABASE_PUBLIC_URL as Railway dynamic references.
5. Re-run read-only DB integrity audit while still isolated.
6. Rename the SAME service ID from postgres-recovery to postgres.
7. Verify service identity, volume attachment, deployment digest and backup again.

No Production consumer Variable is edited here. Existing ${{postgres.DATABASE_URL}}
references are expected to resolve by service-name restoration. Consumer redeploys are
performed separately only after post-promotion read-only verification.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
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


def rename_service(service_id: str) -> None:
    query = """
    mutation Q($id:String!, $input:ServiceUpdateInput!) {
      serviceUpdate(id:$id, input:$input) { id name }
    }
    """
    req = urllib.request.Request(
        stage1.ENDPOINT,
        data=json.dumps({
            "query": query,
            "variables": {"id": service_id, "input": {"name": TARGET_SERVICE}},
        }).encode("utf-8"),
        method="POST",
        headers={
            "Project-Access-Token": stage1.TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "boat-ai-v2-postgres-recovery-stage2",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise PromotionError(
            "Service rename request failed: " + type(exc).__name__
        ) from None

    errors = payload.get("errors") or []
    if errors:
        text = " ".join(
            str(item.get("message") or "").lower()
            for item in errors
            if isinstance(item, dict)
        )
        if any(word in text for word in ("already exists", "already in use", "duplicate", "taken")):
            reason = "name_conflict"
        elif any(word in text for word in ("not authorized", "unauthorized", "permission", "forbidden")):
            reason = "not_authorized"
        elif any(word in text for word in ("invalid", "validation", "bad user input")):
            reason = "invalid_input"
        else:
            reason = "other_graphql_rejection"
        raise PromotionError("Service rename GraphQL rejected: " + reason)

    data = payload.get("data")
    if not isinstance(data, dict):
        raise PromotionError("Service rename returned no data")
    service = data.get("serviceUpdate")
    if not isinstance(service, dict):
        raise PromotionError("Service rename failed")
    if str(service.get("id") or "") != service_id:
        raise PromotionError("Service identity changed during rename")
    if service.get("name") != TARGET_SERVICE:
        raise PromotionError("Service rename did not produce postgres")


def main() -> int:
    lines = [
        "## Railway Postgres recovery Stage 2",
        "",
        "Promotion scope: same-service rename plus public endpoint restoration.",
        "No Production consumer Variable is edited by this command.",
        "",
    ]
    proxy_id: str | None = None
    renamed = False

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

        # Rename is intentionally the LAST promotion mutation. The service ID and
        # attached volume remain unchanged; only the Railway service name is restored.
        rename_service(context["service_id"])
        renamed = True

        post = resolve_context(TARGET_SERVICE, STAGING_SERVICE)
        if post["service_id"] != context["service_id"]:
            raise PromotionError("Post-promotion service ID mismatch")
        if post["volume_instance_id"] != context["volume_instance_id"]:
            raise PromotionError("Post-promotion volume identity mismatch")

        lines += [
            "### Promotion result",
            "",
            "- Same Railway service ID preserved: YES",
            "- Service name restored to postgres: YES",
            "- postgres-recovery name removed: YES",
            "- postgres-volume remained attached: YES",
            "- PostgreSQL deployment remained SUCCESS on pinned digest: YES",
            "- Existing backup guard after rename: PASS",
            "- Production consumer Variable values: NOT EDITED",
            "",
            "**STAGE2_PROMOTION_PASS_VERIFY_CONSUMERS**",
            "",
            "- Keep the restored TCP proxy; it replaces the original public Postgres endpoint.",
            "- Next required step is read-only DATABASE_URL resolution and operational health checks.",
            "- Do not change model/LINE/BUY-WATCH-SKIP/N01/N02/Bao/thresholds or PR #169.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        cleanup = "NOT_NEEDED"
        if proxy_id and not renamed:
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
            f"- Service rename already happened: {'YES' if renamed else 'NO'}",
            f"- Pre-rename TCP proxy cleanup: {cleanup}",
            "",
            "**STAGE2_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- No automatic rollback of a completed service rename is attempted.",
            "- Do not redeploy Production consumers until read-only reference checks pass.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
