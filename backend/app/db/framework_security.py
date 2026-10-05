"""Close legacy ADK tables to Supabase API roles without moving or deleting data.

Current ADK sessions use veridra_private. Old releases may have left populated
framework tables in public; revoking API access preserves backend owner access.
Only the ADK allowlist is touched, and only when its metadata marker exists.
"""

from sqlalchemy.engine import Connection

LEGACY_ADK_TABLES = (
    "adk_internal_metadata", "app_states", "user_states", "sessions", "events",
)


def protect_legacy_framework_tables(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    if connection.exec_driver_sql(
        "SELECT to_regclass('public.adk_internal_metadata')"
    ).scalar_one_or_none() is None:
        return
    roles = ["PUBLIC"]
    for role in ("anon", "authenticated"):
        if connection.exec_driver_sql(
            f"SELECT 1 FROM pg_roles WHERE rolname = '{role}'"
        ).scalar_one_or_none() is not None:
            roles.append(role)
    for table in LEGACY_ADK_TABLES:
        # Identifiers come solely from the closed constants above, never users.
        qualified = f"public.{table}"
        if connection.exec_driver_sql(
            f"SELECT to_regclass('{qualified}')"
        ).scalar_one_or_none() is None:
            continue
        connection.exec_driver_sql(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        for role in roles:
            connection.exec_driver_sql(
                f"REVOKE ALL PRIVILEGES ON TABLE {qualified} FROM {role}"
            )
