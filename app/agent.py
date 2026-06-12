"""The 'agent': a Claude tool-use loop that answers questions over ClickHouse.

Claude is given one tool, `run_sql`. It writes a query, sees the rows (or the
error), and keeps going until it can answer in plain language. Because a failed
query comes back as an error string rather than an exception, the loop is
self-correcting — Claude fixes its own bad SQL.
"""
import anthropic
from anthropic import Anthropic

from app.config import settings
from app.db import run_sql, schema_text

_client = Anthropic(api_key=settings.anthropic_api_key)

# Adaptive thinking improves SQL quality but is only supported on newer models
# (Claude 4.6+). If the configured model rejects it, we remember that and stop
# sending it — so the template works with whatever model the user picks.
_use_thinking = True


def _create(system, messages):
    global _use_thinking
    kwargs = dict(
        model=settings.claude_model,
        max_tokens=2000,
        system=system,
        tools=TOOLS,
        messages=messages,
    )
    if _use_thinking:
        try:
            return _client.messages.create(thinking={"type": "adaptive"}, **kwargs)
        except anthropic.BadRequestError as exc:
            if "thinking" in str(exc).lower():
                _use_thinking = False  # this model doesn't support it; fall through
            else:
                raise
    return _client.messages.create(**kwargs)

SYSTEM = (
    "You are a booking assistant for a directory of ~100 Finnish sauna "
    "experiences stored in ClickHouse. Use the run_sql tool to inspect and "
    "query the data — write standard ClickHouse SQL. The `experiences` table "
    "is the catalog (title, provider, city, location, description, priceAmount, "
    "priceUnit, capacity, durationHours, status) and `sessions` are the "
    "availability — bookable date+time slots (status 'open' or 'booked'); "
    "sessions.experienceId joins to experiences.id. Filter by city, capacity, "
    "price or description keywords to narrow the 100 saunas down. "
    "These tables use ReplacingMergeTree: always query them with FINAL and "
    "WHERE _deleted = 0. "
    "When the user asks to book something, find a matching OPEN session via SQL, "
    "then call book_session with its id. Only published experiences are bookable. "
    "Never book without finding a concrete session first; if nothing matches, say so. "
    "When you have the answer, state it in a few plain sentences (name the sauna, "
    "city, date, time and price). Do not invent data; only report what the tools "
    "returned."
)

TOOLS = [
    {
        "name": "run_sql",
        "description": (
            "Run a single read-only ClickHouse SQL query and return the rows. "
            "If the query errors, you get the error text back — fix it and try again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "ClickHouse SQL"}},
            "required": ["sql"],
        },
    },
    {
        "name": "book_session",
        "description": (
            "Book an open session by its id (sessions.id), flipping it to 'booked'. "
            "Call this only after finding the session via run_sql. Returns the "
            "booked session, or an error if it doesn't exist / is already booked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string", "description": "sessions.id"}},
            "required": ["session_id"],
        },
    },
]

MAX_STEPS = 6


def _book(ch, session_id: str) -> str:
    """Execute a booking for the agent; errors come back as text it can act on."""
    from app import store

    try:
        store.ensure_tables(ch)
        ses, err = store.book_session(ch, session_id)
        if err == "not_found":
            return f"ERROR: no session with id {session_id}"
        if err == "already_booked":
            return f"ERROR: session {session_id} is already booked"
        if err == "not_published":
            return (
                f"ERROR: the sauna for session {session_id} is not on the "
                "platform (not published) — pick a published one"
            )
        return f"BOOKED: {ses.model_dump_json()}"
    except Exception as exc:  # noqa: BLE001 - surface to the model
        return f"ERROR: {exc}"


def answer(question: str, ch) -> dict:
    """Run the tool-use loop for one question. `ch` is a ClickHouse client.

    Returns {"answer": str, "queries": list[str]}.
    """
    system = SYSTEM + "\n\nSchema:\n" + schema_text(ch)
    messages = [{"role": "user", "content": question}]
    queries: list[str] = []
    resp = None

    for _ in range(MAX_STEPS):
        resp = _create(system, messages)

        if resp.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "run_sql":
                sql = block.input["sql"]
                queries.append(sql)
                out = run_sql(ch, sql)
            elif block.name == "book_session":
                out = _book(ch, block.input["session_id"])
                queries.append(f"-- book_session({block.input['session_id']}): {out}")
            else:
                out = f"ERROR: unknown tool {block.name}"
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )
        messages.append({"role": "user", "content": tool_results})

    final = ""
    if resp is not None:
        final = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not final:
        final = "I couldn't reach a final answer within the step limit."
    return {"answer": final, "queries": queries}
