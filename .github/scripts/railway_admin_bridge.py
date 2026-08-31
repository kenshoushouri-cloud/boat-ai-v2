#!/usr/bin/env python3
"""Guarded Railway admin bridge for production operations.

Read-only:
- deployments <service>
- cron-plan <service> "<5-field cron>"
- start-plan <service> <entry.py>
- var-plan <service> <KEY> <VALUE>

Guarded writes (require exact trailing CONFIRM):
- restart <service> CONFIRM
- cron-set <service> "<5-field cron>" CONFIRM
- start-set <service> <entry.py> CONFIRM
- var-set <service> <KEY> <VALUE> CONFIRM

Safety:
- postgres / postgres-recovery are read-only here
- no destructive service, volume, backup, restore, or rename operations
- no arbitrary shell
- no secret-like or model/LINE/threshold Variables
- Variable writes use --skip-deploys; redeploy is a separate approval
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any

VERSION = "2026-08-31 railway-admin-bridge-v1"
ISSUE_PREFIX = "/railway "
ENVIRONMENT = "production"
SUMMARY_PATH = Path("railway-admin-summary.md")

WRITE_SERVICES = {
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
}
READ_SERVICES = WRITE_SERVICES | {"postgres", "postgres-recovery"}
CRON_SERVICES = {
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
}

SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASS|API_KEY|PRIVATE|CREDENTIAL|AUTH|COOKIE|SESSION|"
    r"DATABASE|URL|URI|DSN|WEBHOOK|ACCESS_KEY|RAILWAY)",
    re.IGNORECASE,
)
MODEL_KEY_RE = re.compile(
    r"(PROB|BETA|COEFF|THRESH|MODEL|CALIBR|TEMP|N01|N02|BAO|BUY|WATCH|SKIP|"
    r"LINE|FINAL|EV_|ODDS_MIN|ODDS_MAX)",
    re.IGNORECASE,
)
VAR_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
CRON_FIELD_RE = re.compile(r"^[0-9*/,-]+$")
ENTRY_RE = re.compile(r"^[A-Za-z0-9_./-]+\.py$")


class AdminError(RuntimeError):
    pass


def write_summary(lines: list[str]) -> None:
    SUMMARY_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_cli(args: list[str]) -> str:
    proc = subprocess.run(
        ["railway", *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AdminError(f"Railway CLI command failed: {args[0]}")
    return proc.stdout


def service_guard(service: str, *, write: bool) -> None:
    allowed = WRITE_SERVICES if write else READ_SERVICES
    if service not in allowed:
        raise AdminError(f"unsupported service: {service}")
    if write and service in {"postgres", "postgres-recovery"}:
        raise AdminError("DB service mutation is forbidden by this bridge")


def validate_cron(value: str) -> str:
    value = value.strip()
    parts = value.split()
    if len(parts) != 5:
        raise AdminError("cron must have exactly 5 fields")
    if len(value) > 80 or any(not CRON_FIELD_RE.fullmatch(x) for x in parts):
        raise AdminError("cron contains unsupported characters")
    return " ".join(parts)


def validate_entry(entry: str) -> str:
    if not ENTRY_RE.fullmatch(entry) or ".." in entry or entry.startswith("/"):
        raise AdminError("entry must be a safe repository-relative .py path")
    root = Path.cwd().resolve()
    path = (root / entry).resolve()
    if root not in path.parents or not path.is_file():
        raise AdminError("entry script does not exist in the checked-out repository")
    return entry


def validate_variable(key: str, value: str) -> None:
    if not VAR_KEY_RE.fullmatch(key):
        raise AdminError("Variable key format is not allowed")
    if SECRET_KEY_RE.search(key):
        raise AdminError("secret-like Variable keys are not managed through Issue comments")
    if MODEL_KEY_RE.search(key):
        raise AdminError("model/LINE/threshold Variables are blocked by this bridge")
    if len(value) > 160 or any(ord(ch) < 32 for ch in value):
        raise AdminError("Variable value is too long or contains control characters")
    if "://" in value or "-----BEGIN" in value or "\n" in value or "\r" in value:
        raise AdminError("secret-like Variable value is not allowed through Issue comments")
    if re.fullmatch(r"[A-Za-z0-9+/=_-]{40,}", value or ""):
        raise AdminError("token-like Variable value is not allowed through Issue comments")


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def load_config() -> dict[str, Any]:
    raw = run_cli(["environment", "config", "--environment", ENVIRONMENT, "--json"])
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise AdminError("unexpected Railway environment config shape")
    return data


def candidate_for(obj: Any, service: str) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        direct = obj.get(service)
        if isinstance(direct, dict) and any(k in direct for k in ("build", "deploy", "source", "variables")):
            return direct
        marker = obj.get("serviceName") or obj.get("name")
        if marker == service and any(k in obj for k in ("build", "deploy", "source", "variables")):
            return obj
        for value in obj.values():
            found = candidate_for(value, service)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = candidate_for(value, service)
            if found is not None:
                return found
    return None


def nested(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def current_service_config(service: str) -> dict[str, Any]:
    svc = candidate_for(load_config(), service)
    if svc is None:
        raise AdminError(f"service config unresolved: {service}")
    return svc


def deployment_summary(service: str) -> list[str]:
    service_guard(service, write=False)
    raw = run_cli([
        "deployment", "list",
        "--service", service,
        "--environment", ENVIRONMENT,
        "--limit", "10",
        "--json",
    ])
    data = json.loads(raw)
    if not isinstance(data, list):
        raise AdminError("unexpected deployment list shape")
    lines = [
        "## Railway deployments",
        "",
        f"Service: `{service}`",
        "",
        "Read-only. Deployment IDs are intentionally omitted.",
        "",
        "| Status | Created |",
        "|---|---|",
    ]
    for row in data[:10]:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "-")[:32]
        created = str(row.get("createdAt") or row.get("created_at") or "-")[:40]
        lines.append(f"| {status} | {created} |")
    if len(lines) == 7:
        lines.append("| (none) | - |")
    return lines


def restart_service(service: str) -> list[str]:
    service_guard(service, write=True)
    run_cli(["restart", "--service", service, "--yes", "--json"])
    return [
        "## Railway restart",
        "",
        f"Service: `{service}`",
        "",
        "✅ Railway accepted the guarded restart.",
        "",
        "Existing deployment image is reused; no rebuild was requested.",
    ]


def cron_plan(service: str, cron: str) -> list[str]:
    service_guard(service, write=True)
    if service not in CRON_SERVICES:
        raise AdminError("cron mutation is restricted to existing cron services")
    cron = validate_cron(cron)
    svc = current_service_config(service)
    current = nested(svc, "deploy", "cronSchedule") or "(not set)"
    return [
        "## Railway cron plan",
        "",
        f"Service: `{service}`",
        f"Current: `{current}`",
        f"Proposed: `{cron}`",
        "",
        "Read-only plan. No Railway setting was changed.",
    ]


def cron_set(service: str, cron: str) -> list[str]:
    cron_plan(service, cron)
    cron = validate_cron(cron)
    run_cli([
        "environment", "edit",
        "--service-config", service,
        "deploy.cronSchedule", cron,
        "--message", "ops: guarded cron update",
        "--json",
    ])
    after = nested(current_service_config(service), "deploy", "cronSchedule")
    if after != cron:
        raise AdminError("cron postcondition verification failed")
    return [
        "## Railway cron update",
        "",
        f"Service: `{service}`",
        f"Cron: `{cron}`",
        "",
        "✅ Railway config postcondition verified.",
        "",
        "This is a service configuration change; Railway may create/apply a deployment according to its staged-change behavior.",
    ]


def start_plan(service: str, entry: str) -> list[str]:
    service_guard(service, write=True)
    entry = validate_entry(entry)
    proposed = f"python -u {entry}"
    current = nested(current_service_config(service), "deploy", "startCommand") or "(not set)"
    return [
        "## Railway Start Command plan",
        "",
        f"Service: `{service}`",
        f"Current: `{current}`",
        f"Proposed: `{proposed}`",
        "",
        "Read-only plan. Arbitrary shell commands are not accepted; only an existing repository .py entrypoint is allowed.",
    ]


def start_set(service: str, entry: str) -> list[str]:
    start_plan(service, entry)
    entry = validate_entry(entry)
    proposed = f"python -u {entry}"
    run_cli([
        "environment", "edit",
        "--service-config", service,
        "deploy.startCommand", proposed,
        "--message", "ops: guarded start command update",
        "--json",
    ])
    after = nested(current_service_config(service), "deploy", "startCommand")
    if after != proposed:
        raise AdminError("Start Command postcondition verification failed")
    return [
        "## Railway Start Command update",
        "",
        f"Service: `{service}`",
        f"Start Command: `{proposed}`",
        "",
        "✅ Railway config postcondition verified.",
    ]


def var_plan(service: str, key: str, value: str) -> list[str]:
    service_guard(service, write=True)
    validate_variable(key, value)
    return [
        "## Railway non-secret Variable plan",
        "",
        f"Service: `{service}`",
        f"Key: `{key}`",
        f"Value length: **{len(value)}**",
        f"Value fingerprint: `sha256:{fingerprint(value)}`",
        "",
        "Read-only plan. Value is intentionally not echoed.",
        "Secret-like and model/LINE/threshold Variable keys are blocked.",
    ]


def var_set(service: str, key: str, value: str) -> list[str]:
    var_plan(service, key, value)
    run_cli([
        "variable", "set", f"{key}={value}",
        "--service", service,
        "--environment", ENVIRONMENT,
        "--skip-deploys",
        "--json",
    ])
    raw = run_cli(["variable", "list", "--service", service, "--environment", ENVIRONMENT, "--json"])
    data = json.loads(raw)
    actual = None
    if isinstance(data, dict):
        actual = data.get(key)
    elif isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and (row.get("name") == key or row.get("key") == key):
                actual = row.get("value")
                break
    if str(actual) != value:
        raise AdminError("Variable postcondition verification failed")
    return [
        "## Railway non-secret Variable update",
        "",
        f"Service: `{service}`",
        f"Key: `{key}`",
        f"Value length: **{len(value)}**",
        f"Value fingerprint: `sha256:{fingerprint(value)}`",
        "",
        "✅ Variable postcondition verified.",
        "Deployment was deliberately skipped. Redeploy/restart requires a separate operation.",
    ]


def parse_command(command: str) -> tuple[str, list[str]]:
    if not command.startswith(ISSUE_PREFIX):
        raise AdminError("command must start with /railway")
    try:
        parts = shlex.split(command[len(ISSUE_PREFIX):])
    except ValueError as exc:
        raise AdminError("invalid quoting") from exc
    if not parts:
        raise AdminError("missing operation")
    return parts[0], parts[1:]


def execute(command: str) -> list[str]:
    op, args = parse_command(command)

    if op == "deployments" and len(args) == 1:
        return deployment_summary(args[0])
    if op == "restart" and len(args) == 2 and args[1] == "CONFIRM":
        return restart_service(args[0])

    if op == "cron-plan" and len(args) == 2:
        return cron_plan(args[0], args[1])
    if op == "cron-set" and len(args) == 3 and args[2] == "CONFIRM":
        return cron_set(args[0], args[1])

    if op == "start-plan" and len(args) == 2:
        return start_plan(args[0], args[1])
    if op == "start-set" and len(args) == 3 and args[2] == "CONFIRM":
        return start_set(args[0], args[1])

    if op == "var-plan" and len(args) == 3:
        return var_plan(args[0], args[1], args[2])
    if op == "var-set" and len(args) == 4 and args[3] == "CONFIRM":
        return var_set(args[0], args[1], args[2])

    raise AdminError("unsupported or malformed Railway admin command")


def self_test() -> int:
    assert parse_command('/railway cron-plan cron-window-day "35 0 * * *"')[1][1] == "35 0 * * *"
    assert validate_cron("*/15 23,0-14 * * *") == "*/15 23,0-14 * * *"
    try:
        validate_variable("DATABASE_URL", "x")
    except AdminError:
        pass
    else:
        raise AssertionError("DATABASE_URL must be blocked")
    try:
        validate_variable("PROB_TEMP", "2.2")
    except AdminError:
        pass
    else:
        raise AssertionError("model Variable must be blocked")
    validate_variable("WINDOW_WORKERS", "2")
    print("RAILWAY_ADMIN_SELF_TEST=PASS")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    command = os.getenv("ADMIN_COMMAND", "").strip()
    lines = [
        "## Railway admin bridge",
        "",
        f"Version: `{VERSION}`",
        "",
    ]
    try:
        result = execute(command)
        write_summary(result)
        return 0
    except Exception as exc:
        safe = str(exc) if isinstance(exc, AdminError) else type(exc).__name__
        lines += [
            "❌ Operation blocked or failed.",
            "",
            f"Safe error: `{safe}`",
            "",
            "No secret values are published.",
        ]
        write_summary(lines)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
