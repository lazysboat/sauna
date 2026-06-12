"""ClickHouse persistence for experiences & sessions.

ClickHouse is OLAP — no in-place UPDATE/DELETE — so we use the standard simple
pattern: ReplacingMergeTree keyed by id with a monotonically increasing
`_version`; an upsert inserts a new version row, a delete inserts a tombstone
(`_deleted = 1`), and reads use FINAL to collapse to the latest version.
Tiny data, hackathon scale — FINAL is fine.
"""
import time

from app.models import Experience, Session

_EXPERIENCE_COLS = [
    "id", "title", "location", "description", "priceAmount",
    "priceUnit", "capacity", "durationHours", "status",
]
_SESSION_COLS = ["id", "experienceId", "date", "time", "status"]

_tables_ready = False


def ensure_tables(client) -> None:
    global _tables_ready
    if _tables_ready:
        return
    client.command(
        """
        CREATE TABLE IF NOT EXISTS experiences (
            id            String,
            title         String,
            location      String,
            description   String,
            priceAmount   Float64,
            priceUnit     String,
            capacity      UInt32,
            durationHours Float64,
            status        String,
            _deleted      UInt8 DEFAULT 0,
            _version      UInt64
        ) ENGINE = ReplacingMergeTree(_version) ORDER BY id
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id           String,
            experienceId String,
            date         String,
            time         String,
            status       String,
            _deleted     UInt8 DEFAULT 0,
            _version     UInt64
        ) ENGINE = ReplacingMergeTree(_version) ORDER BY id
        """
    )
    _tables_ready = True


def _insert(client, table: str, cols: list[str], values: list, deleted: int = 0) -> None:
    client.insert(
        table,
        [values + [deleted, time.time_ns()]],
        column_names=cols + ["_deleted", "_version"],
    )


# --- experiences ---

def list_experiences(client) -> list[Experience]:
    rows = client.query(
        f"SELECT {', '.join(_EXPERIENCE_COLS)} FROM experiences FINAL "
        "WHERE _deleted = 0 ORDER BY title"
    ).result_rows
    return [Experience(**dict(zip(_EXPERIENCE_COLS, r))) for r in rows]


def upsert_experience(client, exp: Experience) -> Experience:
    _insert(client, "experiences", _EXPERIENCE_COLS,
            [getattr(exp, c) for c in _EXPERIENCE_COLS])
    return exp


def delete_experience(client, exp_id: str) -> None:
    _insert(client, "experiences", _EXPERIENCE_COLS,
            [exp_id, "", "", "", 0.0, "booking", 1, 0.0, "paused"], deleted=1)


# --- sessions ---

def list_sessions(client) -> list[Session]:
    rows = client.query(
        f"SELECT {', '.join(_SESSION_COLS)} FROM sessions FINAL "
        "WHERE _deleted = 0 ORDER BY date, time"
    ).result_rows
    return [Session(**dict(zip(_SESSION_COLS, r))) for r in rows]


def get_session(client, session_id: str) -> Session | None:
    rows = client.query(
        f"SELECT {', '.join(_SESSION_COLS)} FROM sessions FINAL "
        "WHERE _deleted = 0 AND id = %(id)s",
        parameters={"id": session_id},
    ).result_rows
    return Session(**dict(zip(_SESSION_COLS, rows[0]))) if rows else None


def upsert_session(client, ses: Session) -> Session:
    _insert(client, "sessions", _SESSION_COLS,
            [getattr(ses, c) for c in _SESSION_COLS])
    return ses


def delete_session(client, session_id: str) -> None:
    _insert(client, "sessions", _SESSION_COLS,
            [session_id, "", "", "", "open"], deleted=1)


def book_session(client, session_id: str) -> tuple[Session | None, str | None]:
    """Flip an open session to booked. Returns (session, error)."""
    ses = get_session(client, session_id)
    if ses is None:
        return None, "not_found"
    if ses.status == "booked":
        return ses, "already_booked"
    ses.status = "booked"
    upsert_session(client, ses)
    return ses, None
