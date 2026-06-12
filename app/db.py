"""ClickHouse client + helpers shared by the seed script and the agent."""
import clickhouse_connect

from app.config import settings


def get_client():
    """Open a ClickHouse client.

    ClickHouse Cloud: HTTPS on port 8443 with secure=True (the defaults here).
    Local Docker:     set CLICKHOUSE_PORT=8123 and CLICKHOUSE_SECURE=false.
    """
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        secure=settings.clickhouse_secure,
    )


def schema_text(client) -> str:
    """Return a compact `table.column (type)` listing of the current database.

    Injected into the agent's system prompt so Claude knows what it can query.
    """
    rows = client.query(
        "SELECT table, name, type FROM system.columns "
        "WHERE database = currentDatabase() "
        "ORDER BY table, position"
    ).result_rows
    if not rows:
        return "(no tables yet — run `make seed` or an Airbyte sync)"
    return "\n".join(f"{table}.{col} ({typ})" for table, col, typ in rows)


def run_sql(client, sql: str) -> str:
    """Execute a query and return rows as text, or the error string on failure.

    Returning the error (instead of raising) is what lets the agent read what
    went wrong and retry with corrected SQL.
    """
    try:
        result = client.query(sql)
        header = ", ".join(result.column_names)
        body = "\n".join(", ".join(str(v) for v in row) for row in result.result_rows)
        return f"{header}\n{body}" if body else f"{header}\n(no rows)"
    except Exception as exc:  # noqa: BLE001 - surface any DB error back to the model
        return f"ERROR: {exc}"
