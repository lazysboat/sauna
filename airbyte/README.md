# Airbyte → ClickHouse (the ingestion pipeline)

Airbyte is the **ELT** layer: it extracts data from a source and loads it into ClickHouse.
For the demo we use Airbyte's built-in **Sample Data (Faker)** source so there's nothing to
configure on the source side. (The `scripts/seed.py` fallback already gives the agent data to
query — this is the "real pipeline" version.)

## Steps (Airbyte Cloud)

1. **Source** → *New source* → **Sample Data (Faker)**. Accept the defaults (it generates
   `users`, `products`, `purchases` streams). No credentials needed.

2. **Destination** → *New destination* → **ClickHouse** (the certified v2 connector). Fill in,
   from your ClickHouse Cloud "Connect" panel:
   - **Host**: `xxxxxxxx.region.provider.clickhouse.cloud`
   - **Port**: `8443`  •  **HTTPS / SSL**: on
   - **Username**: `default`  •  **Password**: your ClickHouse Cloud password
   - **Database**: `default`

   > ⚠️ **Connectivity gotcha:** if your ClickHouse Cloud service has an IP allow-list, add
   > Airbyte Cloud's egress IPs (or temporarily set it to "Anywhere" for the hackathon),
   > otherwise the connection test fails.

3. **Connection** → source = Faker, destination = ClickHouse.
   - Select the streams you want (e.g. `users`, `products`, `purchases`).
   - Sync mode: **Full refresh | Overwrite** (simplest; re-runs replace the data).
   - **Sync now**.

4. When the sync succeeds, the tables appear in ClickHouse. The agent introspects the schema
   automatically (`app/db.py: schema_text`), so you can immediately ask questions about the
   Faker tables — no app change.

## Going beyond the demo

Swap the Faker source for a real one (Postgres, GitHub, Stripe, a Google Sheet, a CSV…). The
ClickHouse destination and the whole app stay exactly the same — only the source changes.
