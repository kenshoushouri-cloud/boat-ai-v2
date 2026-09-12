# -*- coding: utf-8 -*-
"""Read-only Railway backup metadata audit for storage-retention research.

This script sends GraphQL queries only. It never creates, restores, deletes, or
mutates a Railway backup, backup schedule, volume, service, deployment,
variable, or database row. It prints no IDs, URLs, credentials, or token values.
"""
from __future__ import annotations

import json
import os
import urllib.request


ENDPOINT = "https://backboard.railway.com/graphql/v2"
TOKEN = os.environ.get("RAILWAY_TOKEN", "")
TARGET_VOLUME = "postgres-volume"
TARGET_SERVICE = "postgres-recovery"


def gql(query: str, variables: dict | None = None) -> dict:
    if not TOKEN:
        raise RuntimeError("RAILWAY_TOKEN missing")
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        method="POST",
        headers={
            "Project-Access-Token": TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "boat-ai-v2-storage-retention-backup-readonly",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError("Railway GraphQL query failed")
    return payload.get("data") or {}


def nodes(connection: dict | None) -> list[dict]:
    if not isinstance(connection, dict):
        return []
    return [
        edge["node"]
        for edge in (connection.get("edges") or [])
        if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
    ]


def main() -> None:
    context = gql(
        """
        query {
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
                          id createdAt deletedAt state isPendingDeletion serviceId
                          currentSizeMB sizeMB mountPath region
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
    project = ((context.get("projectToken") or {}).get("project") or {})
    services = {row.get("id"): row for row in nodes(project.get("services"))}

    instance = None
    for volume in nodes(project.get("volumes")):
        if volume.get("name") != TARGET_VOLUME:
            continue
        candidates = [
            row for row in nodes(volume.get("volumeInstances"))
            if not row.get("deletedAt") and row.get("isPendingDeletion") is not True
        ]
        candidates.sort(key=lambda row: row.get("createdAt") or "", reverse=True)
        for row in candidates:
            service = services.get(row.get("serviceId")) or {}
            if service.get("name") == TARGET_SERVICE:
                instance = row
                break
        if instance is None and candidates:
            instance = candidates[0]
        break

    print("STORAGE_RETENTION_BACKUP_AUDIT_MODE=READ_ONLY_NO_MUTATION")
    if instance is None or not instance.get("id"):
        print("STORAGE_RETENTION_BACKUP_VOLUME=NOT_RESOLVED")
        print("STORAGE_RETENTION_BACKUP_RESULT=BLOCK_NO_VOLUME_INSTANCE")
        return

    backups_data = gql(
        """
        query Q($id:String!) {
          volumeInstanceBackupList(volumeInstanceId:$id) {
            createdAt expiresAt name referencedMB usedMB volumeInstanceSizeMB
          }
        }
        """,
        {"id": instance["id"]},
    )
    backups = [
        row
        for row in (backups_data.get("volumeInstanceBackupList") or [])
        if isinstance(row, dict)
    ]
    backups.sort(key=lambda row: row.get("createdAt") or "", reverse=True)

    schedules_data = gql(
        """
        query Q($id:String!) {
          volumeInstanceBackupScheduleList(volumeInstanceId:$id) {
            createdAt cron kind name retentionSeconds
          }
        }
        """,
        {"id": instance["id"]},
    )
    schedules = [
        row
        for row in (schedules_data.get("volumeInstanceBackupScheduleList") or [])
        if isinstance(row, dict)
    ]
    schedules.sort(
        key=lambda row: (str(row.get("kind") or ""), str(row.get("name") or ""))
    )

    print(
        "STORAGE_RETENTION_BACKUP_VOLUME="
        f"resolved:true service_match:{str((services.get(instance.get('serviceId')) or {}).get('name') == TARGET_SERVICE).lower()} "
        f"state:{instance.get('state')} size_mb:{instance.get('sizeMB')} current_size_mb:{instance.get('currentSizeMB')}"
    )
    print(f"STORAGE_RETENTION_BACKUP_COUNT={len(backups)}")
    for index, row in enumerate(backups[:10], start=1):
        safe_name = str(row.get("name") or "unnamed").replace("\n", " ").replace("\r", " ")
        print(
            "STORAGE_RETENTION_BACKUP="
            f"rank:{index} name:{safe_name} created_at:{row.get('createdAt')} "
            f"expires_at:{row.get('expiresAt')} referenced_mb:{row.get('referencedMB')} "
            f"used_mb:{row.get('usedMB')} volume_size_mb:{row.get('volumeInstanceSizeMB')}"
        )

    print(f"STORAGE_RETENTION_BACKUP_SCHEDULE_COUNT={len(schedules)}")
    if not schedules:
        print("STORAGE_RETENTION_BACKUP_SCHEDULE=NONE")
    for index, row in enumerate(schedules, start=1):
        safe_name = str(row.get("name") or "unnamed").replace("\n", " ").replace("\r", " ")
        safe_kind = str(row.get("kind") or "unknown").replace("\n", " ").replace("\r", " ")
        safe_cron = str(row.get("cron") or "-").replace("\n", " ").replace("\r", " ")
        print(
            "STORAGE_RETENTION_BACKUP_SCHEDULE="
            f"rank:{index} kind:{safe_kind} name:{safe_name} cron:{safe_cron} "
            f"retention_seconds:{row.get('retentionSeconds')} created_at:{row.get('createdAt')}"
        )

    print(
        "STORAGE_RETENTION_BACKUP_RESULT="
        + ("PASS_METADATA_VISIBLE" if backups else "BLOCK_NO_BACKUP_VISIBLE")
    )


if __name__ == "__main__":
    main()
