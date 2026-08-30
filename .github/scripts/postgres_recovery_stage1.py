#!/usr/bin/env python3
"""
Stage 1 Railway Postgres recovery.

This script is intentionally mutating and MUST only be invoked by the owner-only,
exact-confirmation GitHub Actions workflow. It performs a guarded, isolated recovery:

1. Re-run recovery preflight guards.
2. Re-verify the preserved Pre-Security-Patch Backup immediately before volume mutation.
3. Create an isolated service named postgres-recovery without reconnecting Production.
4. Attach the preserved postgres-volume.
5. Configure the exact original PostgreSQL 18 image/runtime settings.
6. Start the staging service.
7. Create a temporary TCP proxy.
8. Run read-only DB integrity checks.
9. Remove the temporary TCP proxy.
10. Leave postgres-recovery isolated for manual promotion review.

No new manual volume backup is created in Stage 1. The preserved volume currently
exceeds Railway's documented 50%-of-capacity manual-backup threshold, so Stage 1
relies on the already-existing independently guarded backup instead of issuing a
backup mutation that is expected to be rejected.

It never renames the service to postgres and never edits Production consumer Variables.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://backboard.railway.com/graphql/v2"
TOKEN = os.environ.get("RAILWAY_TOKEN", "")
TARGET_SERVICE = "postgres"
STAGING_SERVICE = "postgres-recovery"
TARGET_VOLUME = "postgres-volume"

EXPECTED_IMAGE = "ghcr.io/railwayapp-templates/postgres-ssl:18"
EXPECTED_DIGEST = "sha256:e617e80d34d40def28ab197662197acc5cd6c1dc120db9cf38d835a2386c226c"
EXPECTED_MOUNT = "/var/lib/postgresql/data"
EXPECTED_PGDATA = "/var/lib/postgresql/data/pgdata"
EXPECTED_REGION = "us-west2"
EXPECTED_SIZE_MB = 5000
KNOWN_BACKUP_NAME = "Pre-Security-Patch Backup"
KNOWN_BACKUP_REFERENCED_MB = 3582

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class RecoveryError(RuntimeError):
    pass


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    if not TOKEN:
        raise RecoveryError("RAILWAY_TOKEN missing")
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        method="POST",
        headers={
            "Project-Access-Token": TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "boat-ai-v2-postgres-recovery-stage1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RecoveryError(f"Railway GraphQL request failed: {type(exc).__name__}") from None

    if payload.get("errors"):
        raise RecoveryError("Railway GraphQL returned an error")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RecoveryError("Railway GraphQL returned no data")
    return data


def nodes(conn: Any) -> list[dict[str, Any]]:
    if not isinstance(conn, dict):
        return []
    out: list[dict[str, Any]] = []
    for edge in conn.get("edges") or []:
        if isinstance(edge, dict) and isinstance(edge.get("node"), dict):
            out.append(edge["node"])
    return out


def page(conn: Any) -> tuple[bool, str | None]:
    if not isinstance(conn, dict):
        return False, None
    info = conn.get("pageInfo") or {}
    return bool(info.get("hasNextPage")), info.get("endCursor")


def walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def contains_target(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(
            TARGET_SERVICE in str(key).lower() or contains_target(value)
            for key, value in obj.items()
        )
    if isinstance(obj, list):
        return any(contains_target(value) for value in obj)
    return isinstance(obj, str) and TARGET_SERVICE in obj.lower()


def extract_uuids(obj: Any) -> list[str]:
    out: list[str] = []

    def rec(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                rec(child)
        elif isinstance(value, list):
            for child in value:
                rec(child)
        elif isinstance(value, str) and UUID_RE.match(value) and value not in out:
            out.append(value)

    rec(obj)
    return out


def find_string(obj: Any, exact: str) -> bool:
    for item in walk(obj):
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if isinstance(value, str) and value == exact:
                return True
    return False


def ref(name: str) -> str:
    return "$" + "{{" + name + "}}"


def safe_detail(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_summary(lines: list[str]) -> None:
    Path("stage1-result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_context_and_volume() -> dict[str, Any]:
    query = """
    query RecoveryContext {
      projectToken {
        projectId
        environmentId
        project {
          services(first: 100) {
            edges { node { id name deletedAt } }
          }
          volumes(first: 100) {
            edges {
              node {
                id
                name
                volumeInstances(first: 100) {
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
    data = gql(query)
    token_obj = data.get("projectToken") or {}
    project_id = token_obj.get("projectId")
    environment_id = token_obj.get("environmentId")
    project = token_obj.get("project") or {}
    if not project_id or not environment_id:
        raise RecoveryError("Project/environment context unresolved")

    services = nodes(project.get("services"))
    names = {service.get("name") for service in services}
    if TARGET_SERVICE in names:
        raise RecoveryError("postgres service already exists")
    if STAGING_SERVICE in names:
        raise RecoveryError("postgres-recovery service already exists")

    volume = None
    volume_instance = None
    for item in nodes(project.get("volumes")):
        if item.get("name") != TARGET_VOLUME:
            continue
        volume = item
        instances = nodes(item.get("volumeInstances"))
        if instances:
            volume_instance = sorted(
                instances,
                key=lambda row: row.get("createdAt") or "",
                reverse=True,
            )[0]
        break

    if not volume or not volume_instance:
        raise RecoveryError("Preserved postgres-volume not resolved")

    guards = {
        "state": volume_instance.get("state") == "READY",
        "not_pending_deletion": (
            volume_instance.get("isPendingDeletion") is False
            and not volume_instance.get("deletedAt")
        ),
        "detached": not volume_instance.get("serviceId"),
        "mount_path": volume_instance.get("mountPath") == EXPECTED_MOUNT,
        "region": volume_instance.get("region") == EXPECTED_REGION,
        "configured_size": int(volume_instance.get("sizeMB") or 0) == EXPECTED_SIZE_MB,
        "data_size": float(volume_instance.get("currentSizeMB") or 0) >= 3500.0,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise RecoveryError("Volume preflight failed: " + ",".join(failed))

    return {
        "project_id": project_id,
        "environment_id": environment_id,
        "volume_id": volume.get("id"),
        "volume_instance_id": volume_instance.get("id"),
        "volume_current_size_mb": volume_instance.get("currentSizeMB"),
    }


def list_backups(volume_instance_id: str) -> list[dict[str, Any]]:
    query = """
    query Q($id:String!) {
      volumeInstanceBackupList(volumeInstanceId:$id) {
        createdAt
        expiresAt
        name
        referencedMB
        usedMB
        volumeInstanceSizeMB
      }
    }
    """
    data = gql(query, {"id": volume_instance_id})
    rows = data.get("volumeInstanceBackupList") or []
    return [row for row in rows if isinstance(row, dict)]


def parse_utc_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RecoveryError("Backup expiry timestamp missing")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise RecoveryError("Backup expiry timestamp invalid") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def guard_known_backup(volume_instance_id: str) -> dict[str, Any]:
    backups = list_backups(volume_instance_id)
    known = next(
        (row for row in backups if row.get("name") == KNOWN_BACKUP_NAME),
        None,
    )
    if not known:
        raise RecoveryError("Known Pre-Security-Patch Backup missing")

    expiry = parse_utc_timestamp(known.get("expiresAt"))
    referenced_mb = int(float(known.get("referencedMB") or 0))
    guards = {
        "not_expired": expiry > datetime.now(timezone.utc),
        "reference_size": referenced_mb == KNOWN_BACKUP_REFERENCED_MB,
    }
    failed = [name for name, ok in guards.items() if not ok]
    if failed:
        raise RecoveryError("Known backup guard failed: " + ",".join(failed))
    return known


def resolve_deleted_deployment_and_snapshot(
    project_id: str,
    environment_id: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    events_query = """
    query Q($p:String!, $e:String!, $a:String) {
      events(first:100, after:$a, projectId:$p, environmentId:$e) {
        pageInfo { hasNextPage endCursor }
        edges { node { action object payload activityPayload } }
      }
    }
    """
    removed_events: list[dict[str, Any]] = []
    after = None
    for _ in range(20):
        data = gql(
            events_query,
            {"p": project_id, "e": environment_id, "a": after},
        )
        conn = data.get("events") or {}
        for item in nodes(conn):
            if (
                str(item.get("action") or "").lower() == "removed"
                and str(item.get("object") or "") in ("Deployment", "ServiceInstance")
                and (
                    contains_target(item.get("payload"))
                    or contains_target(item.get("activityPayload"))
                )
            ):
                removed_events.append(item)
        more, cursor = page(conn)
        if not more or not cursor:
            break
        after = cursor

    if len(removed_events) < 2:
        raise RecoveryError("Deleted Postgres event evidence incomplete")

    candidate_ids: list[str] = []
    for event in removed_events:
        for raw in (event.get("payload"), event.get("activityPayload")):
            for value in extract_uuids(raw):
                if value not in candidate_ids:
                    candidate_ids.append(value)

    dep_query = """
    query Q($id:String!) {
      deployment(id:$id) {
        id
        snapshotId
        meta
      }
    }
    """
    deployment = None
    deployment_id = None
    for candidate in candidate_ids[:60]:
        try:
            data = gql(dep_query, {"id": candidate})
        except RecoveryError:
            continue
        dep = data.get("deployment")
        if not isinstance(dep, dict):
            continue
        meta = dep.get("meta")
        if (
            contains_target(meta)
            and find_string(meta, EXPECTED_IMAGE)
            and find_string(meta, EXPECTED_DIGEST)
        ):
            deployment = dep
            deployment_id = candidate
            break

    if not deployment or not deployment_id:
        raise RecoveryError("Exact deleted Postgres deployment not resolved")

    meta_text = json.dumps(deployment.get("meta"), ensure_ascii=False, sort_keys=True)
    if EXPECTED_MOUNT not in meta_text:
        raise RecoveryError("Original mount-path evidence missing")
    if EXPECTED_REGION not in meta_text:
        raise RecoveryError("Original region evidence missing")
    if "ON_FAILURE" not in meta_text:
        raise RecoveryError("Original restart-policy evidence missing")

    snap_query = """
    query Q($id:String!) {
      deploymentSnapshot(deploymentId:$id) {
        variables
      }
    }
    """
    snap = gql(snap_query, {"id": deployment_id}).get("deploymentSnapshot")
    if not isinstance(snap, dict) or not isinstance(snap.get("variables"), dict):
        raise RecoveryError("Original deployment snapshot variables unresolved")

    variables = snap["variables"]
    required = (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "PGDATA",
        "SSL_CERT_DAYS",
    )
    for key in required:
        if variables.get(key) in (None, ""):
            raise RecoveryError(f"Required recovery variable missing: {key}")
    if variables.get("PGDATA") != EXPECTED_PGDATA:
        raise RecoveryError("PGDATA mismatch")

    return deployment, {str(k): str(v) for k, v in variables.items()}


def build_recovery_variables(snapshot: dict[str, str]) -> dict[str, str]:
    return {
        "POSTGRES_USER": snapshot["POSTGRES_USER"],
        "POSTGRES_PASSWORD": snapshot["POSTGRES_PASSWORD"],
        "POSTGRES_DB": snapshot["POSTGRES_DB"],
        "PGDATA": snapshot["PGDATA"],
        "SSL_CERT_DAYS": snapshot["SSL_CERT_DAYS"],
        "PGUSER": ref("POSTGRES_USER"),
        "PGPASSWORD": ref("POSTGRES_PASSWORD"),
        "PGDATABASE": ref("POSTGRES_DB"),
        "PGHOST": ref("RAILWAY_PRIVATE_DOMAIN"),
        "PGPORT": "5432",
        "DATABASE_URL": (
            "postgresql://"
            + ref("PGUSER")
            + ":"
            + ref("POSTGRES_PASSWORD")
            + "@"
            + ref("RAILWAY_PRIVATE_DOMAIN")
            + ":5432/"
            + ref("PGDATABASE")
        ),
    }


def create_staging_service(
    project_id: str,
    environment_id: str,
    variables: dict[str, str],
) -> str:
    mutation = """
    mutation CreateRecoveryService($input:ServiceCreateInput!) {
      serviceCreate(input:$input) {
        id
        name
      }
    }
    """
    data = gql(
        mutation,
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "name": STAGING_SERVICE,
                "variables": variables,
            }
        },
    )
    service = data.get("serviceCreate")
    if not isinstance(service, dict) or service.get("name") != STAGING_SERVICE:
        raise RecoveryError("Staging service creation failed")
    service_id = service.get("id")
    if not service_id:
        raise RecoveryError("Staging service ID missing")
    return str(service_id)


def attach_volume(
    volume_id: str,
    environment_id: str,
    service_id: str,
) -> None:
    mutation = """
    mutation AttachRecoveryVolume(
      $volumeId:String!,
      $environmentId:String!,
      $input:VolumeInstanceUpdateInput!
    ) {
      volumeInstanceUpdate(
        volumeId:$volumeId,
        environmentId:$environmentId,
        input:$input
      )
    }
    """
    data = gql(
        mutation,
        {
            "volumeId": volume_id,
            "environmentId": environment_id,
            "input": {
                "serviceId": service_id,
                "mountPath": EXPECTED_MOUNT,
            },
        },
    )
    if data.get("volumeInstanceUpdate") is not True:
        raise RecoveryError("Volume attach mutation did not succeed")


def configure_staging_service(
    environment_id: str,
    service_id: str,
) -> None:
    mutation = """
    mutation ConfigureRecoveryService(
      $environmentId:String!,
      $serviceId:String!,
      $input:ServiceInstanceUpdateInput!
    ) {
      serviceInstanceUpdate(
        environmentId:$environmentId,
        serviceId:$serviceId,
        input:$input
      )
    }
    """
    input_payload = {
        "source": {"image": EXPECTED_IMAGE},
        "numReplicas": 1,
        "multiRegionConfig": {
            EXPECTED_REGION: {"numReplicas": 1},
        },
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10,
        "sleepApplication": False,
    }
    data = gql(
        mutation,
        {
            "environmentId": environment_id,
            "serviceId": service_id,
            "input": input_payload,
        },
    )
    if data.get("serviceInstanceUpdate") is not True:
        raise RecoveryError("Service configuration mutation did not succeed")


def wait_for_successful_deployment(service_id: str) -> dict[str, Any]:
    query = """
    query Q($id:String!) {
      service(id:$id) {
        name
        deployments(first:20) {
          edges {
            node {
              id
              createdAt
              status
              updatedAt
            }
          }
        }
      }
    }
    """
    terminal_bad = {"CRASHED", "FAILED", "REMOVED"}
    last_status = None
    for _ in range(36):
        data = gql(query, {"id": service_id})
        service = data.get("service") or {}
        deployments = nodes((service or {}).get("deployments"))
        if deployments:
            latest = sorted(
                deployments,
                key=lambda row: row.get("createdAt") or "",
                reverse=True,
            )[0]
            status = str(latest.get("status") or "")
            last_status = status
            if status == "SUCCESS":
                return latest
            if status in terminal_bad:
                raise RecoveryError(f"Staging deployment terminal status: {status}")
        time.sleep(5)
    raise RecoveryError(f"Staging deployment did not reach SUCCESS; last={last_status}")


def create_tcp_proxy(environment_id: str, service_id: str) -> dict[str, Any]:
    mutation = """
    mutation CreateRecoveryProxy($input:TCPProxyCreateInput!) {
      tcpProxyCreate(input:$input) {
        id
        applicationPort
        domain
        proxyPort
        syncStatus
      }
    }
    """
    data = gql(
        mutation,
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
        raise RecoveryError("Temporary TCP proxy creation failed")
    if not proxy.get("id") or not proxy.get("domain") or not proxy.get("proxyPort"):
        raise RecoveryError("Temporary TCP proxy metadata incomplete")
    return proxy


def delete_tcp_proxy(proxy_id: str) -> None:
    mutation = """
    mutation DeleteRecoveryProxy($id:String!) {
      tcpProxyDelete(id:$id)
    }
    """
    data = gql(mutation, {"id": proxy_id})
    if data.get("tcpProxyDelete") is not True:
        raise RecoveryError("Temporary TCP proxy cleanup failed")


def run_db_integrity_audit(
    proxy: dict[str, Any],
    snapshot: dict[str, str],
) -> dict[str, Any]:
    try:
        import psycopg2
    except Exception:
        raise RecoveryError("psycopg2 unavailable") from None

    host = str(proxy["domain"])
    port = int(proxy["proxyPort"])

    conn = None
    last_error = None
    for _ in range(24):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=snapshot["POSTGRES_DB"],
                user=snapshot["POSTGRES_USER"],
                password=snapshot["POSTGRES_PASSWORD"],
                sslmode="require",
                connect_timeout=10,
                options="-c default_transaction_read_only=on",
            )
            break
        except Exception as exc:
            last_error = type(exc).__name__
            time.sleep(5)

    if conn is None:
        raise RecoveryError(f"Database connection failed: {last_error}")

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            server_version = str(cur.fetchone()[0])

            cur.execute(
                "SELECT current_database(), pg_is_in_recovery(), "
                "pg_database_size(current_database())"
            )
            current_db, in_recovery, db_size = cur.fetchone()

            core_tables = [
                "v2_races",
                "v2_race_entries",
                "v2_results",
                "v2_odds_trifecta",
            ]
            table_presence: dict[str, bool] = {}
            for table in core_tables:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                table_presence[table] = cur.fetchone()[0] is not None

            if not all(table_presence.values()):
                missing = [name for name, ok in table_presence.items() if not ok]
                raise RecoveryError("Core DB tables missing: " + ",".join(missing))

            cur.execute("SELECT COUNT(*) FROM public.v2_races")
            races = int(cur.fetchone()[0])

            cur.execute("SELECT COUNT(*) FROM public.v2_race_entries")
            entries = int(cur.fetchone()[0])

            cur.execute("SELECT COUNT(*) FROM public.v2_results")
            results = int(cur.fetchone()[0])

            cur.execute(
                "SELECT COALESCE(reltuples::bigint,0), "
                "pg_total_relation_size(oid) "
                "FROM pg_class "
                "WHERE oid='public.v2_odds_trifecta'::regclass"
            )
            odds_estimate, odds_size = cur.fetchone()
            odds_estimate = int(odds_estimate or 0)
            odds_size = int(odds_size or 0)

            cur.execute("SELECT MAX(race_date) FROM public.v2_races")
            max_race_date = cur.fetchone()[0]

        guards = {
            "postgres_major_18": server_version.startswith("18."),
            "not_in_recovery": in_recovery is False,
            "database_size": int(db_size or 0) >= 2_000_000_000,
            "v2_races_rows": races >= 10_000,
            "v2_race_entries_rows": entries >= 60_000,
            "v2_results_rows": results >= 10_000,
            "v2_odds_estimate": odds_estimate >= 500_000,
            "v2_odds_size": odds_size >= 500_000_000,
        }
        failed = [name for name, ok in guards.items() if not ok]
        if failed:
            raise RecoveryError("Database integrity guard failed: " + ",".join(failed))

        return {
            "server_version": server_version,
            "current_database": str(current_db),
            "in_recovery": bool(in_recovery),
            "database_size_bytes": int(db_size),
            "races": races,
            "entries": entries,
            "results": results,
            "odds_estimate": odds_estimate,
            "odds_size_bytes": odds_size,
            "max_race_date": str(max_race_date) if max_race_date else "-",
        }
    finally:
        conn.close()


def main() -> int:
    lines = [
        "## Railway Postgres recovery Stage 1",
        "",
        "This command performs the explicitly gated Stage 1 recovery only.",
        "It does not rename the staging service to postgres and does not reconnect Production consumers.",
        "",
    ]
    proxy_id = None
    stage_started = False

    try:
        context = resolve_context_and_volume()
        lines += [
            "### Preflight",
            "",
            "- Project/environment context: PASS",
            "- postgres absent: PASS",
            "- postgres-recovery absent: PASS",
            "- Preserved volume READY / detached / correct region+mount+size: PASS",
            f"- Preserved volume current size MB: {safe_detail(context['volume_current_size_mb'])}",
            "",
        ]

        known_backup = guard_known_backup(str(context["volume_instance_id"]))
        known_backup_expiry = safe_detail(known_backup.get("expiresAt") or "-")
        known_backup_ref = safe_detail(known_backup.get("referencedMB") or "-")
        lines += [
            "### Existing backup guard",
            "",
            f"- {KNOWN_BACKUP_NAME}: PRESENT / VALID",
            f"- Referenced MB: {known_backup_ref}",
            f"- Expires: {known_backup_expiry}",
            "",
        ]

        _, snapshot = resolve_deleted_deployment_and_snapshot(
            str(context["project_id"]),
            str(context["environment_id"]),
        )
        recovery_variables = build_recovery_variables(snapshot)

        service_id = create_staging_service(
            str(context["project_id"]),
            str(context["environment_id"]),
            recovery_variables,
        )
        stage_started = True
        lines += [
            "### Isolated staging service",
            "",
            "- postgres-recovery created: YES",
            "- Production service name postgres: NOT CREATED",
            "- Production consumer Variables: UNCHANGED",
            "",
        ]

        # Re-check the known independent backup immediately before the first
        # preserved-volume attachment mutation. Abort on expiry/size drift.
        guard_known_backup(str(context["volume_instance_id"]))

        attach_volume(
            str(context["volume_id"]),
            str(context["environment_id"]),
            service_id,
        )
        lines += [
            "- Preserved postgres-volume attached to staging: YES",
        ]

        configure_staging_service(
            str(context["environment_id"]),
            service_id,
        )
        wait_for_successful_deployment(service_id)
        lines += [
            "- PostgreSQL 18 staging deployment: SUCCESS",
            "",
        ]

        proxy = create_tcp_proxy(str(context["environment_id"]), service_id)
        proxy_id = str(proxy["id"])
        lines += [
            "### Temporary integrity-check access",
            "",
            "- Temporary TCP proxy: CREATED",
            "- Proxy host/port: NOT PUBLISHED",
            "",
        ]

        audit = run_db_integrity_audit(proxy, snapshot)
        lines += [
            "### Read-only database integrity audit",
            "",
            f"- PostgreSQL version: {safe_detail(audit['server_version'])}",
            f"- pg_is_in_recovery: {safe_detail(audit['in_recovery'])}",
            f"- Database size bytes: {safe_detail(audit['database_size_bytes'])}",
            f"- v2_races rows: {safe_detail(audit['races'])}",
            f"- v2_race_entries rows: {safe_detail(audit['entries'])}",
            f"- v2_results rows: {safe_detail(audit['results'])}",
            f"- v2_odds_trifecta estimated rows: {safe_detail(audit['odds_estimate'])}",
            f"- v2_odds_trifecta total bytes: {safe_detail(audit['odds_size_bytes'])}",
            f"- Latest v2_races race_date: {safe_detail(audit['max_race_date'])}",
            "",
        ]

        delete_tcp_proxy(proxy_id)
        proxy_id = None
        lines += [
            "- Temporary TCP proxy cleanup: SUCCESS",
            "",
            "### Stage 1 decision",
            "",
            "**STAGE1_PASS_AWAIT_MANUAL_PROMOTION_REVIEW**",
            "",
            "- postgres-recovery remains isolated with the preserved volume attached.",
            "- Production consumers remain disconnected because no service named postgres exists.",
            "- No Production cron/service Variable, model, threshold, LINE logic, N02/Bao setting, or PR #169 was changed.",
            "- Stage 2 promotion/rename must be a separate explicit review.",
        ]
        write_summary(lines)
        return 0

    except Exception as exc:
        error_name = type(exc).__name__
        error_text = str(exc)
        safe_error = error_text if isinstance(exc, RecoveryError) else error_name

        cleanup = "NOT_NEEDED"
        if proxy_id:
            try:
                delete_tcp_proxy(proxy_id)
                cleanup = "SUCCESS"
            except Exception:
                cleanup = "FAILED"

        lines += [
            "",
            "### Stage 1 failure",
            "",
            f"- Error class: {safe_detail(error_name)}",
            f"- Safe error: {safe_detail(safe_error)}",
            f"- Temporary TCP proxy cleanup: {cleanup}",
            f"- Staging service may have been created: {'YES' if stage_started else 'NO'}",
            "",
            "**STAGE1_BLOCK_MANUAL_REVIEW_REQUIRED**",
            "",
            "- No service rename to postgres was attempted.",
            "- Production consumer Variables were not changed.",
            "- Do not issue Stage 2 promotion.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    sys.exit(main())
