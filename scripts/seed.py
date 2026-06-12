"""Seed ClickHouse with a small demo table so the agent has data to query.

This is the 'always works' path: it inserts rows directly, so a live demo never
depends on Airbyte being set up. Run with:  python -m scripts.seed
"""
from datetime import datetime, timedelta

from app.db import get_client

USERS = ["alice", "bob", "carol", "dave", "erin"]
PRODUCTS = [
    ("sauna bucket", 39.0),
    ("birch whisk", 24.5),
    ("thermometer", 18.0),
    ("ladle", 15.5),
    ("essential oil", 12.0),
    ("hourglass", 28.0),
]


def rows():
    base = datetime(2026, 6, 1, 9, 0, 0)
    rid = 0
    for day in range(10):
        for u_i, user in enumerate(USERS):
            # deterministic but varied: each user buys a couple of products per day
            for p_i in range((u_i + day) % 3 + 1):
                product, price = PRODUCTS[(rid + p_i) % len(PRODUCTS)]
                qty = (rid % 3) + 1
                rid += 1
                yield [
                    rid,
                    user,
                    product,
                    round(price * qty, 2),
                    base + timedelta(days=day, hours=u_i),
                ]


def main():
    client = get_client()
    client.command(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id      UInt64,
            user    String,
            product String,
            amount  Float64,
            ts      DateTime
        ) ENGINE = MergeTree ORDER BY id
        """
    )
    client.command("TRUNCATE TABLE purchases")
    data = list(rows())
    client.insert(
        "purchases",
        data,
        column_names=["id", "user", "product", "amount", "ts"],
    )
    count = client.query("SELECT count() FROM purchases").result_rows[0][0]
    print(f"Seeded `purchases`: inserted {count} rows.")


if __name__ == "__main__":
    main()
