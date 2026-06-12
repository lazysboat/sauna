# sauna 🧖

A minimal, **working** template that wires together three tools for a hackathon:

| Tool | Role |
|------|------|
| **ClickHouse** (Cloud) | Analytical (OLAP) database — stores the data, runs the SQL |
| **Airbyte** (Cloud) | ELT ingestion — loads data *into* ClickHouse |
| **Render** | Hosts the app |
| **Claude** (agent) | A FastAPI app that turns natural-language questions into ClickHouse SQL, runs it, and answers |

```
Airbyte "Sample Data (Faker)"  ──ELT──▶  ClickHouse Cloud  ◀──SQL──  FastAPI agent  ◀── you
        (or scripts/seed.py)             (OLAP store)               (Claude tool-use loop)
                                                                    deployed on Render
```

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

`make seed` means the demo works immediately, with no dependency on Airbyte.

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
