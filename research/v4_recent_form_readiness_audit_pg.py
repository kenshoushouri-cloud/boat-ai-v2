# -*- coding: utf-8 -*-
"""Result-blind read-only readiness audit for v2_race_entries.recent_form.

This audit intentionally does not read outcomes, payouts, odds, or prediction results.
It only measures whether recent_form has enough coverage, structure, provenance,
and strict-prior timing evidence to justify a future preregistered model test.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

START_DATE = date(2025, 7, 1)
END_DATE = date(2026, 9, 22)
JST = timezone(timedelta(hours=9))
CUTOFF_CLOCK = time(8, 15)
OUTPUT_JSON = Path(os.getenv("V4_RECENT_FORM_OUTPUT_JSON", "v4-recent-form-readiness.json"))
VERSION = "2026-09-27-v4-recent-form-readiness-v1"

EVENT_DATE_KEYS = (
    "race_date",
    "date",
    "event_date",
    "held_date",
    "race_day",
    "day",
)
STRONG_CAPTURE_COLUMNS = (
    "source_fetched_at",
    "fetched_at",
    "captured_at",
    "snapshot_at",
    "source_captured_at",
)
WEAK_CAPTURE_COLUMNS = ("created_at", "updated_at")


def nonempty_json(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip()
        if text in {"", "[]", "{}", "null", "None"}:
            return False
        try:
            return nonempty_json(json.loads(text))
        except Exception:
            return True
    return True


def coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def parse_event_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    norm = text.replace("/", "-").replace(".", "-")
    candidates = [
        r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
        r"^(\d{4})(\d{2})(\d{2})$",
    ]
    for pattern in candidates:
        m = re.match(pattern, norm)
        if not m:
            continue
        try:
            return date(*map(int, m.groups()))
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        return None


def direct_item_date(item: dict[str, Any]) -> tuple[str | None, date | None]:
    lowered = {str(k).casefold(): k for k in item}
    for key in EVENT_DATE_KEYS:
        source_key = lowered.get(key)
        if source_key is None:
            continue
        parsed = parse_event_date(item.get(source_key))
        if parsed is not None:
            return str(source_key), parsed
    return None, None


def normalize_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(JST)


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute(
                    """
                    select column_name, data_type, udt_name
                    from information_schema.columns
                    where table_schema='public' and table_name='v2_race_entries'
                    order by ordinal_position
                    """
                )
                schema_rows = list(cur.fetchall())
                columns = {str(r["column_name"]): r for r in schema_rows}
                if "recent_form" not in columns:
                    report = {
                        "version": VERSION,
                        "period": [START_DATE.isoformat(), END_DATE.isoformat()],
                        "classification": "NOT_READY_COLUMN_MISSING",
                        "purchase_action": False,
                    }
                    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    print("RECENT_FORM_READINESS=NOT_READY_COLUMN_MISSING", flush=True)
                    print("RESULT=PASS_READ_ONLY", flush=True)
                    return

                recent_type = str(columns["recent_form"]["udt_name"])
                racer_col = next(
                    (name for name in ("racer_number", "racer_no", "registration_no", "racer_id") if name in columns),
                    None,
                )
                strong_capture_col = next((name for name in STRONG_CAPTURE_COLUMNS if name in columns), None)
                weak_capture_cols = [name for name in WEAK_CAPTURE_COLUMNS if name in columns]

                select_parts = [
                    "r.race_date",
                    "e.race_id",
                    "e.lane",
                    "e.recent_form",
                ]
                if racer_col:
                    select_parts.append(f'e."{racer_col}" as racer_identity')
                else:
                    select_parts.append("null as racer_identity")
                if strong_capture_col:
                    select_parts.append(f'e."{strong_capture_col}" as strong_capture_at')
                else:
                    select_parts.append("null as strong_capture_at")
                for name in weak_capture_cols:
                    select_parts.append(f'e."{name}" as "{name}"')

                cur.execute(
                    f"""
                    select {", ".join(select_parts)}
                    from v2_race_entries e
                    join v2_races r on r.race_id=e.race_id
                    where r.race_date >= %s and r.race_date <= %s
                    order by r.race_date, e.race_id, e.lane
                    """,
                    (START_DATE, END_DATE),
                )
                rows = list(cur.fetchall())

    total_rows = len(rows)
    race_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    day_races: dict[str, set[str]] = defaultdict(set)
    nonempty_rows: list[dict[str, Any]] = []
    top_types = Counter()
    array_lengths = Counter()
    item_key_counts = Counter()
    item_total = 0
    item_dict_total = 0
    item_dates_found = 0
    item_dates_strict_prior = 0
    item_dates_nonprior = 0
    item_date_keys = Counter()
    racer_bound_nonempty = 0
    strong_capture_present = 0
    strong_capture_by_cutoff = 0
    strong_capture_after_cutoff = 0
    strong_capture_unparseable = 0
    weak_timing_summary = Counter()

    for row in rows:
        race_id = str(row["race_id"])
        race_date = row["race_date"]
        if isinstance(race_date, datetime):
            race_date = race_date.date()
        race_rows[race_id].append(row)
        day_races[str(race_date)].add(race_id)

        payload = coerce_json(row["recent_form"])
        if not nonempty_json(payload):
            continue

        nonempty_rows.append(row)
        if row.get("racer_identity") is not None:
            racer_bound_nonempty += 1

        type_name = type(payload).__name__
        top_types[type_name] += 1
        if isinstance(payload, list):
            array_lengths[len(payload)] += 1
            items = payload
        elif isinstance(payload, dict):
            items = [payload]
        else:
            items = []

        for item in items:
            item_total += 1
            if not isinstance(item, dict):
                continue
            item_dict_total += 1
            for key in item:
                item_key_counts[str(key)] += 1
            key, parsed = direct_item_date(item)
            if parsed is not None:
                item_dates_found += 1
                item_date_keys[str(key)] += 1
                if parsed < race_date:
                    item_dates_strict_prior += 1
                else:
                    item_dates_nonprior += 1

        cutoff = datetime.combine(race_date, CUTOFF_CLOCK, tzinfo=JST)
        strong_dt = normalize_dt(row.get("strong_capture_at"))
        if row.get("strong_capture_at") is not None:
            strong_capture_present += 1
            if strong_dt is None:
                strong_capture_unparseable += 1
            elif strong_dt <= cutoff:
                strong_capture_by_cutoff += 1
            else:
                strong_capture_after_cutoff += 1

        for name in WEAK_CAPTURE_COLUMNS:
            if name not in row:
                continue
            dt = normalize_dt(row.get(name))
            if row.get(name) is None:
                weak_timing_summary[f"{name}_missing"] += 1
            elif dt is None:
                weak_timing_summary[f"{name}_unparseable_or_naive"] += 1
            elif dt <= cutoff:
                weak_timing_summary[f"{name}_by_0815"] += 1
            else:
                weak_timing_summary[f"{name}_after_0815"] += 1

    total_races = len(race_rows)
    total_days = len(day_races)
    nonempty_race_ids = {
        str(row["race_id"]) for row in nonempty_rows
    }
    full6_races = 0
    full6_nonempty_races = 0
    for race_id, rr in race_rows.items():
        if len(rr) == 6:
            full6_races += 1
            if sum(1 for row in rr if nonempty_json(coerce_json(row["recent_form"]))) == 6:
                full6_nonempty_races += 1

    all_nonempty_top_array = bool(nonempty_rows) and top_types.get("list", 0) == len(nonempty_rows)
    all_array_items_dict = bool(item_total) and item_dict_total == item_total
    all_items_have_dates = bool(item_total) and item_dates_found == item_total
    all_item_dates_strict_prior = all_items_have_dates and item_dates_nonprior == 0
    racer_binding_complete = bool(nonempty_rows) and racer_bound_nonempty == len(nonempty_rows)
    strong_capture_complete = bool(nonempty_rows) and strong_capture_present == len(nonempty_rows)
    strong_capture_cutoff_safe = (
        strong_capture_complete
        and strong_capture_unparseable == 0
        and strong_capture_after_cutoff == 0
        and strong_capture_by_cutoff == len(nonempty_rows)
    )

    gates = {
        "column_is_jsonb": recent_type == "jsonb",
        "has_nonempty_rows": len(nonempty_rows) > 0,
        "racer_binding_complete": racer_binding_complete,
        "top_level_array_consistent": all_nonempty_top_array,
        "array_items_are_dicts": all_array_items_dict,
        "every_item_has_parseable_event_date": all_items_have_dates,
        "every_item_event_date_strictly_prior": all_item_dates_strict_prior,
        "strong_capture_timestamp_column_present": strong_capture_col is not None,
        "every_nonempty_row_proven_by_0815": strong_capture_cutoff_safe,
    }
    readiness = all(gates.values())

    report = {
        "version": VERSION,
        "period": [START_DATE.isoformat(), END_DATE.isoformat()],
        "safety": {
            "transaction_read_only": True,
            "outcome_tables_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "purchase_action": False,
        },
        "schema": {
            "recent_form_udt": recent_type,
            "racer_identity_column": racer_col,
            "strong_capture_column": strong_capture_col,
            "weak_capture_columns": weak_capture_cols,
        },
        "coverage": {
            "rows": total_rows,
            "races": total_races,
            "days": total_days,
            "nonempty_rows": len(nonempty_rows),
            "nonempty_row_percent": round(100.0 * len(nonempty_rows) / total_rows, 6) if total_rows else 0.0,
            "races_with_any_nonempty": len(nonempty_race_ids),
            "full6_races": full6_races,
            "full6_nonempty_races": full6_nonempty_races,
            "racer_bound_nonempty_rows": racer_bound_nonempty,
        },
        "structure": {
            "top_level_types": dict(sorted(top_types.items())),
            "array_length_counts": {str(k): v for k, v in sorted(array_lengths.items())},
            "item_total": item_total,
            "item_dict_total": item_dict_total,
            "item_key_counts": dict(item_key_counts.most_common(50)),
        },
        "chronology": {
            "item_dates_found": item_dates_found,
            "item_dates_strict_prior": item_dates_strict_prior,
            "item_dates_nonprior": item_dates_nonprior,
            "item_date_keys": dict(item_date_keys),
        },
        "capture_timing": {
            "strong_capture_present": strong_capture_present,
            "strong_capture_by_0815": strong_capture_by_cutoff,
            "strong_capture_after_0815": strong_capture_after_cutoff,
            "strong_capture_unparseable": strong_capture_unparseable,
            "weak_columns_are_diagnostic_only": dict(weak_timing_summary),
        },
        "gates": gates,
        "classification": "READY_FOR_PREREGISTRATION_ONLY" if readiness else "NOT_READY_FAIL_CLOSED",
    }
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"RECENT_FORM_ROWS={total_rows}", flush=True)
    print(f"RECENT_FORM_NONEMPTY_ROWS={len(nonempty_rows)}", flush=True)
    print(f"RECENT_FORM_FULL6_NONEMPTY_RACES={full6_nonempty_races}", flush=True)
    print(f"RECENT_FORM_ITEM_DATES={item_dates_found}/{item_total}", flush=True)
    print(f"RECENT_FORM_STRONG_CAPTURE_COLUMN={strong_capture_col or 'NONE'}", flush=True)
    print(f"RECENT_FORM_READINESS={report['classification']}", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
