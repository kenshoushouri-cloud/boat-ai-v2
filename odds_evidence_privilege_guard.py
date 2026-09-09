"""Bounded, catalog-only privilege prerequisite for the fixed historical audit.

Not a cluster security certification. No role creation, grants, or race-data reads.
Unknown catalog semantics and unverifiable privileges fail closed.
"""
from __future__ import annotations

ROLE_NAME = "boat_odds_audit_ro"
TARGET_COLUMNS = {
    "v2_races": ("race_id", "race_date", "deadline_at"),
    "v2_race_entries": ("race_id", "lane"),
    "v2_odds_trifecta": ("race_id", "ticket", "fetched_at", "is_final"),
    "v2_bao_market_shadow_snapshots": (
        "race_id", "phase", "captured_at", "created_at", "deadline_at",
        "odds", "source", "schema_version"),
}
REQUIRED_TABLES = frozenset(TARGET_COLUMNS) - {"v2_bao_market_shadow_snapshots"}
MIN_VERSION = 140000
MAX_VERSION = 190000  # Review new major versions before permitting execution.


class PrivilegeGuardError(RuntimeError):
    """Only fixed, non-sensitive failure codes may escape this module."""


def _one(cur, query, params=()):
    cur.execute(query, params)
    rows = cur.fetchmany(2)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise PrivilegeGuardError("privilege_preflight_unavailable")
    return rows[0]


def _clear(row, names):
    if set(row) != set(names) or any(row[name] is not False for name in names):
        raise PrivilegeGuardError("privilege_preflight_rejected")


