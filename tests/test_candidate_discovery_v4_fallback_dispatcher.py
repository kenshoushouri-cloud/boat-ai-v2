# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.candidate_discovery_v4_fallback_dispatcher import (
    FallbackDispatchError,
    HttpResult,
    decide_dispatch,
    execute_dispatch,
    WORKFLOW_ID,
)

JST = timezone(timedelta(hours=9))
REPO = "owner/private-repo"


class FakeTransport:
    def __init__(self, *, runs_status=200, runs=None, artifacts=None, dispatch_status=204):
        self.runs_status = runs_status
        self.runs = runs or []
        self.artifacts = artifacts or {}
        self.dispatch_status = dispatch_status
        self.calls = []

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        if method == "GET" and path.endswith("/artifacts"):
            run_id = path.split("/")[-2]
            return HttpResult(
                200,
                {"artifacts": self.artifacts.get(run_id, [])},
            )
        if method == "GET":
            return HttpResult(
                self.runs_status,
                {"workflow_runs": self.runs} if self.runs_status == 200 else None,
            )
        if method == "POST":
            return HttpResult(self.dispatch_status, None)
        raise AssertionError((method, path, body))


def observed(hh=8, mm=25, ss=0):
    return datetime(2026, 9, 21, hh, mm, ss, tzinfo=JST)


def run(*, run_id, event, created, status="completed", conclusion="success"):
    return {
        "id": run_id,
        "event": event,
        "created_at": created,
        "status": status,
        "conclusion": conclusion,
    }


def test_before_checkpoint_never_calls_github():
    tx = FakeTransport()
    result = decide_dispatch(
        repo=REPO,
        observed_at_jst=observed(8, 24, 59),
        transport=tx,
    )
    assert result.action == "NOT_DUE"
    assert result.should_dispatch is False
    assert tx.calls == []


def test_valid_primary_artifact_forces_noop():
    primary = run(
        run_id=101,
        event="schedule",
        created="2026-09-20T23:16:20Z",
    )
    tx = FakeTransport(
        runs=[primary],
        artifacts={
            "101": [
                {
                    "name": "candidate-discovery-v4-prospective-freeze-101",
                    "expired": False,
                }
            ]
        },
    )
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "NOOP_VALID_PRIMARY"
    assert result.primary_run_id == "101"
    assert [call[0] for call in tx.calls] == ["GET", "GET"]


def test_successful_primary_without_artifact_does_not_suppress_fallback():
    primary = run(
        run_id=102,
        event="schedule",
        created="2026-09-20T23:16:20Z",
    )
    tx = FakeTransport(runs=[primary], artifacts={"102": []})
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "DISPATCH_FALLBACK"
    posts = [call for call in tx.calls if call[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2] == {
        "ref": "main",
        "inputs": {"target_date": "2026-09-21"},
    }


def test_failed_or_late_primary_does_not_suppress_fallback():
    failed = run(
        run_id=103,
        event="schedule",
        created="2026-09-20T23:17:00Z",
        conclusion="failure",
    )
    future = run(
        run_id=104,
        event="schedule",
        created="2026-09-20T23:26:00Z",
    )
    tx = FakeTransport(runs=[future, failed])
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "DISPATCH_FALLBACK"
    assert sum(call[0] == "POST" for call in tx.calls) == 1


def test_existing_same_day_dispatch_prevents_retry_even_if_failed():
    previous = run(
        run_id=201,
        event="workflow_dispatch",
        created="2026-09-20T23:25:05Z",
        conclusion="failure",
    )
    tx = FakeTransport(runs=[previous])
    result = execute_dispatch(
        repo=REPO,
        observed_at_jst=observed(8, 26),
        transport=tx,
    )
    assert result.action == "NOOP_FALLBACK_ALREADY_DISPATCHED"
    assert result.previous_dispatch_run_id == "201"
    assert not any(call[0] == "POST" for call in tx.calls)


def test_previous_day_dispatch_does_not_block_today():
    previous = run(
        run_id=202,
        event="workflow_dispatch",
        created="2026-09-19T23:25:05Z",
    )
    tx = FakeTransport(runs=[previous])
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "DISPATCH_FALLBACK"
    assert sum(call[0] == "POST" for call in tx.calls) == 1


def test_primary_observability_failure_attempts_single_fallback():
    tx = FakeTransport(runs_status=503)
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "DISPATCH_FALLBACK"
    assert result.reason == "primary_observability_unavailable_attempt_fallback"
    assert sum(call[0] == "POST" for call in tx.calls) == 1


def test_dispatch_http_200_success_is_accepted():
    tx = FakeTransport(dispatch_status=200)
    result = execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    assert result.action == "DISPATCH_FALLBACK"
    assert sum(call[0] == "POST" for call in tx.calls) == 1


def test_dispatch_contract_matches_guarded_workflow():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / WORKFLOW_ID).read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "target_date:" in workflow
    assert "required: true" in workflow
    assert "github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'" in workflow
    assert "DISPATCH_TARGET_DATE: ${{ inputs.target_date }}" in workflow
    assert "candidate-discovery-v4-prospective-freeze-${{ github.run_id }}" in workflow


def test_dispatch_http_failure_fails_closed():
    tx = FakeTransport(dispatch_status=403)
    try:
        execute_dispatch(repo=REPO, observed_at_jst=observed(), transport=tx)
    except FallbackDispatchError as exc:
        assert "HTTP status 403" in str(exc)
        return
    raise AssertionError("expected FallbackDispatchError")


def test_non_jst_time_is_rejected():
    tx = FakeTransport()
    try:
        decide_dispatch(
            repo=REPO,
            observed_at_jst=datetime(2026, 9, 21, 8, 25, tzinfo=timezone.utc),
            transport=tx,
        )
    except ValueError:
        assert tx.calls == []
        return
    raise AssertionError("expected ValueError")


def test_future_created_run_is_not_observable():
    future = run(
        run_id=301,
        event="workflow_dispatch",
        created="2026-09-20T23:25:01Z",
    )
    tx = FakeTransport(runs=[future])
    result = execute_dispatch(
        repo=REPO,
        observed_at_jst=observed(8, 25, 0),
        transport=tx,
    )
    assert result.action == "DISPATCH_FALLBACK"
    assert sum(call[0] == "POST" for call in tx.calls) == 1
