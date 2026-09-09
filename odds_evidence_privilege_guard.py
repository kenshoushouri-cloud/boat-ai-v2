"""Conservative, SELECT-only privilege gate for the fixed 2026-09-08 audit.

This is a bounded execution prerequisite, not a cluster security certification.
No role creation, grants, privilege changes, or application-data reads occur here.
"""
from __future__ import annotations

ROLE_NAME = "boat_odds_audit_ro"
ALLOWED_TABLES = (
    "v2_races", "v2_race_entries", "v2_odds_trifecta",
    "v2_bao_market_shadow_snapshots",
)
MIN_VERSION = 140000
MAX_VERSION = 190000  # New major versions require a review of privilege semantics.


class PrivilegeGuardError(RuntimeError):
    """A deliberately non-sensitive failure; never include catalog values."""


def _one(cur, query, params=()):
    cur.execute(query, params)
    rows = cur.fetchmany(2)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise PrivilegeGuardError("privilege_preflight_unavailable")
    return rows[0]


def preflight(cur, expected_role=ROLE_NAME):
    """Check the authenticated role inside the audit's read-only transaction.

    Rejects any role membership, administrative attributes, ownership, broad
    object privileges, and executable non-system routines. The catalog checks
    intentionally over-reject rather than infer least privilege from SELECT.
    """
    if expected_role != ROLE_NAME:
        raise PrivilegeGuardError("privilege_preflight_rejected")
    try:
        identity = _one(cur, """SELECT current_setting('server_version_num')::int AS version,
            current_setting('transaction_read_only') AS read_only,
            session_user AS login_role, current_user AS active_role,
            current_database() AS database_name,
            r.oid AS role_oid, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
            r.rolreplication, r.rolbypassrls, r.rolinherit, r.rolcanlogin
            FROM pg_catalog.pg_roles r WHERE r.rolname = session_user""")
        version = identity.get("version")
        if (type(version) is not int or not MIN_VERSION <= version < MAX_VERSION
                or identity.get("read_only") != "on"
                or identity.get("login_role") != expected_role
                or identity.get("active_role") != expected_role
                or type(identity.get("role_oid")) is not int
                or any(identity.get(k) is not False for k in (
                    "rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication",
                    "rolbypassrls", "rolinherit"))
                or identity.get("rolcanlogin") is not True):
            raise PrivilegeGuardError("privilege_preflight_rejected")
        role_oid = identity["role_oid"]
        # MAINTAIN was introduced in PostgreSQL 17. Never pass an unknown
        # privilege name to an older server or silently accept a newer major.
        table_writes = "INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER"
        if version >= 170000:
            table_writes += ", MAINTAIN"
        checks = _one(cur, """SELECT
            EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = %s) AS memberships,
            EXISTS (SELECT 1 FROM pg_catalog.pg_shdepend
                WHERE refclassid = 'pg_catalog.pg_authid'::regclass
                  AND refobjid = %s AND deptype = 'o') AS owns_objects,
            EXISTS (SELECT 1 FROM pg_catalog.pg_database
                WHERE pg_catalog.has_database_privilege(oid, 'CREATE, TEMP')) AS database_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_namespace
                WHERE pg_catalog.has_schema_privilege(oid, 'CREATE')) AS schema_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_tablespace
                WHERE pg_catalog.has_tablespace_privilege(oid, 'CREATE')) AS tablespace_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class
                WHERE relkind IN ('r','p','v','m','f')
                  AND pg_catalog.has_table_privilege(oid, %s)) AS table_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND pg_catalog.has_column_privilege(c.oid, a.attnum,
                      'INSERT, UPDATE, REFERENCES')) AS column_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class
                WHERE relkind = 'S'
                  AND pg_catalog.has_sequence_privilege(oid, 'USAGE, SELECT, UPDATE')) AS sequence_access,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND pg_catalog.has_table_privilege(c.oid, 'SELECT')
                  AND NOT (n.nspname = 'pg_catalog' OR n.nspname = 'information_schema'
                    OR (n.nspname = 'public' AND c.relname = ANY(%s)))) AS extra_table_read,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND pg_catalog.has_column_privilege(c.oid, a.attnum, 'SELECT')
                  AND NOT (n.nspname = 'pg_catalog' OR n.nspname = 'information_schema'
                    OR (n.nspname = 'public' AND c.relname = ANY(%s)))) AS extra_column_read,
            EXISTS (SELECT 1 FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE pg_catalog.has_function_privilege(p.oid, 'EXECUTE')
                  AND (n.nspname NOT IN ('pg_catalog','information_schema')
                    OR p.prosecdef
                    OR (p.proacl IS NOT NULL AND NOT EXISTS (
                        SELECT 1 FROM pg_catalog.aclexplode(p.proacl) a
                        WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE')))) AS extra_routine_execute,
            EXISTS (SELECT 1 FROM pg_catalog.pg_language
                WHERE NOT lanpltrusted AND pg_catalog.has_language_privilege(oid, 'USAGE')) AS untrusted_language,
            EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_data_wrapper
                WHERE pg_catalog.has_foreign_data_wrapper_privilege(oid, 'USAGE')) AS foreign_wrapper,
            EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_server
                WHERE pg_catalog.has_server_privilege(oid, 'USAGE')) AS foreign_server,
            EXISTS (SELECT 1 FROM pg_catalog.pg_largeobject_metadata
                WHERE pg_catalog.has_largeobject_privilege(oid, 'SELECT, UPDATE')) AS largeobject_access,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND c.relkind NOT IN ('r','p')) AS unexpected_target_kind,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND NOT pg_catalog.has_table_privilege(c.oid, 'SELECT')) AS missing_target_read
            """, (role_oid, role_oid, table_writes, list(ALLOWED_TABLES),
                  list(ALLOWED_TABLES), list(ALLOWED_TABLES), list(ALLOWED_TABLES)))
        if set(checks) != {
            "memberships", "owns_objects", "database_write", "schema_write",
            "tablespace_write", "table_write", "column_write", "sequence_access",
            "extra_table_read", "extra_column_read", "extra_routine_execute",
            "untrusted_language", "foreign_wrapper", "foreign_server",
            "largeobject_access", "unexpected_target_kind", "missing_target_read",
        } or any(value is not False for value in checks.values()):
            raise PrivilegeGuardError("privilege_preflight_rejected")
        return {"status": "BOUNDED_PRIVILEGE_PREFLIGHT_PASSED",
                "database_name": identity["database_name"],
                "role": expected_role, "server_version": version}
    except PrivilegeGuardError:
        raise
    except Exception:
        raise PrivilegeGuardError("privilege_preflight_unavailable") from None
