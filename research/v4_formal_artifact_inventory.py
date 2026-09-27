# -*- coding: utf-8 -*-
"""Inventory all V4 prospective-freeze artifacts for the formal Forward period.

Provider runs/artifacts are enumerated read-only. Selection uses the arbitration
contract frozen before the 2026-09-16 primary and never reads race results,
payouts, odds, or Boat PostgreSQL.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import candidate_discovery_v4_capture_arbiter as arb

START = date(2026, 9, 16)
END = date.fromisoformat(os.getenv("V4_INVENTORY_END", "2026-09-27"))
RUN_LIST = Path(os.getenv("V4_INVENTORY_RUN_LIST", "v4-run-list.json"))
OUTPUT = Path(os.getenv("V4_INVENTORY_OUTPUT", "v4-formal-artifact-inventory.json"))
REPO = os.environ["GITHUB_REPOSITORY"]


def daterange(a: date, b: date):
    cur = a
    from datetime import timedelta
    while cur <= b:
        yield cur
        cur += timedelta(days=1)


def gh_json(endpoint: str) -> Any:
    cp = subprocess.run(
        ["gh", "api", endpoint],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(cp.stdout.decode("utf-8"))


def gh_bytes(endpoint: str) -> bytes:
    cp = subprocess.run(
        ["gh", "api", endpoint],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return cp.stdout


def parse_artifact(run: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any] | None:
    aid = int(meta["id"])
    raw_zip = gh_bytes(f"repos/{REPO}/actions/artifacts/{aid}/zip")
    digest = hashlib.sha256(raw_zip).hexdigest()
    expected_digest = str(meta.get("digest") or "").replace("sha256:", "").lower()
    if expected_digest and digest != expected_digest:
        raise RuntimeError(f"artifact archive digest mismatch: {aid}")

    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "a.zip"
        zp.write_bytes(raw_zip)
        with zipfile.ZipFile(zp) as zf:
            names = set(zf.namelist())
            required = {
                "candidate-discovery-v4-prospective-freeze.json",
                "candidate-discovery-v4-prospective-freeze.json.core.sha256",
            }
            if not required.issubset(names):
                return None
            payload = json.loads(zf.read("candidate-discovery-v4-prospective-freeze.json"))
            embedded_core = zf.read("candidate-discovery-v4-prospective-freeze.json.core.sha256").decode("utf-8").strip().split()[0]

    try:
        computed_core = arb.canonical_core_payload_sha256(payload)
    except Exception as exc:
        return {
            "artifact_id": aid,
            "run_id": int(run["databaseId"]),
            "event": str(run.get("event") or ""),
            "archive_sha256": digest,
            "parse_valid": False,
            "reject_reason": f"canonical:{type(exc).__name__}:{str(exc)[:300]}",
        }
    if embedded_core != computed_core:
        raise RuntimeError(f"embedded/computed core hash mismatch: {aid}")

    fp = payload.get("freeze_provenance") or {}
    summary = payload.get("summary") or {}
    try:
        target = date.fromisoformat(str(fp.get("target_date") or summary.get("date")))
    except Exception:
        return None
    if target < START or target > END:
        return None

    deadline_ok = False
    try:
        completed = datetime.fromisoformat(str(fp["completed_at_jst"]).replace("Z", "+00:00"))
        earliest = datetime.fromisoformat(str(fp["earliest_feed_deadline_at_jst"]).replace("Z", "+00:00"))
        deadline_ok = completed < earliest
    except Exception:
        deadline_ok = False

    capture = arb.capture_from_mapping({
        "channel": str(run.get("event") or ""),
        "provider_run_id": str(run["databaseId"]),
        "target_date": target.isoformat(),
        "generated_at_jst": payload.get("generated_at_jst"),
        "canonical_payload_sha256": computed_core,
        "prospective_evidence_eligible": payload.get("prospective_evidence_eligible"),
        "purchase_action": payload.get("purchase_action"),
        "promotion_allowed": payload.get("promotion_allowed"),
        "core_races": summary.get("core_races"),
        "core_tickets": summary.get("core_tickets"),
        "all_frozen_rows_pre_deadline": fp.get("all_frozen_rows_pre_deadline"),
    })

    return {
        "artifact_id": aid,
        "artifact_name": str(meta.get("name") or ""),
        "run_id": int(run["databaseId"]),
        "event": str(run.get("event") or ""),
        "run_conclusion": str(run.get("conclusion") or ""),
        "created_at": str(run.get("createdAt") or ""),
        "archive_sha256": digest,
        "core_sha256": computed_core,
        "target_date": target.isoformat(),
        "generated_at_jst": payload.get("generated_at_jst"),
        "completed_at_jst": fp.get("completed_at_jst"),
        "earliest_feed_deadline_at_jst": fp.get("earliest_feed_deadline_at_jst"),
        "deadline_ok": deadline_ok,
        "parse_valid": True,
        "capture": capture,
    }


def main() -> None:
    print("V4_INVENTORY_POLICY=ALL_RUNS_FROZEN_ARBITER_NO_RESULT_READ", flush=True)
    print("V4_INVENTORY_DB_READ=0 RESULT_READ=0 PAYOUT_READ=0 ODDS_READ=0", flush=True)
    print("V4_INVENTORY_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    runs = json.loads(RUN_LIST.read_text(encoding="utf-8"))
    if not isinstance(runs, list):
        raise RuntimeError("run list must be JSON array")

    artifacts_by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    scanned_runs = formal_artifacts = 0

    for run in runs:
        if not isinstance(run, dict) or not run.get("databaseId"):
            continue
        scanned_runs += 1
        rid = int(run["databaseId"])
        data = gh_json(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100")
        for meta in data.get("artifacts", []):
            name = str(meta.get("name") or "")
            if not name.startswith("candidate-discovery-v4-prospective-freeze-"):
                continue
            if bool(meta.get("expired")):
                continue
            formal_artifacts += 1
            parsed = parse_artifact(run, meta)
            if not parsed or not parsed.get("target_date"):
                continue
            artifacts_by_date[date.fromisoformat(parsed["target_date"])].append(parsed)

    days = []
    for day in daterange(START, END):
        candidates = artifacts_by_date.get(day, [])
        captures = [
            x["capture"]
            for x in candidates
            if x.get("parse_valid") and x.get("deadline_ok")
        ]
        result = arb.arbitrate_captures(captures, target_date=day)
        selected = None
        if result.formal_available and result.formal_capture is not None:
            fc = result.formal_capture
            matches = [
                x for x in candidates
                if x.get("parse_valid")
                and x.get("deadline_ok")
                and str(x["run_id"]) == fc.provider_run_id
                and x["core_sha256"] == fc.canonical_payload_sha256
                and x["generated_at_jst"] == fc.generated_at_jst.isoformat()
            ]
            if len(matches) != 1:
                # timezone formatting can differ but instant/hash/run remains unique.
                matches = [
                    x for x in candidates
                    if x.get("parse_valid")
                    and x.get("deadline_ok")
                    and str(x["run_id"]) == fc.provider_run_id
                    and x["core_sha256"] == fc.canonical_payload_sha256
                ]
            if len(matches) != 1:
                raise RuntimeError(f"selected artifact lookup ambiguous: {day}")
            selected = {k:v for k,v in matches[0].items() if k != "capture"}

        days.append({
            "date": day.isoformat(),
            "classification": result.classification,
            "selected": selected,
            "valid_capture_count": len(captures),
            "candidate_artifact_count": len(candidates),
            "duplicate_count": len(result.duplicate_copies),
            "later_diagnostic_count": len(result.later_diagnostics),
            "rejected_capture_count": len(result.rejected_captures) + sum(
                1 for x in candidates if not x.get("parse_valid") or not x.get("deadline_ok")
            ),
            "candidates": [
                {k:v for k,v in x.items() if k != "capture"}
                for x in candidates
            ],
        })

    out = {
        "contract": "v4_formal_artifact_inventory_v1",
        "period": {"start": START.isoformat(), "end": END.isoformat()},
        "scanned_runs": scanned_runs,
        "formal_artifacts_seen": formal_artifacts,
        "days": days,
        "formal_available_dates": [d["date"] for d in days if d["classification"] == "FORMAL_AVAILABLE"],
        "unavailable_dates": [d["date"] for d in days if d["classification"] != "FORMAL_AVAILABLE"],
        "safety": {
            "frozen_arbiter": True,
            "db_read": False,
            "result_read": False,
            "payout_read": False,
            "odds_read": False,
            "db_write": False,
            "line": False,
            "buy": False,
            "production_change": False,
            "promotion_allowed": False,
        },
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"V4_INVENTORY_SCANNED_RUNS={scanned_runs}", flush=True)
    print(f"V4_INVENTORY_FORMAL_ARTIFACTS_SEEN={formal_artifacts}", flush=True)
    print("V4_INVENTORY_DAYS=" + json.dumps([
        {
            "date": d["date"],
            "classification": d["classification"],
            "selected_run_id": d["selected"]["run_id"] if d["selected"] else None,
            "selected_artifact_id": d["selected"]["artifact_id"] if d["selected"] else None,
            "valid_capture_count": d["valid_capture_count"],
            "candidate_artifact_count": d["candidate_artifact_count"],
        }
        for d in days
    ], sort_keys=True), flush=True)
    print("V4_INVENTORY_FORMAL_AVAILABLE=" + json.dumps(out["formal_available_dates"]), flush=True)
    print("V4_INVENTORY_UNAVAILABLE=" + json.dumps(out["unavailable_dates"]), flush=True)
    print("V4_INVENTORY_PROMOTION_ALLOWED=0", flush=True)
    print("V4_INVENTORY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
