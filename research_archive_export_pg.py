# -*- coding: utf-8 -*-
"""Bounded research-only PostgreSQL archive exporter.

This helper is intentionally not referenced by Production services. It exports
one allow-listed table/date slice through a read-only PostgreSQL session, writes
canonical JSONL.gz plus a manifest, and never deletes or updates source rows.

No external upload is performed by this script.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

JST = timezone(timedelta(hours=9))
MAX_DAYS_DEFAULT = 31
MIN_AGE_DAYS_DEFAULT = 14

TABLES: dict[str, dict[str, Any]] = {
    "v2_odds_trifecta": {
        "date_column": "race_date",
        "key_fields": ("race_id", "ticket"),
        "label_column": None,
    },
    "v2_realtime_odds_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label", "ticket"),
        "label_column": "snapshot_label",
    },
    "v2_realtime_weather_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label"),
        "label_column": "snapshot_label",
    },
    "v2_realtime_exhibition_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label", "lane"),
        "label_column": "snapshot_label",
    },
    "v2_realtime_entry_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label", "lane"),
        "label_column": "snapshot_label",
    },
    "v2_realtime_race_condition_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label"),
        "label_column": "snapshot_label",
    },
    "v2_realtime_racer_condition_snapshots": {
        "date_column": "race_date",
        "key_fields": ("race_id", "snapshot_label", "lane"),
        "label_column": "snapshot_label",
    },
}


@dataclass(frozen=True)
class ExportSpec:
    table: str
    start_date: date
    end_date: date
    label: str | None
    output_dir: Path
    max_days: int = MAX_DAYS_DEFAULT
    min_age_days: int = MIN_AGE_DAYS_DEFAULT

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def config(self) -> Mapping[str, Any]:
        return TABLES[self.table]

    def validate(self, today: date | None = None) -> None:
        today = today or datetime.now(JST).date()
        if self.table not in TABLES:
            raise ValueError(f"table is not allow-listed: {self.table}")
        if self.max_days <= 0:
            raise ValueError("max_days must be positive")
        if self.min_age_days < 0:
            raise ValueError("min_age_days must be >= 0")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if self.days > self.max_days:
            raise ValueError(f"date slice too large: {self.days} > {self.max_days}")
        if self.end_date > today - timedelta(days=self.min_age_days):
            raise ValueError(
                "date slice is too recent for archive pilot: "
                f"end={self.end_date} min_age_days={self.min_age_days}"
            )
        label_column = self.config.get("label_column")
        if self.label and not label_column:
            raise ValueError(f"label filter is unsupported for {self.table}")
        if self.label is not None and not self.label.strip():
            raise ValueError("label must be non-empty when supplied")

    def stem(self) -> str:
        label = f"_{self.label}" if self.label else ""
        return f"{self.table}_{self.start_date.isoformat()}_{self.end_date.isoformat()}{label}"


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as exc:
        raise ValueError(f"invalid {name}: {value!r}") from exc


def spec_from_env() -> ExportSpec:
    table = os.getenv("ARCHIVE_TABLE", "").strip()
    start = _parse_date(os.getenv("ARCHIVE_START_DATE", "").strip(), "ARCHIVE_START_DATE")
    end = _parse_date(os.getenv("ARCHIVE_END_DATE", "").strip(), "ARCHIVE_END_DATE")
    label = os.getenv("ARCHIVE_LABEL", "").strip() or None
    output_dir = Path(os.getenv("ARCHIVE_OUTPUT_DIR", "/tmp/boat-archive")).expanduser()
    max_days = int(os.getenv("ARCHIVE_MAX_DAYS", str(MAX_DAYS_DEFAULT)))
    min_age_days = int(os.getenv("ARCHIVE_MIN_AGE_DAYS", str(MIN_AGE_DAYS_DEFAULT)))
    spec = ExportSpec(table, start, end, label, output_dir, max_days=max_days, min_age_days=min_age_days)
    spec.validate()
    return spec


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def canonical_line(row: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            _jsonable(dict(row)),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _verify_gzip_readback(path: Path) -> tuple[int, int, str]:
    row_count = 0
    payload_bytes = 0
    sha = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for line in fh:
            row_count += 1
            payload_bytes += len(line)
            sha.update(line)
    return row_count, payload_bytes, sha.hexdigest()


def _key_tuple(row: Mapping[str, Any], key_fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(json.dumps(_jsonable(row.get(k)), ensure_ascii=False, sort_keys=True) for k in key_fields)


def _schema_rows(conn: Any, table: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name, data_type, udt_name, is_nullable, ordinal_position
            from information_schema.columns
            where table_schema='public' and table_name=%s
            order by ordinal_position
            """,
            (table,),
        )
        return [
            {
                "column_name": r[0],
                "data_type": r[1],
                "udt_name": r[2],
                "is_nullable": r[3],
                "ordinal_position": r[4],
            }
            for r in cur.fetchall()
        ]


