# sauna — Technical Workflow

A natural-language → SQL analytics service. The user asks a question in English; a
Claude agent writes ClickHouse SQL, executes it, and returns a plain-language answer
plus the queries it ran.

## 1. System overview

```
┌──────────┐   ELT    ┌───────────────┐   SQL    ┌──────────────────────┐   HTTP   ┌─────────┐
│ Airbyte  │ ───────▶ │  ClickHouse   │ ◀──────▶ │  FastAPI app (agent) │ ◀──────▶ │  User   │
│  Cloud   │  loads   │    Cloud      │  queries │  Claude tool-use loop │  /ask    │ browser │
└──────────┘          └───────────────┘          └──────────────────────┘          └─────────┘
   (or scripts/seed.py)                                 hosted on Render
```

| Layer | Tech | Responsibility |
|-------|------|----------------|
| Ingestion | Airbyte Cloud (Faker→ClickHouse), or `scripts/seed.py` | Populate ClickHouse tables |
| Storage / compute | ClickHouse Cloud (OLAP) | Hold data, execute SQL |
| Application / agent | FastAPI + Anthropic SDK (`app/`) | Translate question → SQL → answer |
| Hosting | Render (web service) | Run the app, expose HTTP |
| LLM | Claude (`claude-opus-4-8` default) | SQL generation + answer synthesis |

## 2. Components (`app/`)

- **`config.py`** — `Settings` (pydantic-settings) loads all config from env / `.env`:
  Anthropic key, model, ClickHouse connection. Single `settings` instance.
- **`db.py`** — ClickHouse access:
  - `get_client()` — `clickhouse_connect` client (Cloud: HTTPS:8443, `secure=True`).
  - `schema_text(client)` — introspects `system.columns` → `table.column (type)` listing,
    injected into the prompt so the model knows the schema at query time (no hardcoding).
  - `run_sql(client, sql)` — executes a query; returns formatted rows **or an `ERROR: …`
    string** (never raises). This is what lets the agent self-correct.
- **`agent.py`** — the agent loop (§4). One tool, `run_sql`; system prompt + live schema;
  `_create()` wrapper for model compatibility.
- **`main.py`** — FastAPI surface: `GET /health`, `POST /ask`, `GET /` (web UI). Lazy,
  cached ClickHouse client so the app boots without a live DB.

## 3. Request lifecycle (`POST /ask`)

```
1. Client POSTs {"question": "..."} to /ask
2. main.ask() → agent.answer(question, clickhouse_client)
3. answer() builds system prompt = SYSTEM + live schema_text(ch)
4. Tool-use loop (max 6 steps):
     a. Claude.messages.create(model, tools=[run_sql], messages, [thinking])
     b. stop_reason == "tool_use"?
          yes → for each run_sql block: execute via db.run_sql(),
                return tool_result (with matching tool_use_id) → loop
          no  → break (final answer)
5. Collect final text + list of queries run
6. Return {"answer": str, "queries": [str, ...]}
```

## 4. The agent loop (core logic)

A **manual agentic loop** over the Anthropic Messages API:

1. Send the question with the `run_sql` tool available.
2. If `response.stop_reason == "tool_use"`: append `response.content` as the assistant
   turn, run each requested query, append one `tool_result` per call (keyed by
   `tool_use_id`), and re-invoke the model.
3. If `stop_reason != "tool_use"` (i.e. `end_turn`): stop — the response text is the answer.
4. Bounded by `MAX_STEPS = 6`.

**Self-correction:** a failed query returns an `ERROR: …` string as the tool result, so the
model reads the DB error and retries with corrected SQL instead of the request crashing.

**Model compatibility (`_create`):** adaptive thinking (`thinking:{type:"adaptive"}`) is sent
only for models that accept it. On a `400 … "adaptive thinking is not supported"`, the wrapper
disables thinking and falls back — so any configured model works (it is supported on Claude
4.6+; older models like `claude-opus-4-5` are not).

## 5. Data ingestion paths

- **Demo / fallback** — `scripts/seed.py` (`python -m scripts.seed`): creates
  `purchases (id, user, product, amount, ts)` as `MergeTree`, truncates, inserts ~99
  deterministic fake rows. No external dependency; guarantees the demo works.
- **Real pipeline** — Airbyte Cloud: "Sample Data (Faker)" source → certified ClickHouse v2
  destination → Full-refresh/Overwrite sync. Swappable for any real source (Postgres, Stripe,
  GitHub) with **zero app changes**, because the agent reads whatever schema exists at query time.

> Connectivity caveat: if ClickHouse Cloud has an IP allow-list, Airbyte Cloud egress IPs must be allowed.

## 6. Configuration (env vars)

`ANTHROPIC_API_KEY`, `CLAUDE_MODEL` (default `claude-opus-4-8`); `CLICKHOUSE_HOST`,
`CLICKHOUSE_PORT` (8443), `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`,
`CLICKHOUSE_SECURE` (true). Local: `.env`. Render: dashboard env vars (secrets `sync:false`).

## 7. Deployment (Render)

`render.yaml` Blueprint → one `web` service: `pip install -r requirements.txt`, start
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health`. ClickHouse Cloud
and Airbyte Cloud remain external managed services; Render only runs the app and connects out.

## 8. Error handling & resilience

- `run_sql` converts DB exceptions → strings (agent recovers).
- `_create` degrades gracefully on unsupported thinking param.
- `/ask` wraps the agent in try/except → returns `{"answer": "Error: …"}` as JSON (never a bare 500).
- UI parses responses defensively and renders any error instead of hanging.
- Lazy ClickHouse client → app boots and `/health` passes even if the DB is briefly unreachable.

## 9. Local dev workflow

```bash
cp .env.example .env            # add key + ClickHouse Cloud creds
make install                    # creates .venv (uv, stdlib fallback), installs deps
make seed                       # load demo data into ClickHouse
make run                        # uvicorn on :8000  → open http://localhost:8000
```

## 10. Scope / non-goals

No auth (demo); read-only by intent (enforce with a read-only ClickHouse user in prod);
single database; cloud provisioning is console-driven, not scripted; `seed.py` exists so
demos never hard-depend on Airbyte.
