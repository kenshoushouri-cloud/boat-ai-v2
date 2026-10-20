# -*- coding: utf-8 -*-
"""V5 prospective PAPER-SHADOW candidate freeze (local files only).

This is NOT an authenticated official-source receipt, V5 performance ledger,
BUY authorization, or proof of profitable betting. It never reads results,
settles races, sends notifications, accesses the DB, or accesses the network.

Input manifest must be assembled independently from genuinely observed
predeadline data and V5-only model output. Historical replay is rejected.
The recorded timestamp is created by this process, not caller-controlled.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_RID = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TICKET = re.compile(r"[1-6]-[1-6]-[1-6]\Z")


def _dt(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO8601 string")
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid timestamp") from None
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone is mandatory")
    return d.astimezone(timezone.utc)


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def prepare_candidate(manifest: object, *, now: datetime | None = None) -> dict:
    """Validate a fresh prospective mock selection, never claim as-of proof."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    observed = datetime.now(timezone.utc) if now is None else now
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("clock must be timezone aware")
    observed = observed.astimezone(timezone.utc)

    rid = manifest.get("race_id")
    if not isinstance(rid, str) or not _RID.fullmatch(rid):
        raise ValueError("invalid race_id")
    deadline = _dt(manifest.get("deadline_at"))
    if deadline <= observed or (deadline - observed).total_seconds() < 180:
        raise ValueError("deadline is too close or already passed")
    if deadline.astimezone(timezone.utc).astimezone(
            __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))
    ).strftime("%Y%m%d") != rid[:8]:
        raise ValueError("race date/deadline mismatch")

    if manifest.get("model_family") != "V5" or not isinstance(manifest.get("model_version"), str) or not manifest["model_version"].strip():
        raise ValueError("explicit V5 model version required")

    for tag, required in (("exhibition", 6), ("odds", 120)):
        evidence = manifest.get(tag)
        if not isinstance(evidence, dict) or evidence.get("complete_items") != required:
            raise ValueError(f"incomplete {tag} evidence")
        if not isinstance(evidence.get("sha256"), str) or not _SHA.fullmatch(evidence["sha256"]):
            raise ValueError(f"invalid {tag} hash")
        captured = _dt(evidence.get("captured_at"))
        if captured > observed or captured >= deadline:
            raise ValueError(f"late {tag} capture")

    tickets = manifest.get("selected_tickets")
    if not isinstance(tickets, list) or not 1 <= len(tickets) <= 120 or len(set(map(str, tickets))) != len(tickets):
        raise ValueError("invalid ticket set")
    for ticket in tickets:
        if not isinstance(ticket, str) or not _TICKET.fullmatch(ticket) or len(set(ticket.split("-"))) != 3:
            raise ValueError("invalid 3-ren-tan ticket")
    stake = manifest.get("stake_per_ticket_yen")
    if type(stake) is not int or not 100 <= stake <= 100000 or stake % 100:
        raise ValueError("invalid hypothetical stake")

    # Hash the literal manifest to detect later edits. A hash does not prove
    # publisher authenticity or an independent immutable first observation.
    material = _canonical(manifest)
    return {
        "race_id": rid,
        "mode": "shadow",
        "model_version": manifest["model_version"],
        "recorded_at": observed.isoformat(),
        "deadline_at": deadline.isoformat(),
        "selected_tickets": tickets,
        "hypothetical_stake_yen": stake * len(tickets),
        "manifest_sha256": hashlib.sha256(material).hexdigest(),
        "source_provenance": "UNVERIFIED_FIRST_OBSERVATION",
        "settlement_status": "PENDING_NO_REAL_ROI",
        "original_first_observation_verified": False,
        "forward_eligible": False,
        "buy_eligible": False,
    }


def append_once(path: Path, record: dict) -> None:
    """Append exactly one fresh race to a local shadow-only candidate journal."""
    if not path.parent.is_dir():
        raise ValueError("journal directory must exist")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "a+", encoding="utf-8") as fp:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
            # O_APPEND+write-only cannot read; use a separate read descriptor
            # under the exclusive writer lock, if journal already has bytes.
            if os.path.getsize(path):
                with path.open("r", encoding="utf-8") as existing:
                    for line in existing:
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            raise ValueError("corrupt journal; no append") from None
                        if row.get("race_id") == record["race_id"] and row.get("mode") == "shadow":
                            raise ValueError("duplicate race; journal is append-only")
            fp.write(_canonical(record).decode("utf-8") + "\n")
            fp.flush()
            os.fsync(fp.fileno())
    except BaseException:
        # fd is owned by fdopen if that has started.
        raise


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--journal", type=Path, help="private local shadow-only journal")
    p.add_argument("--append", action="store_true", help="explicit opt-in local write")
    args = p.parse_args(argv)
    if args.append and args.journal is None:
        p.error("--append requires --journal")
    try:
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
        record = prepare_candidate(doc)
        if args.append:
            append_once(args.journal, record)
            print("V5_SHADOW_JOURNAL=APPENDED_PENDING_UNVERIFIED")
        else:
            print("V5_SHADOW_JOURNAL=PREVIEW_NO_WRITES")
        print(f"RACE_ID={record['race_id']} tickets={len(record['selected_tickets'])}")
        print("REAL_ROI_VERIFIED=0 BUY_ELIGIBLE=0")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print("V5_SHADOW_JOURNAL=HOLD " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