def preflight(cur, *, expected_database):
    """Check the authenticated role inside the caller's read-only transaction.

    Reject administrative attributes, role membership, ownership, write/grant
    authority, extra application-data reads, and executable non-system routines.
    This deliberately over-rejects rather than infer safety from SELECT alone.
    """
    if (not isinstance(expected_database, str) or not expected_database
            or len(expected_database) > 63):
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
                or identity.get("login_role") != ROLE_NAME
                or identity.get("active_role") != ROLE_NAME
                or identity.get("database_name") != expected_database
                or type(identity.get("role_oid")) is not int
                or any(identity.get(k) is not False for k in (
                    "rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication",
                    "rolbypassrls", "rolinherit"))
                or identity.get("rolcanlogin") is not True):
            raise PrivilegeGuardError("privilege_preflight_rejected")
        oid = identity["role_oid"]
        table_writes = "INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER"
        if version >= 170000:
            table_writes += ", MAINTAIN"
        table_nonupdate_writes = table_writes.replace("UPDATE, ", "")
        table_grants = ", ".join(
            privilege + " WITH GRANT OPTION" for privilege in table_writes.split(", "))
        checks = _one(cur, """SELECT
            EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = %s) AS memberships,
            EXISTS (SELECT 1 FROM pg_catalog.pg_shdepend
                WHERE refclassid = 'pg_catalog.pg_authid'::regclass
                  AND refobjid = %s AND deptype = 'o') AS owns_objects,
            EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl WHERE defaclrole = %s) AS default_acl_owner,
            -- CREATE is disallowed in every database. A direct TEMP grant is
            -- also disallowed; ordinary PUBLIC TEMP is a PostgreSQL default,
            -- constrained by the already verified read-only transaction.
            EXISTS (SELECT 1 FROM pg_catalog.pg_database d
                WHERE pg_catalog.has_database_privilege(d.oid, 'CREATE')
                   OR EXISTS (SELECT 1 FROM pg_catalog.aclexplode(
                       COALESCE(d.datacl, pg_catalog.acldefault('d', d.datdba))) a
                       WHERE a.grantee = %s AND a.privilege_type = 'TEMP')) AS database_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_database
                WHERE pg_catalog.has_database_privilege(oid, 'CREATE WITH GRANT OPTION, CONNECT WITH GRANT OPTION, TEMP WITH GRANT OPTION')) AS database_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_namespace
                WHERE pg_catalog.has_schema_privilege(oid, 'CREATE')) AS schema_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_namespace
                WHERE pg_catalog.has_schema_privilege(oid, 'CREATE WITH GRANT OPTION, USAGE WITH GRANT OPTION')) AS schema_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_tablespace
                WHERE pg_catalog.has_tablespace_privilege(oid, 'CREATE')) AS tablespace_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_tablespace
                WHERE pg_catalog.has_tablespace_privilege(oid, 'CREATE WITH GRANT OPTION')) AS tablespace_grant,
            -- pg_settings has a built-in PUBLIC UPDATE grant. Its rule is
            -- equivalent to SET; other writes and grant options remain denied.
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND (pg_catalog.has_table_privilege(c.oid, %s)
                    OR (NOT (n.nspname = 'pg_catalog' AND c.relname = 'pg_settings')
                        AND pg_catalog.has_table_privilege(c.oid, 'UPDATE')))) AS table_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class
                WHERE relkind IN ('r','p','v','m','f')
                  AND pg_catalog.has_table_privilege(oid, %s)) AS table_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND (pg_catalog.has_column_privilege(c.oid, a.attnum,
                      'INSERT, REFERENCES')
                    OR (NOT (n.nspname = 'pg_catalog' AND c.relname = 'pg_settings')
                        AND pg_catalog.has_column_privilege(c.oid, a.attnum, 'UPDATE')))) AS column_write,
            EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND pg_catalog.has_column_privilege(c.oid, a.attnum,
                      'SELECT WITH GRANT OPTION, INSERT WITH GRANT OPTION, UPDATE WITH GRANT OPTION, REFERENCES WITH GRANT OPTION')) AS column_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class
                WHERE CASE WHEN relkind = 'S'
                  THEN pg_catalog.has_sequence_privilege(oid, 'USAGE, SELECT, UPDATE')
                  ELSE false END) AS sequence_access,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class
                WHERE CASE WHEN relkind = 'S'
                  THEN pg_catalog.has_sequence_privilege(oid, 'USAGE WITH GRANT OPTION, SELECT WITH GRANT OPTION, UPDATE WITH GRANT OPTION')
                  ELSE false END) AS sequence_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE pg_catalog.has_function_privilege(p.oid, 'EXECUTE')
                  AND (n.nspname NOT IN ('pg_catalog','information_schema')
                       OR p.prosecdef)) AS extra_routine_execute,
            EXISTS (SELECT 1 FROM pg_catalog.pg_proc
                WHERE pg_catalog.has_function_privilege(oid, 'EXECUTE WITH GRANT OPTION')) AS routine_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_language
                WHERE lanispl AND NOT lanpltrusted
                  AND pg_catalog.has_language_privilege(oid, 'USAGE')) AS untrusted_language,
            EXISTS (SELECT 1 FROM pg_catalog.pg_language
                WHERE pg_catalog.has_language_privilege(oid, 'USAGE WITH GRANT OPTION')) AS language_grant,
            EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_data_wrapper
                WHERE pg_catalog.has_foreign_data_wrapper_privilege(oid, 'USAGE')) AS foreign_wrapper,
            EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_server
                WHERE pg_catalog.has_server_privilege(oid, 'USAGE')) AS foreign_server,
            EXISTS (SELECT 1 FROM pg_catalog.pg_largeobject_metadata lo
                CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(lo.lomacl, pg_catalog.acldefault('L', lo.lomowner))) a
                WHERE a.grantee IN (0, %s)
                  AND a.privilege_type IN ('SELECT', 'UPDATE')) AS largeobject_access,
            EXISTS (SELECT 1 FROM pg_catalog.pg_type
                WHERE pg_catalog.has_type_privilege(oid, 'USAGE WITH GRANT OPTION')) AS type_grant
            """, (oid, oid, oid, oid, table_nonupdate_writes, table_grants, oid))
        _clear(checks, (
            "memberships", "owns_objects", "default_acl_owner", "database_write",
            "database_grant", "schema_write", "schema_grant", "tablespace_write",
            "tablespace_grant", "table_write", "table_grant", "column_write", "column_grant",
            "sequence_access", "sequence_grant", "extra_routine_execute", "routine_grant",
            "untrusted_language", "language_grant", "foreign_wrapper", "foreign_server",
            "largeobject_access", "type_grant"))
        # PostgreSQL 15 introduced parameter ACLs. Check explicit rights only;
        # ordinary USERSET defaults must not be mistaken for elevated grants.
        if version >= 150000:
            parameters = _one(cur, """SELECT
                EXISTS (SELECT 1 FROM pg_catalog.pg_parameter_acl
                    WHERE pg_catalog.has_parameter_privilege(parname, 'SET WITH GRANT OPTION, ALTER SYSTEM WITH GRANT OPTION')) AS parameter_grant,
                EXISTS (SELECT 1 FROM pg_catalog.pg_settings
                    WHERE context IN ('superuser','postmaster','sighup','backend','superuser-backend')
                      AND pg_catalog.has_parameter_privilege(name, 'SET, ALTER SYSTEM')) AS privileged_parameter
                """)
            _clear(parameters, ("parameter_grant", "privileged_parameter"))
        targets = _one(cur, """SELECT
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND c.relkind NOT IN ('r','p')) AS unexpected_target_kind,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND pg_catalog.has_table_privilege(c.oid, 'SELECT')
                  AND NOT (n.nspname IN ('pg_catalog','information_schema')
                    OR (n.nspname = 'public' AND c.relname = ANY(%s)))) AS extra_table_read,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                WHERE c.relkind IN ('r','p','v','m','f')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND pg_catalog.has_column_privilege(c.oid, a.attnum, 'SELECT')
                  AND NOT (n.nspname IN ('pg_catalog','information_schema')
                    OR (n.nspname = 'public' AND c.relname = ANY(%s)))) AS extra_column_read
            """, (list(TARGET_COLUMNS),) * 3)
        _clear(targets, ("unexpected_target_kind", "extra_table_read", "extra_column_read"))
        # A table-level SELECT grant also exposes future columns. Require
        # column-only grants on the four audited relations, and reject RLS
        # because a policy could silently hide historical rows.
        scope = _one(cur, """SELECT
            NOT pg_catalog.has_schema_privilege('public', 'USAGE') AS missing_schema_usage,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND c.relkind IN ('r','p')
                  AND (c.relrowsecurity OR c.relforcerowsecurity)) AS target_rls,
            EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND c.relkind IN ('r','p')
                  AND pg_catalog.has_table_privilege(c.oid, 'SELECT')) AS broad_target_read,
            EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                  AND c.relkind IN ('r','p')
                  AND a.attnum > 0 AND NOT a.attisdropped
                  AND pg_catalog.has_column_privilege(c.oid, a.attnum, 'SELECT')
                  AND NOT (a.attname = ANY(CASE c.relname
                      WHEN 'v2_races' THEN ARRAY['race_id','race_date','deadline_at']
                      WHEN 'v2_race_entries' THEN ARRAY['race_id','lane']
                      WHEN 'v2_odds_trifecta' THEN ARRAY['race_id','ticket','fetched_at','is_final']
                      WHEN 'v2_bao_market_shadow_snapshots' THEN ARRAY['race_id','phase','captured_at','created_at','deadline_at','odds','source','schema_version']
                      ELSE ARRAY[]::text[] END))) AS extra_target_column_read
            """, (list(TARGET_COLUMNS),) * 3)
        _clear(scope, ('missing_schema_usage', 'target_rls', 'broad_target_read',
                       'extra_target_column_read'))
        for table, names in TARGET_COLUMNS.items():
            row = _one(cur, """SELECT
                EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = %s
                      AND c.relkind IN ('r','p')) AS relation_exists,
                NOT EXISTS (SELECT 1 FROM unnest(%s::text[]) AS required(name)
                    WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c
                        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                        JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                        WHERE n.nspname = 'public' AND c.relname = %s
                          AND c.relkind IN ('r','p') AND a.attname = required.name
                          AND a.attnum > 0 AND NOT a.attisdropped
                          AND pg_catalog.has_column_privilege(c.oid, a.attnum, 'SELECT'))
                ) AS columns_readable""", (table, list(names), table))
            if (set(row) != {"relation_exists", "columns_readable"}
                    or type(row["relation_exists"]) is not bool
                    or type(row["columns_readable"]) is not bool
                    or (row["relation_exists"] and not row["columns_readable"])
                    or (table in REQUIRED_TABLES and not row["relation_exists"])):
                raise PrivilegeGuardError("privilege_preflight_rejected")
        return {"status": "BOUNDED_PRIVILEGE_PREFLIGHT_PASSED", "server_version": version}
    except PrivilegeGuardError:
        raise
    except Exception:
        raise PrivilegeGuardError("privilege_preflight_unavailable") from None
