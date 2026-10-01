import base64
import csv
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import psycopg
from psycopg import sql

ARTIFACT_NAME = "boat-ai-pre-hobby-restorable-20261001-v3-parity-36812386066"
EXPECTED_DUMP_SHA = "87dea392d2667509c5040d3fd9bff85ffbbd2dc0d5dec974cba9f75a29e062ab"
EXPECTED_EVIDENCE_SHA = "658bac46705b3006fdc0ee370e9370bf90a484bc2a8767d8cc29734ae0af603d"
EXPECTED = {
    "PUBLIC_TABLES": 39,
    "PUBLIC_COLUMNS": 771,
    "PUBLIC_CONSTRAINTS": 289,
    "PUBLIC_INDEXES": 98,
    "PUBLIC_SEQUENCES": 24,
    "PUBLIC_VIEWS": 0,
    "PUBLIC_TRIGGERS": 0,
    "PUBLIC_POLICIES": 0,
    "EXTENSIONS": 1,
}
LIMIT_BYTES = 5_000_000_000

QUERIES = {
    "tables": """
        SELECT c.relname,
               c.relkind::text,
               c.relpersistence::text,
               c.relreplident::text,
               c.relrowsecurity::text,
               c.relforcerowsecurity::text
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r','p')
        ORDER BY c.relname
    """,
    "columns": """
        SELECT table_name,
               ordinal_position::text,
               column_name,
               data_type,
               udt_schema,
               udt_name,
               is_nullable,
               COALESCE(column_default, ''),
               COALESCE(character_maximum_length::text, ''),
               COALESCE(numeric_precision::text, ''),
               COALESCE(numeric_scale::text, ''),
               COALESCE(collation_schema, ''),
               COALESCE(collation_name, ''),
               is_identity,
               COALESCE(identity_generation, ''),
               is_generated,
               COALESCE(generation_expression, '')
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """,
    "constraints": """
        SELECT c.conrelid::regclass::text,
               c.conname,
               c.contype::text,
               pg_get_constraintdef(c.oid, true)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE n.nspname = 'public'
          AND c.conrelid <> 0
        ORDER BY c.conrelid::regclass::text, c.conname
    """,
    "indexes": """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """,
    "sequences": """
        SELECT sequencename,
               data_type,
               start_value::text,
               min_value::text,
               max_value::text,
               increment_by::text,
               cycle::text,
               cache_size::text
        FROM pg_sequences
        WHERE schemaname = 'public'
        ORDER BY sequencename
    """,
    "views": """
        SELECT c.relname,
               c.relkind::text,
               pg_get_viewdef(c.oid, true)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('v','m')
        ORDER BY c.relname
    """,
    "triggers": """
        SELECT c.relname,
               t.tgname,
               pg_get_triggerdef(t.oid, true)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND NOT t.tgisinternal
        ORDER BY c.relname, t.tgname
    """,
    "policies": """
        SELECT tablename,
               policyname,
               permissive,
               roles::text,
               cmd,
               COALESCE(qual, ''),
               COALESCE(with_check, '')
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY tablename, policyname
    """,
    "extensions": """
        SELECT extname, extversion
        FROM pg_extension
        ORDER BY extname
    """,
}

