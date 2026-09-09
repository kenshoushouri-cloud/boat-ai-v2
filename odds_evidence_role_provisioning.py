"""Provision the dedicated odds-evidence audit role after explicit approval.

This module is intentionally not a CLI and never connects by itself. The caller
must already hold an administrator connection and an open transaction. It
performs no COMMIT. Production execution, credential creation, secret storage
and Railway changes require a separate human approval gate.
"""
from __future__ import annotations

import re

import odds_evidence_privilege_guard as guard

ROLE_NAME = guard.ROLE_NAME
CONFIRMATION = "PROVISION-BOAT-ODDS-AUDIT-RO"
_DB_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$-]{0,62}$")
SETTINGS = {
    "default_transaction_read_only": "on",
    "search_path": "pg_catalog",
    "statement_timeout": "15s",
    "lock_timeout": "2s",
    "idle_in_transaction_session_timeout": "30s",
}


class ProvisioningError(RuntimeError):
    """Fixed, non-sensitive provisioning failure."""


def validate_request(*, database: str, password: str, confirmation: str) -> None:
    if (not isinstance(database, str) or not _DB_RE.fullmatch(database)
            or not isinstance(password, str) or len(password) < 24
            or len(password) > 256 or any(ord(ch) < 32 for ch in password)
            or confirmation != CONFIRMATION):
        raise ProvisioningError("audit_role_provisioning_rejected")


def apply(cur, *, database: str, password: str, confirmation: str) -> dict:
    """Apply the least-privilege role contract using the caller's transaction.

    The function deliberately refuses to create missing application tables and
    does not alter PUBLIC privileges. Required tables must already exist. The
    optional snapshot table is granted only when it exists. The caller is
    responsible for rollback on any failure and for commit only after approval.
    """
    validate_request(database=database, password=password, confirmation=confirmation)
    try:
        from psycopg import sql

        role = sql.Identifier(ROLE_NAME)
        db = sql.Identifier(database)
        cur.execute(sql.SQL("""CREATE ROLE {} WITH LOGIN NOINHERIT NOSUPERUSER
            NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1
            PASSWORD {}""").format(role, sql.Literal(password)))

        cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(db, role))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, role))
        cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {}").format(role))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))

        granted = []
        for table, columns in guard.TARGET_COLUMNS.items():
            cur.execute("SELECT to_regclass(%s) AS relation", ("public." + table,))
            row = cur.fetchone()
            relation = None
            if isinstance(row, dict):
                relation = row.get("relation")
            elif row:
                relation = row[0]
            if relation is None:
                if table in guard.REQUIRED_TABLES:
                    raise ProvisioningError("audit_role_required_relation_missing")
                continue
            table_id = sql.Identifier(table)
            cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON TABLE public.{} FROM {}").format(
                table_id, role))
            cur.execute(sql.SQL("GRANT SELECT ({}) ON TABLE public.{} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(name) for name in columns), table_id, role))
            granted.append(table)

        for name, value in SETTINGS.items():
            cur.execute(sql.SQL("ALTER ROLE {} SET {} TO {}").format(
                role, sql.Identifier(name), sql.Literal(value)))

        return {
            "status": "AUDIT_ROLE_PROVISIONING_APPLIED_UNCOMMITTED",
            "role": ROLE_NAME,
            "database": database,
            "granted_tables": tuple(granted),
            "settings": tuple(sorted(SETTINGS)),
        }
    except ProvisioningError:
        raise
    except Exception:
        raise ProvisioningError("audit_role_provisioning_unavailable") from None


if __name__ == "__main__":
    raise SystemExit("not_a_cli")
