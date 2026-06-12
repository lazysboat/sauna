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
    "is the catalog (title, provider, city, location, description, imageUrl, "
    "priceAmount, priceUnit, capacity, durationHours, status) and `sessions` "
    "are the availability — bookable date+time slots (status 'open' or 'booked'); "
    "sessions.experienceId joins to experiences.id. Filter by city, capacity, "
    "price or description keywords to narrow the 100 saunas down. "
    "These tables use ReplacingMergeTree: always query them with FINAL and "
    "WHERE _deleted = 0. "
    "When the user asks to book something, find a matching OPEN session via SQL, "
    "then call book_session with its id. Only published experiences are bookable. "
    "Never book without finding a concrete session first; if nothing matches, say so. "
    "\n\n"
    "PRESENTATION: whenever your answer is about one or more specific saunas "
    "(search results, availability, or a booking confirmation), ALWAYS also "
    "`SELECT experiences.imageUrl` and call the `present_ui` tool to render rich "
    "sauna cards with images — do not describe saunas in prose alone. After "
    "present_ui, add one short plain sentence summarising the result. For "
    "non-sauna analytics (revenue totals, counts, generic questions) just answer "
    "in plain sentences and skip present_ui. "
    "Do not invent data; only report what the tools returned."
)

# OpenUI Lang guide embedded in the present_ui tool. OpenUI Lang is a compact,
# line-oriented DSL the renderer (browser bundle in main.py) turns into live
# React cards. Signatures below are a tailored subset of @openuidev's chat
# library — keep them in sync with the bundle version pinned in main.py.
OPENUI_GUIDE = (
    "Render sauna results as visual cards. The `ui` argument must be a complete "
    "OpenUI Lang program — a declarative, line-oriented UI language. Rules:\n"
    "1. One statement per line: `name = Expression`.\n"
    "2. The FIRST line must be `root = Card([...])`. Card is the response container.\n"
    "3. Arguments are POSITIONAL (order matters, never `key: value`). Strings use "
    "double quotes.\n"
    "4. Every name you define (except root) must be referenced from another line, "
    "or it is silently dropped.\n"
    "5. Use REAL data from your SQL rows — never invent saunas, prices or ids.\n\n"
    "Components you may use (positional args):\n"
    "- Card(children[]) — root container; children stack vertically.\n"
    "- TextContent(text, size?) — text; size one of "
    "\"small\"|\"default\"|\"large\"|\"small-heavy\"|\"large-heavy\". Use for the "
    "intro line and per-sauna price/capacity/time details.\n"
    "- CardHeader(title, subtitle?) — sauna name as title, \"City · Provider\" as "
    "subtitle.\n"
    "- ImageBlock(src, alt?) — the sauna image; src = the row's imageUrl. If "
    "imageUrl is empty use \"https://picsum.photos/seed/<experienceId>/800/500\".\n"
    "- TagBlock(tags[]) — short string tags, e.g. [\"smoke sauna\",\"lakeside\"].\n"
    "- Button(label, action?) — a Book button; action = an Action expression.\n"
    "- Action([@ToAssistant(\"...\")]) — clicking sends that text back as a new "
    "message. For booking use @ToAssistant(\"Book session <sessions.id>\").\n"
    "- Carousel(slides[][]) — horizontal scroll of cards; each slide is an array of "
    "components and EVERY slide must have the same component types in the same "
    "order. Use this when showing 2+ saunas.\n"
    "- Separator() — a divider, useful between stacked saunas.\n\n"
    "Example — two matching saunas (use this shape; substitute real values):\n"
    "root = Card([intro, gallery])\n"
    "intro = TextContent(\"Found 2 smoke saunas in Tampere\", \"large-heavy\")\n"
    "gallery = Carousel([[h1, img1, d1, t1, b1], [h2, img2, d2, t2, b2]])\n"
    "h1 = CardHeader(\"Kuuma Savusauna\", \"Tampere · Löyly Co\")\n"
    "img1 = ImageBlock(\"https://picsum.photos/seed/exp-1a2b/800/500\", \"Kuuma Savusauna\")\n"
    "d1 = TextContent(\"€120 / booking · up to 12 people · Sat 18:00\", \"default\")\n"
    "t1 = TagBlock([\"smoke sauna\", \"lakeside\", \"12 ppl\"])\n"
    "b1 = Button(\"Book Sat 18:00\", Action([@ToAssistant(\"Book session s-111aaa\")]))\n"
    "h2 = CardHeader(\"Järvi Savusauna\", \"Tampere · Sauna Society\")\n"
    "img2 = ImageBlock(\"https://picsum.photos/seed/exp-3c4d/800/500\", \"Järvi Savusauna\")\n"
    "d2 = TextContent(\"€90 / person · up to 8 people · Sun 15:00\", \"default\")\n"
    "t2 = TagBlock([\"smoke sauna\", \"wood-fired\"])\n"
    "b2 = Button(\"Book Sun 15:00\", Action([@ToAssistant(\"Book session s-222bbb\")]))\n\n"
    "For a SINGLE sauna, skip the Carousel and stack directly: "
    "root = Card([header, image, details, tags, bookBtn]). For a booking "
    "confirmation, render one card and set the intro/title to confirm it is booked."
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
    {
        "name": "present_ui",
        "description": (
            "Render rich visual sauna cards (image, name, city/provider, price, "
            "capacity, a Book button) to the user instead of a plain paragraph. "
            "Call this whenever your answer concerns one or more specific saunas.\n\n"
            + OPENUI_GUIDE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ui": {
                    "type": "string",
                    "description": "A complete OpenUI Lang program starting with `root = Card([...])`.",
                }
            },
            "required": ["ui"],
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

    Returns {"answer": str, "ui": str | None, "queries": list[str]}.
    `ui` is an OpenUI Lang program (rendered as sauna cards by the chat UI) when
    the agent chose to present results visually, else None.
    """
    system = SYSTEM + "\n\nSchema:\n" + schema_text(ch)
    messages = [{"role": "user", "content": question}]
    queries: list[str] = []
    ui: str | None = None
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
            elif block.name == "present_ui":
                ui = block.input.get("ui") or ui
                queries.append(f"-- present_ui: rendered sauna cards ({len(ui or '')} chars)")
                out = (
                    "UI rendered to the user. Now reply with one short plain-text "
                    "sentence summarising the result."
                )
            else:
                out = f"ERROR: unknown tool {block.name}"
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )
        messages.append({"role": "user", "content": tool_results})

    final = ""
    if resp is not None:
        final = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not final and not ui:
        final = "I couldn't reach a final answer within the step limit."
    return {"answer": final, "ui": ui, "queries": queries}
