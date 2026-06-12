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
    "You answer questions about data stored in a ClickHouse database. "
    "Use the run_sql tool to inspect and query the data — write standard "
    "ClickHouse SQL. Prefer a single query when you can. When you have the "
    "answer, state it in one or two plain sentences. Do not invent numbers; "
    "only report what the query returned."
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
    }
]

MAX_STEPS = 6


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
            if block.type == "tool_use" and block.name == "run_sql":
                sql = block.input["sql"]
                queries.append(sql)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": run_sql(ch, sql),
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    final = ""
    if resp is not None:
        final = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not final:
        final = "I couldn't reach a final answer within the step limit."
    return {"answer": final, "queries": queries}
