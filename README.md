# sauna 🧖 — Löyly booking marketplace

A sauna-experience **booking marketplace** with two interfaces over one FastAPI +
ClickHouse backend:

1. **Agent interface** — buyer agents discover and book sessions: REST
   (`GET /catalog`, `POST /sessions/{id}/book`) or natural language via `POST /ask`
   (a Claude tool-use agent that writes SQL *and* can call `book_session`). The
   page at :8000 is a deliberate dark-terminal chat UI for this agent.
2. **Sauna directory** (`frontend/`, Next.js on :3000) — a read-only summary of
   **100 saunas across Finland**: one image each, provider, city, price, capacity,
   and upcoming **availability** (the open sessions the agent can book).

```
 Sauna directory (Next.js :3000)             Buyer agent (:8000 terminal UI)
   100 saunas · images · availability       "book me a smoke sauna in Tampere…"
            │  read-only                           │  /ask · /catalog · /book
            ▼                                      ▼
        FastAPI backend (:8000) ── Claude tool-use loop (run_sql + book_session)
            │
        ClickHouse Cloud  ◀──ELT── Airbyte (optional)
```

| Tool | Role |
|------|------|
| **ClickHouse** (Cloud) | Stores experiences, sessions, demo data; runs the agent's SQL |
| **Airbyte** (Cloud) | Optional ELT ingestion into ClickHouse |
| **Render** | Hosts the backend |
| **Claude** | Booking agent: NL → SQL → answer, plus the `book_session` tool |

The "agent" is a small Claude **tool-use loop**: Claude is given one `run_sql` tool, writes a
query, sees the rows (or the error), and self-corrects until it can answer in plain language.

> Airbyte is a data-integration platform, not an agent framework — here it's the ingestion that
> fills ClickHouse. The agent is the Claude app in `app/`.

**Docs:** [`CLAUDE.md`](CLAUDE.md) — runbook for getting it running (an AI agent can follow it
unattended) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how it works internally.

> **Sharing this?** Push to a Git repo and send the link. `.env` (your secrets) is gitignored
> and will **not** travel with it — the recipient adds their own keys per `.env.example`. Their
> Claude Code can read `CLAUDE.md` and spin the whole thing up.

## Prerequisites

- Python 3.10+
- A **ClickHouse Cloud** account (free trial) — create a service, open **Connect**, copy the
  host + password.
- An **Anthropic API key**.
- (Optional) an **Airbyte Cloud** account for the real ingestion pipeline.
- (Optional) a **Render** account for deployment.

## Quick start (local, ~5 min)

```bash
cp .env.example .env      # then fill in ANTHROPIC_API_KEY + ClickHouse Cloud host/password
make install
make seed                 # creates `purchases` and inserts demo rows directly into ClickHouse
make run                  # http://localhost:8000
```

Open <http://localhost:8000> and ask, e.g.:
- "how many purchases were over 100?"
- "top 5 products by total amount"
- "average amount per user, top 3"

Or via the API:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"top 5 products by total amount"}'
# -> {"answer": "...", "queries": ["SELECT ..."]}
```

`make seed` rebuilds the whole demo world deterministically: **100 dummy saunas**
(8 content archetypes × 20 Finnish cities, one picsum image each) with realistic
schedules — ~3,000 availability sessions over three weeks, more booked near-term.
The platform "launches" with **10 saunas onboarded**; the directory's **Scout with
Agent** button (`POST /simulate-month`) onboards 10 more per press up to 100, and
the agent's bookable catalog grows in sync. Hidden dev reset: click the
"Month N · …" label in the directory 5 times quickly (or `POST /dev/reset`).

## The sauna directory (frontend/)

Next.js app (Tailwind v4, lucide-react) in the Traverum design — a read-only grid
of all 100 saunas with image, provider · city, price, capacity, duration and the
next open slots as dashed pills ("Fully booked" when none). Client-side search +
city filter. Needs Node 20+:

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000 (backend must be running on :8000)
```

Data comes from the same REST API (`/experiences`, `/sessions`) the agent uses.
Override the API origin with `NEXT_PUBLIC_API_BASE_URL` (defaults to
`http://localhost:8000`).

## The agent booking interface

```bash
curl -s localhost:8000/catalog                      # published experiences + open sessions
curl -s -X POST localhost:8000/sessions/<id>/book   # book (409 if already booked)
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"Book the earliest open session for the raft cruise"}'
```

The `/ask` agent finds a matching open session via SQL, books it with its
`book_session` tool, and the pill flips to solid (booked) in the owner's calendar.

## The real ingestion pipeline (Airbyte)

To load data the "proper" way instead of `seed.py`, follow [`airbyte/README.md`](airbyte/README.md):
Airbyte **Sample Data (Faker)** source → **ClickHouse** destination → **Sync**. The agent picks up
the new tables automatically (it introspects the schema at query time).

## Deploy to Render

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** → select the repo. It reads [`render.yaml`](render.yaml) and
   creates one web service.
3. Set the secret env vars in the dashboard: `ANTHROPIC_API_KEY`, `CLICKHOUSE_HOST`,
   `CLICKHOUSE_PASSWORD` (the rest have defaults in `render.yaml`).
4. After deploy, check `GET https://<service>.onrender.com/health` → `{"ok": true}`, then open the URL.

> ClickHouse Cloud and Airbyte Cloud are managed separately — Render only runs the app and connects
> out to ClickHouse Cloud. (Render has no managed ClickHouse; ClickHouse Cloud is the simplest store.)

## Configuration

All config is env vars (see `.env.example`). Notable one:

- `CLAUDE_MODEL` — defaults to `claude-opus-4-8` (best quality). For cheaper/faster demos use
  `claude-sonnet-4-6` or `claude-haiku-4-5` — no code change.

## Project layout

```
app/
  config.py   env-var settings
  db.py       ClickHouse client + schema introspection + run_sql
  agent.py    Claude tool-use loop (the "agent")
  main.py     FastAPI: GET /health, POST /ask, GET / (web UI)
scripts/
  seed.py     direct-insert demo data (the always-works fallback)
airbyte/
  README.md   Faker -> ClickHouse click-path
render.yaml   one-service Render Blueprint
```

## Notes / scope

- No auth on the app — it's a hackathon demo. Don't expose it publicly with real data as-is.
- The agent is read-only in spirit (it only needs SELECT); use a read-only ClickHouse user in
  production to enforce that.
