# -*- coding: utf-8 -*-
"""Independent-scheduler dispatcher for the V4 08:25 JST fallback.

Draft/research adapter only. Intended future topology:
Railway Cron (08:25 JST) -> GitHub workflow_dispatch -> existing guarded V4
prospective-freeze workflow.

This adapter never reads the Boat Production database and has no LINE/purchase
surface. It only observes GitHub workflow metadata/artifacts and, when needed,
creates at most one workflow_dispatch attempt for the current JST date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from typing import Any, Callable
from urllib import error, parse, request

JST = timezone(timedelta(hours=9))
CHECKPOINT = time(8, 25)
WORKFLOW_PATH = ".github/workflows/candidate-discovery-v4-prospective-freeze.yml"
PRIMARY_EVENT = "schedule"
FALLBACK_EVENT = "workflow_dispatch"


class FallbackDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResult:
    status: int
    data: Any


@dataclass(frozen=True)
class DispatchDecision:
    action: str
    should_dispatch: bool
    target_date: date
    primary_run_id: str | None = None
    previous_dispatch_run_id: str | None = None
    reason: str = ""


Transport = Callable[[str, str, dict[str, Any] | None], HttpResult]


def _require_jst(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != JST.utcoffset(value):
        raise ValueError("now_jst must be timezone-aware JST")


def _parse_github_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(JST)


def _run_is_same_target_day(run: dict[str, Any], target: date) -> bool:
    created = _parse_github_time(run.get("created_at"))
    return created is not None and created.date() == target


def _run_is_observable(run: dict[str, Any], observed_at_jst: datetime) -> bool:
    created = _parse_github_time(run.get("created_at"))
    return created is not None and created <= observed_at_jst


def _run_id(run: dict[str, Any]) -> str | None:
    value = run.get("id")
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and value:
        return value
    return None


def _has_valid_primary_artifact(
    *,
    repo: str,
    run: dict[str, Any],
    transport: Transport,
) -> bool:
    run_id = _run_id(run)
    if run_id is None:
        return False
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False
    result = transport(
        "GET",
        f"/repos/{repo}/actions/runs/{run_id}/artifacts",
        None,
    )
    if result.status != 200 or not isinstance(result.data, dict):
        return False
    artifacts = result.data.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    expected = f"candidate-discovery-v4-prospective-freeze-{run_id}"
    return any(
        isinstance(item, dict)
        and item.get("name") == expected
        and item.get("expired") is not True
        for item in artifacts
    )


def decide_dispatch(
    *,
    repo: str,
    observed_at_jst: datetime,
    transport: Transport,
) -> DispatchDecision:
    _require_jst(observed_at_jst)
    target = observed_at_jst.date()
    checkpoint_dt = datetime.combine(target, CHECKPOINT, tzinfo=JST)
    if observed_at_jst < checkpoint_dt:
        return DispatchDecision(
            action="NOT_DUE",
            should_dispatch=False,
            target_date=target,
            reason="before_0825_checkpoint",
        )

    workflow_ref = parse.quote(WORKFLOW_PATH, safe="")
    runs_endpoint = (
        f"/repos/{repo}/actions/workflows/{workflow_ref}/runs"
        "?branch=main&per_page=30"
    )
    runs_result = transport("GET", runs_endpoint, None)
    runs: list[dict[str, Any]] = []
    if runs_result.status == 200 and isinstance(runs_result.data, dict):
        raw_runs = runs_result.data.get("workflow_runs")
        if isinstance(raw_runs, list):
            runs = [row for row in raw_runs if isinstance(row, dict)]

    observable = [
        run
        for run in runs
        if _run_is_same_target_day(run, target)
        and _run_is_observable(run, observed_at_jst)
    ]

    primary_runs = [run for run in observable if run.get("event") == PRIMARY_EVENT]
    for run in sorted(
        primary_runs,
        key=lambda row: _parse_github_time(row.get("created_at"))
        or datetime.max.replace(tzinfo=JST),
    ):
        if _has_valid_primary_artifact(repo=repo, run=run, transport=transport):
            return DispatchDecision(
                action="NOOP_VALID_PRIMARY",
                should_dispatch=False,
                target_date=target,
                primary_run_id=_run_id(run),
                reason="completed_success_primary_artifact_observable",
            )

    prior_dispatches = [
        run
        for run in observable
        if run.get("event") == FALLBACK_EVENT
        and (_parse_github_time(run.get("created_at")) or checkpoint_dt) >= checkpoint_dt
    ]
    if prior_dispatches:
        first = min(
            prior_dispatches,
            key=lambda row: _parse_github_time(row.get("created_at"))
            or datetime.max.replace(tzinfo=JST),
        )
        return DispatchDecision(
            action="NOOP_FALLBACK_ALREADY_DISPATCHED",
            should_dispatch=False,
            target_date=target,
            previous_dispatch_run_id=_run_id(first),
            reason="single_fallback_attempt_per_target_date",
        )

    return DispatchDecision(
        action="DISPATCH_FALLBACK",
        should_dispatch=True,
        target_date=target,
        reason=(
            "no_valid_primary_artifact_observable"
            if runs_result.status == 200
            else "primary_observability_unavailable_attempt_fallback"
        ),
    )


def execute_dispatch(
    *,
    repo: str,
    observed_at_jst: datetime,
    transport: Transport,
) -> DispatchDecision:
    decision = decide_dispatch(
        repo=repo,
        observed_at_jst=observed_at_jst,
        transport=transport,
    )
    if not decision.should_dispatch:
        return decision

    workflow_ref = parse.quote(WORKFLOW_PATH, safe="")
    endpoint = f"/repos/{repo}/actions/workflows/{workflow_ref}/dispatches"
    result = transport(
        "POST",
        endpoint,
        {
            "ref": "main",
            "inputs": {"target_date": decision.target_date.isoformat()},
        },
    )
    if result.status != 204:
        raise FallbackDispatchError(
            f"workflow dispatch failed with HTTP status {result.status}"
        )
    return decision


def _github_transport(*, token: str) -> Transport:
    base = "https://api.github.com"

    def call(method: str, path: str, body: dict[str, Any] | None) -> HttpResult:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(
            base + path,
            data=payload,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "boat-ai-v4-fallback-dispatcher",
                **({"Content-Type": "application/json"} if payload is not None else {}),
            },
        )
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read()
                data = json.loads(raw) if raw else None
                return HttpResult(status=response.status, data=data)
        except error.HTTPError as exc:
            raw = exc.read()
            try:
                data = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                data = None
            return HttpResult(status=exc.code, data=data)
        except error.URLError as exc:
            raise FallbackDispatchError(
                f"github transport unavailable: {type(exc.reason).__name__}"
            ) from exc

    return call


def main() -> int:
    repo = os.environ.get("V4_FALLBACK_GITHUB_REPOSITORY", "")
    token = os.environ.get("V4_FALLBACK_GITHUB_TOKEN", "")
    if not repo or "/" not in repo:
        raise FallbackDispatchError("V4_FALLBACK_GITHUB_REPOSITORY is required")
    if not token:
        raise FallbackDispatchError("V4_FALLBACK_GITHUB_TOKEN is required")

    now = datetime.now(JST)
    decision = execute_dispatch(
        repo=repo,
        observed_at_jst=now,
        transport=_github_transport(token=token),
    )
    print(
        "V4_FALLBACK_DISPATCH "
        f"action={decision.action} target_date={decision.target_date.isoformat()} "
        f"primary_run_id={decision.primary_run_id or '-'} "
        f"previous_dispatch_run_id={decision.previous_dispatch_run_id or '-'} "
        f"reason={decision.reason}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
