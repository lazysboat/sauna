# CLAUDE.md — operating guide for spinning up `sauna`

This file is for an AI coding agent (Claude Code) helping a user get this project running.
Read `docs/ARCHITECTURE.md` for how it works; this file is the **runbook**.

## What this project is

A natural-language → SQL demo: a FastAPI app where Claude answers questions about data in
**ClickHouse** by writing and running SQL (a tool-use loop with one `run_sql` tool).
**ClickHouse** stores the data, **Airbyte** (optional) loads it, **Render** (optional) hosts it.

## Secrets the human must provide — ASK, don't invent

You cannot fabricate these. Ask the user for them and have them paste the values into `.env`:

1. **`ANTHROPIC_API_KEY`** — an Anthropic API key (`sk-ant-...`). Required.
2. **ClickHouse Cloud connection** — required. The user creates a free service at
   <https://clickhouse.cloud>, opens the **Connect** panel, and copies:
   - `CLICKHOUSE_HOST` (e.g. `xxxx.us-east-2.aws.clickhouse.cloud`)
   - `CLICKHOUSE_PASSWORD`
   (User stays `default`, port `8443`, secure `true` — already defaulted.)

Airbyte and Render are **optional** (see below) and not needed for a local demo.

## Spin-up procedure (local)

```bash
cp .env.example .env       # then the user fills in ANTHROPIC_API_KEY + CLICKHOUSE_HOST + CLICKHOUSE_PASSWORD
make install               # builds a local .venv and installs deps
make seed                  # creates `purchases` and inserts ~99 demo rows into ClickHouse
make run                   # serves on http://localhost:8000
```

Then verify:

```bash
curl -s localhost:8000/health           # -> {"ok":true}
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question":"top 3 products by total amount"}'
# -> {"answer":"...","queries":["SELECT ..."]}
```

If `/ask` returns a real answer with a `queries` array, it is working. Open
`http://localhost:8000` for the web UI.

## Known gotchas (these WILL bite — handle proactively)

1. **PEP 668 / externally-managed Python.** Do NOT run `pip install -r requirements.txt`
   directly — on many systems it errors with `externally-managed-environment`. Always use
   `make install`, which creates a local `.venv` (prefers `uv`, falls back to `python3 -m venv`).
   If `python3 -m venv` fails (`ensurepip` missing) and `uv` isn't present, install `uv`
   (`pip install --user uv` or the user's package manager) or `apt install python3-venv`.

2. **Adaptive thinking is model-gated.** The default model `claude-opus-4-8` supports it.
   If the user sets `CLAUDE_MODEL` to an older model (e.g. `claude-opus-4-5`), the app now
   **auto-falls-back** when the API rejects `thinking:{type:"adaptive"}` — no action needed,
   but if you see a 400 mentioning "adaptive thinking", that's expected and handled.

3. **`make seed` must run before asking**, or there are no tables. (If skipped, the agent
   correctly answers "there's no data" rather than erroring.)

4. **ClickHouse Cloud uses HTTPS on port 8443 with `secure=true`.** A local Docker ClickHouse
   uses port `8123` and `secure=false` — set those in `.env` if running ClickHouse locally.

5. **ClickHouse Cloud IP allow-list.** If the connection times out, the service may restrict
   IPs — have the user allow their IP (and Airbyte's egress IPs if using Airbyte).

## Optional: real ingestion (Airbyte) and deployment (Render)

- **Airbyte** — replaces `seed.py` with a real ELT sync. See `airbyte/README.md`
  (Faker source → ClickHouse destination). The app needs no changes; it reads whatever
  schema lands in ClickHouse.
- **Render** — deploy the app: push to GitHub, then Render → New → Blueprint (reads
  `render.yaml`). Set `ANTHROPIC_API_KEY`, `CLICKHOUSE_HOST`, `CLICKHOUSE_PASSWORD` in the
  dashboard. Verify `GET https://<service>.onrender.com/health`.

## Map of the repo

```
app/config.py   env settings (CLAUDE_MODEL default claude-opus-4-8)
app/db.py       ClickHouse client, schema_text(), run_sql()
app/agent.py    Claude tool-use loop (run_sql tool, self-correcting, thinking fallback)
app/main.py     FastAPI: /health, POST /ask, GET / (web UI)
scripts/seed.py direct-insert demo data (no Airbyte needed)
airbyte/README  Faker -> ClickHouse click-path
render.yaml     one-service Render Blueprint
Makefile        install / seed / run / clean (auto-venv)
docs/ARCHITECTURE.md  how it all works
```

## Definition of done

`make install && make seed && make run` succeed, `/health` returns `{"ok":true}`, and a
`POST /ask` returns an `answer` plus the `queries` the agent ran.
