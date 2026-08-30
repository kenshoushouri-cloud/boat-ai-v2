#!/usr/bin/env python3
"""Guarded Stage 2 consumer redeploy via Railway GraphQL.

Only the fixed services whose Railway CLI redeploy did not succeed are touched.
No variables, model settings, database resources, volumes, backups, or LINE settings are modified.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "postgres_recovery_stage1.py"
spec = importlib.util.spec_from_file_location("stage1", P)
if spec is None or spec.loader is None:
    raise RuntimeError("Stage 1 helper unavailable")
stage1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage1)

REAL_DB = "postgres-recovery"
COMPAT_DB = "postgres"
TARGETS = (
    "cron-daily-report",
    "cron-data-prepare",
    "cron-final-check",
    "cron-learning-all",
    "cron-nightly-results",
    "cron-racer-course-stats",
    "cron-window-day",
    "cron-window-morning",
    "cron-window-night",
    "test-beforeinfo-extra",
)

class RedeployError(RuntimeError):
    pass

def nodes(conn):
    return stage1.nodes(conn)

def main() -> int:
    lines = [
        "## Railway Postgres Stage 2 consumer GraphQL redeploy",
        "",
        "Only the fixed consumers whose CLI redeploy was not confirmed are redeployed.",
        "No Variable, database, volume, backup, model, LINE, N01/N02/Bao, or threshold is changed.",
        "",
    ]
    try:
        data = stage1.gql("""
        query Q {
          projectToken {
            environmentId
            project {
              services(first:100) { edges { node { id name deletedAt } } }
              volumes(first:100) {
                edges { node { name volumeInstances(first:100) {
                  edges { node { id serviceId state mountPath region sizeMB currentSizeMB deletedAt isPendingDeletion } }
                } } }
              }
            }
          }
        }
        """)
        token = data.get("projectToken") or {}
        env_id = token.get("environmentId")
        project = token.get("project") or {}
        if not env_id:
            raise RedeployError("Environment unresolved")
        services = {
            str(row.get("name")): row
            for row in nodes(project.get("services"))
            if row.get("name") and not row.get("deletedAt")
        }
        for name in (REAL_DB, COMPAT_DB, *TARGETS):
            if name not in services or not services[name].get("id"):
                raise RedeployError("Required service missing: " + name)

        real_id = str(services[REAL_DB]["id"])
        vol = None
        for v in nodes(project.get("volumes")):
            if v.get("name") != "postgres-volume":
                continue
            for inst in nodes(v.get("volumeInstances")):
                if str(inst.get("serviceId") or "") == real_id:
                    vol = inst
                    break
        if not vol:
            raise RedeployError("postgres-volume not attached to postgres-recovery")
        guards = (
            vol.get("state") == "READY",
            vol.get("isPendingDeletion") is False and not vol.get("deletedAt"),
            vol.get("mountPath") == stage1.EXPECTED_MOUNT,
            vol.get("region") == stage1.EXPECTED_REGION,
            int(vol.get("sizeMB") or 0) == stage1.EXPECTED_SIZE_MB,
            float(vol.get("currentSizeMB") or 0) >= 3500.0,
        )
        if not all(guards):
            raise RedeployError("Preserved volume guard failed")
        stage1.guard_known_backup(str(vol.get("id")))

        mutation = """
        mutation Q($environmentId:String!, $serviceId:String!) {
          serviceInstanceRedeploy(environmentId:$environmentId, serviceId:$serviceId)
        }
        """
        accepted = []
        for name in TARGETS:
            result = stage1.gql(mutation, {
                "environmentId": str(env_id),
                "serviceId": str(services[name]["id"]),
            })
            if result.get("serviceInstanceRedeploy") is not True:
                raise RedeployError("Redeploy mutation rejected: " + name)
            accepted.append(name)

        lines += [
            "### Result",
            "",
            f"- Redeploy accepted: **{len(accepted)}/{len(TARGETS)}**",
            "- postgres-recovery / postgres compatibility services: UNCHANGED",
            "- preserved volume / backup: UNCHANGED",
            "",
        ]
        lines.extend(f"- {name}" for name in accepted)
        lines += [
            "",
            "**STAGE2_REDEPLOY_ACCEPTED_VERIFY_HEALTH**",
            "",
            "- Next: read-only inventory, DB reference, today-health, and sanitized logs if needed.",
        ]
        Path("stage2-redeploy-result.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
        return 0
    except Exception as exc:
        msg = str(exc) if isinstance(exc, (RedeployError, stage1.RecoveryError)) else type(exc).__name__
        lines += [
            "### Failure", "", f"- Safe error: {msg}", "",
            "**STAGE2_REDEPLOY_BLOCK_MANUAL_REVIEW_REQUIRED**",
        ]
        Path("stage2-redeploy-result.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
        return 1

if __name__ == "__main__":
    sys.exit(main())
