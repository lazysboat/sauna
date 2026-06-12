# CLAUDE.md — operating guide for spinning up `sauna`

This file is for an AI coding agent (Claude Code) helping a user get this project running.
Read `docs/ARCHITECTURE.md` for how it works; this file is the **runbook**.

## What this project is

A sauna-experience **booking marketplace** (Löyly) with two interfaces over one
FastAPI + ClickHouse backend:

1. **Agent interface** — buyer agents book sessions: REST (`GET /catalog`,
   `POST /sessions/{id}/book`) or natural language via `POST /ask` (Claude tool-use
   loop with `run_sql` + `book_session` tools). `GET /` on :8000 is a dark-terminal
   chat UI for it.
2. **Sauna directory** — `frontend/` Next.js app (:3000): read-only summary of the
   onboarded saunas (image, provider, city, price, capacity) with upcoming
   availability (open sessions; click a card for the full schedule). Seeded by
   `make seed`; the agent books from the same data.

**Growth simulation:** the platform launches with **10 published saunas** (90 more
seeded as `paused`). The directory's **"Scout with Agent"** button (`POST
/simulate-month`) onboards 10 more per press, capped at 100 — the agent's bookable
world grows in sync (paused saunas 409 on booking). Hidden dev reset: **click the
"Month N · …" label 5 times quickly** (or `POST /dev/reset`) → fresh month-1 world.

**ClickHouse** stores everything (ReplacingMergeTree upsert/tombstone pattern —
query marketplace tables with `FINAL` + `WHERE _deleted = 0`), **Airbyte** (optional)
loads extra data, **Render** (optional) hosts the backend.

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

## Spin-up procedure (provider dashboard)

Needs Node 20+ (if missing, install user-locally via nvm — no sudo:
`curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash`
then `nvm install --lts`).

```bash
cd frontend && npm install && npm run dev    # http://localhost:3000
```

Verify: page shows "Saunas of Finland" with a grid of 100 sauna cards (images via
picsum.photos — needs internet), search + city filter, and dashed availability pills
(data comes from the backend, so the backend must be running). Booking demo:

```bash
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"Find a smoke sauna in Tampere for 10 people and book its earliest open slot"}'
# → answer + a "-- book_session(...)" entry in queries; refresh the directory and
#   that slot disappears from the card's availability pills
```

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
- **Render** — deploy both surfaces: push to GitHub, then Render → New → Blueprint (reads
  `render.yaml`: `sauna-agent` web service + `sauna-directory` static site). Prompted
  secrets: `ANTHROPIC_API_KEY`, `CLICKHOUSE_HOST`, `CLICKHOUSE_PASSWORD`, and
  `NEXT_PUBLIC_API_BASE_URL` (= the backend URL). Verify `GET <backend>/health`.
  Gotcha: ClickHouse Cloud's IP allow-list must permit Render egress.

## Map of the repo

```
app/config.py   env settings (CLAUDE_MODEL default claude-opus-4-8)
app/db.py       ClickHouse client, schema_text(), run_sql()
app/models.py   Pydantic Experience/Session (field names match frontend TS exactly)
app/store.py    marketplace persistence (ReplacingMergeTree upsert/tombstone/book)
app/crud.py     REST: /experiences, /sessions CRUD + /catalog + /sessions/{id}/book
app/agent.py    Claude tool-use loop (run_sql + book_session, self-correcting)
app/main.py     FastAPI: /health, POST /ask, GET / (terminal chat UI), CORS, crud router
scripts/seed.py 100 dummy saunas + ~350 availability sessions + purchases demo data
frontend/       Next.js sauna directory (read-only, Traverum design)
  src/lib/store.ts        the data seam: API-backed useExperiences/useSessions
  src/components/Directory.tsx  the 100-sauna grid w/ search, filter, availability
airbyte/README  Faker -> ClickHouse click-path
render.yaml     one-service Render Blueprint (backend only)
Makefile        install / seed / run / clean (auto-venv)
docs/ARCHITECTURE.md  how it all works
```

## Definition of done

`make install && make seed && make run` succeed, `/health` returns `{"ok":true}`,
`GET /experiences` returns 100 saunas, the directory on :3000 renders the grid with
images and availability pills, and a `POST /ask` asking to book an open slot returns
an `answer` with a `-- book_session(...)` entry in `queries` (the slot disappears
from the directory card after refresh).