KINDS = [
    "table-counts",
    "tables",
    "columns",
    "constraints",
    "indexes",
    "sequences",
    "views",
    "triggers",
    "policies",
    "extensions",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest(path: Path) -> dict[str, str]:
    out = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" in raw:
            k, v = raw.split("=", 1)
            out[k] = v
    return out


def write_tsv(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        for row in rows:
            writer.writerow(["" if value is None else str(value) for value in row])


def capture(conn: psycopg.Connection, root: Path) -> tuple[dict[str, int], int, str]:
    tables = conn.execute("""
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r','p')
        ORDER BY c.relname
    """).fetchall()

    counts = []
    for (table_name,) in tables:
        query = sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier("public"),
            sql.Identifier(table_name),
        )
        counts.append((table_name, conn.execute(query).fetchone()[0]))
    write_tsv(root / "candidate-table-counts.tsv", counts)

    metadata_counts = {}
    for name, query in QUERIES.items():
        rows = conn.execute(query).fetchall()
        write_tsv(root / f"candidate-{name}.tsv", rows)
        metadata_counts[name] = len(rows)

    h = hashlib.sha256()
    for kind in KINDS:
        h.update((root / f"candidate-{kind}.tsv").read_bytes())

    db_bytes = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    return metadata_counts, int(db_bytes), h.hexdigest()


def run_checked(args, env=None) -> None:
    result = subprocess.run(
        args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"command_failed_rc_{result.returncode}")


def main() -> int:
    stage = "preflight"
    root = Path("/tmp/hobby-fullhistory-restore")
    key_path = root / "archive-private.pem"
    dump_path = root / "source.dump"
    try:
        artifact_url = os.environ["ARTIFACT_URL"]
        key_b64 = os.environ["RECOVERY_KEY_B64"]
        target_url = os.environ["TARGET_DATABASE_URL"]
        if not artifact_url or not key_b64 or not target_url:
            raise RuntimeError("required_input_missing")

        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)

        stage = "download"
        zip_path = root / "artifact.zip"
        with urllib.request.urlopen(artifact_url, timeout=120) as resp, zip_path.open("wb") as out:
            shutil.copyfileobj(resp, out)

        stage = "extract"
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(root / "artifact")

        artifact_dir = root / "artifact"
        manifest_path = artifact_dir / "parity-manifest-v3.txt"
        cert_path = artifact_dir / "archive-public-v3.pem"
        cms_path = artifact_dir / f"{ARTIFACT_NAME}.dump.cms"
        if not (manifest_path.is_file() and cert_path.is_file() and cms_path.is_file()):
            raise RuntimeError("artifact_files_missing")

        stage = "manifest"
        manifest = parse_manifest(manifest_path)
        if manifest.get("ARCHIVE_NAME") != ARTIFACT_NAME:
            raise RuntimeError("artifact_name_mismatch")
        if manifest.get("PLAIN_DUMP_SHA256") != EXPECTED_DUMP_SHA:
            raise RuntimeError("manifest_dump_sha_mismatch")
        if manifest.get("SOURCE_EVIDENCE_SHA256") != EXPECTED_EVIDENCE_SHA:
            raise RuntimeError("manifest_evidence_sha_mismatch")
        for key, expected in EXPECTED.items():
            if int(manifest.get(key, "-1")) != expected:
                raise RuntimeError(f"manifest_count_mismatch_{key.lower()}")

        stage = "decrypt"
        key_path.write_bytes(base64.b64decode(key_b64, validate=True))
        os.chmod(key_path, 0o600)
        run_checked([
            "openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
            "-in", str(cms_path),
            "-recip", str(cert_path),
            "-inkey", str(key_path),
            "-out", str(dump_path),
        ])
        key_path.unlink(missing_ok=True)

        stage = "dump_sha"
        dump_sha = sha256_file(dump_path)
        if dump_sha != EXPECTED_DUMP_SHA:
            raise RuntimeError("decrypted_dump_sha_mismatch")

        stage = "restore"
        run_checked([
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            "--jobs=2",
            f"--dbname={target_url}",
            str(dump_path),
        ])

        stage = "candidate_parity"
        with psycopg.connect(target_url) as conn:
            conn.execute("SET default_transaction_read_only = on")
            metadata_counts, db_bytes, evidence_sha = capture(conn, root)

        actual = {
            "PUBLIC_TABLES": metadata_counts["tables"],
            "PUBLIC_COLUMNS": metadata_counts["columns"],
            "PUBLIC_CONSTRAINTS": metadata_counts["constraints"],
            "PUBLIC_INDEXES": metadata_counts["indexes"],
            "PUBLIC_SEQUENCES": metadata_counts["sequences"],
            "PUBLIC_VIEWS": metadata_counts["views"],
            "PUBLIC_TRIGGERS": metadata_counts["triggers"],
            "PUBLIC_POLICIES": metadata_counts["policies"],
            "EXTENSIONS": metadata_counts["extensions"],
        }

        if evidence_sha != EXPECTED_EVIDENCE_SHA:
            raise RuntimeError("candidate_evidence_sha_mismatch")
        for key, expected in EXPECTED.items():
            if actual[key] != expected:
                raise RuntimeError(f"candidate_count_mismatch_{key.lower()}")
        if db_bytes >= LIMIT_BYTES:
            raise RuntimeError("candidate_exceeds_5gb")

        headroom = LIMIT_BYTES - db_bytes
        print("CANDIDATE_RESTORE_RESULT=PASS")
        print(f"CANDIDATE_DUMP_SHA256={dump_sha}")
        print(f"CANDIDATE_EVIDENCE_SHA256={evidence_sha}")
        print(f"CANDIDATE_DB_BYTES={db_bytes}")
        print(f"CANDIDATE_HEADROOM_BYTES={headroom}")
        print(f"PUBLIC_TABLES={actual['PUBLIC_TABLES']}")
        print(f"PUBLIC_COLUMNS={actual['PUBLIC_COLUMNS']}")
        print(f"PUBLIC_CONSTRAINTS={actual['PUBLIC_CONSTRAINTS']}")
        print(f"PUBLIC_INDEXES={actual['PUBLIC_INDEXES']}")
        print(f"PUBLIC_SEQUENCES={actual['PUBLIC_SEQUENCES']}")
        print(f"PUBLIC_VIEWS={actual['PUBLIC_VIEWS']}")
        print(f"PUBLIC_TRIGGERS={actual['PUBLIC_TRIGGERS']}")
        print(f"PUBLIC_POLICIES={actual['PUBLIC_POLICIES']}")
        print(f"EXTENSIONS={actual['EXTENSIONS']}")
        print("SOURCE_WRITE=0")
        print("CUTOVER=0")
        print("PLAN_CHANGE=0")
        return 0
    except Exception as exc:
        print("CANDIDATE_RESTORE_RESULT=FAIL")
        print(f"FAIL_STAGE={stage}")
        print(f"ERROR_TYPE={type(exc).__name__}")
        print("SOURCE_WRITE=0")
        print("CUTOVER=0")
        print("PLAN_CHANGE=0")
        return 1
    finally:
        key_path.unlink(missing_ok=True)
        dump_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