def _source_identity(conn: Any) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("select current_database(), current_setting('server_version_num')")
        db_name, version_num = cur.fetchone()
    return {"database": str(db_name), "server_version_num": str(version_num)}


def _select_sql(spec: ExportSpec) -> tuple[str, list[Any]]:
    cfg = spec.config
    date_col = cfg["date_column"]
    key_fields = cfg["key_fields"]
    where = [f"{date_col} >= %s", f"{date_col} <= %s"]
    params: list[Any] = [spec.start_date, spec.end_date]
    if spec.label:
        where.append(f"{cfg['label_column']} = %s")
        params.append(spec.label)
    sql = f"select * from {spec.table} where {' and '.join(where)} order by {','.join(key_fields)}"
    return sql, params


def export_partition(conn: Any, spec: ExportSpec) -> tuple[Path, Path, dict[str, Any]]:
    spec.validate()
    spec.output_dir.mkdir(parents=True, exist_ok=True)
    data_path = spec.output_dir / f"{spec.stem()}.jsonl.gz"
    manifest_path = spec.output_dir / f"{spec.stem()}.manifest.json"
    if data_path.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite existing archive output")

    sql, params = _select_sql(spec)
    key_fields = tuple(spec.config["key_fields"])
    payload_sha = hashlib.sha256()
    payload_bytes = 0
    row_count = 0
    duplicate_count = 0
    previous_key: tuple[str, ...] | None = None

    with conn.cursor(name="archive_export_stream") as cur:
        cur.itersize = 2000
        cur.execute(sql, params)
        columns = [d.name for d in cur.description]
        with data_path.open("wb") as raw_fh:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=6,
                fileobj=raw_fh,
                mtime=0,
            ) as gz:
                for raw in cur:
                    row = dict(zip(columns, raw))
                    key = _key_tuple(row, key_fields)
                    if key == previous_key:
                        duplicate_count += 1
                    previous_key = key
                    line = canonical_line(row)
                    payload_sha.update(line)
                    payload_bytes += len(line)
                    gz.write(line)
                    row_count += 1

    readback_rows, readback_bytes, readback_sha = _verify_gzip_readback(data_path)
    expected_sha = payload_sha.hexdigest()
    if (readback_rows, readback_bytes, readback_sha) != (row_count, payload_bytes, expected_sha):
        raise RuntimeError(
            "archive readback mismatch: "
            f"written=({row_count},{payload_bytes},{expected_sha}) "
            f"readback=({readback_rows},{readback_bytes},{readback_sha})"
        )

    manifest = {
        "archive_contract_version": 1,
        "table": spec.table,
        "start_date": spec.start_date.isoformat(),
        "end_date": spec.end_date.isoformat(),
        "label": spec.label,
        "logical_key": list(key_fields),
        "row_count": row_count,
        "logical_key_duplicate_count": duplicate_count,
        "canonical_payload_sha256": expected_sha,
        "canonical_payload_bytes": payload_bytes,
        "archive_file": data_path.name,
        "archive_file_sha256": _sha256_file(data_path),
        "archive_file_bytes": data_path.stat().st_size,
        "schema": _schema_rows(conn, spec.table),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_identity": _source_identity(conn),
        "source_mode": "postgresql_read_only",
        "source_rows_deleted": False,
        "readback_verified": True,
        "readback_row_count": readback_rows,
        "readback_payload_sha256": readback_sha,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return data_path, manifest_path, manifest


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    spec = spec_from_env()

    import psycopg

    print("RESEARCH_ARCHIVE_EXPORT=START", flush=True)
    print(
        f"table={spec.table} period={spec.start_date}..{spec.end_date} "
        f"label={spec.label or '-'} max_days={spec.max_days} min_age_days={spec.min_age_days}",
        flush=True,
    )
    # Connection-level default_transaction_read_only prevents accidental writes.
    with psycopg.connect(dsn, options="-c default_transaction_read_only=on") as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            state = str(cur.fetchone()[0]).lower()
            if state != "on":
                raise RuntimeError(f"read-only guard failed: transaction_read_only={state}")
        data_path, manifest_path, manifest = export_partition(conn, spec)

    print(f"archive_file={data_path}", flush=True)
    print(f"manifest_file={manifest_path}", flush=True)
    print(f"rows={manifest['row_count']}", flush=True)
    print(f"payload_sha256={manifest['canonical_payload_sha256']}", flush=True)
    print(f"archive_sha256={manifest['archive_file_sha256']}", flush=True)
    print("RESEARCH_ARCHIVE_EXPORT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
