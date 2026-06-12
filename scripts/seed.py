"""Seed ClickHouse with the sauna-directory demo data.

Marketplace: 100 dummy saunas across Finland (one picsum image each) plus
dummy availability (open/booked sessions over the next two weeks). Generated
deterministically, so every run rebuilds the same world.
Run with:  python -m scripts.seed
"""
import random
from datetime import datetime, timedelta

from app.db import get_client

# --- sauna directory ------------------------------------------------------
# Content templates loosely based on real Finnish sauna offerings (titles,
# descriptions, realistic price/capacity ranges). No personal/contact data.
# (title, description, provider pattern, price unit, price range, capacity range, hours)
TEMPLATES = [
    (
        "Sauna raft cruise",
        "Wood-fired sauna boat cruising the lake, with hot tub, roof terrace, "
        "grill, changing room and shower. Winter cruises include ice swimming.",
        "{city} Saunalautta", "booking", (250, 700), (10, 20), (2, 3),
        "{city} lakeside",
    ),
    (
        "Sea sauna raft with ice swim",
        "Floating sauna raft on the seafront. Two hours of sauna and "
        "open-water dipping, departing from the city shoreline.",
        "{city} by Sea", "person", (12, 25), (10, 16), (2, 2),
        "{city} seafront",
    ),
    (
        "Traditional lakeside smoke sauna",
        "An authentic wood-heated smoke sauna with soft löyly by the lake, "
        "with a dock for swimming and winter ice dipping.",
        "Savusauna {city}", "booking", (250, 450), (8, 14), (3, 3),
        "{city} (lakeside)",
    ),
    (
        "Smoke sauna world with hot tubs",
        "A smoke-sauna complex with one or two wood-fired hot tubs and a "
        "groundwater pond for swimming. Evening-long private rental.",
        "{city} Verstas", "booking", (450, 600), (12, 18), (4, 4),
        "{city}",
    ),
    (
        "Smoke sauna & outdoor hot tub by the rapids",
        "Gentle smoke-sauna löyly, a warm outdoor hot tub on the terrace, "
        "and a jump straight into the river from the dock.",
        "Villa {city}", "person", (35, 55), (10, 14), (2, 2),
        "{city} riverside",
    ),
    (
        "Public wood-fired sauna on the waterfront",
        "A sculptural waterfront sauna with wood-fired saunas, a year-round "
        "water dip, and a restaurant. Two-hour session includes towel and "
        "seat cover.",
        "Sauna House {city}", "person", (18, 28), (16, 25), (2, 2),
        "{city} waterfront",
    ),
    (
        "Private downtown sauna for groups",
        "A central sauna space for groups, with lounge and shower "
        "facilities. Booked by the slot for private evenings.",
        "{city} Forum Sauna", "booking", (150, 260), (12, 20), (3, 3),
        "{city} centre",
    ),
    (
        "Large smoke sauna for big groups",
        "A spacious countryside smoke sauna for big groups — built for "
        "celebrations and company gatherings.",
        "{city} Country Sauna", "person", (20, 30), (30, 45), (3, 3),
        "{city} countryside",
    ),
]

CITIES = [
    "Tampere", "Helsinki", "Turku", "Oulu", "Jyväskylä", "Kuopio", "Lahti",
    "Rovaniemi", "Vaasa", "Joensuu", "Savonlinna", "Keuruu", "Laukaa",
    "Nakkila", "Lieto", "Espoo", "Porvoo", "Naantali", "Kuusamo",
    "Hämeenlinna", "Mikkeli", "Levi",
]

N_SAUNAS = 100


def generate_saunas():
    from app.models import Experience

    rng = random.Random(42)
    saunas = []
    for i in range(1, N_SAUNAS + 1):
        title, desc, provider_pat, unit, price_rng, cap_rng, hours_rng, loc_pat = (
            TEMPLATES[(i - 1) % len(TEMPLATES)]
        )
        city = rng.choice(CITIES)
        exp_id = f"exp-{i:03d}"
        price = rng.randint(*price_rng)
        if unit == "booking":
            price = round(price / 10) * 10  # round bookings to tens of euros
        saunas.append(Experience(
            id=exp_id,
            title=title,
            provider=provider_pat.format(city=city),
            city=city,
            location=loc_pat.format(city=city),
            description=desc,
            imageUrl=f"https://picsum.photos/seed/{exp_id}/600/400",
            priceAmount=price,
            priceUnit=unit,
            capacity=rng.randint(*cap_rng),
            durationHours=rng.randint(*hours_rng),
            status="published",
        ))
    return saunas


def generate_availability(saunas):
    """Realistic schedules over the next 21 days.

    Each sauna has a fixed weekly rhythm: a set of operating weekdays
    (public saunas run most days; private rentals lean Thu–Sun) and 1–3
    fixed daily start times. Near-term slots are more likely already
    booked (the market has been selling), far-out dates are mostly open.
    """
    from app.models import Session

    rng = random.Random(43)
    today = datetime.now().date()
    sessions = []
    for n, sauna in enumerate(saunas):
        # weekly rhythm — per-person/public saunas operate more days than
        # private full-booking rentals
        if sauna.priceUnit == "person":
            n_days = rng.randint(5, 7)
        else:
            n_days = rng.randint(3, 4)
        weekend_first = [3, 4, 5, 6, 0, 1, 2]  # Thu Fri Sat Sun Mon Tue Wed
        operating_weekdays = set(weekend_first[:n_days])
        if n_days < 7:  # vary which weekdays beyond the weekend core
            operating_weekdays = set(rng.sample(weekend_first[:4], min(3, n_days)))
            extra = [d for d in range(7) if d not in operating_weekdays]
            operating_weekdays |= set(rng.sample(extra, n_days - len(operating_weekdays)))

        start_hours = sorted(rng.sample([14, 15, 16, 17, 18, 19, 20], rng.randint(1, 3)))

        for day in range(1, 22):
            date = today + timedelta(days=day)
            if date.weekday() not in operating_weekdays:
                continue
            # closer dates are more sold; weekends sell better too
            p_booked = 0.55 if day <= 7 else 0.30 if day <= 14 else 0.12
            if date.weekday() >= 4:  # Fri/Sat/Sun
                p_booked = min(0.85, p_booked + 0.15)
            for hour in start_hours:
                sessions.append(Session(
                    id=f"s-{n + 1:03d}-{day:02d}{hour:02d}",
                    experienceId=sauna.id,
                    date=date.isoformat(),
                    time=f"{hour:02d}:00",
                    status="booked" if rng.random() < p_booked else "open",
                ))
    return sessions


def seed_marketplace(client):
    from app import store

    # Dummy data: always rebuild from scratch (also migrates schema changes).
    client.command("DROP TABLE IF EXISTS experiences")
    client.command("DROP TABLE IF EXISTS sessions")
    store._tables_ready = False
    store.ensure_tables(client)

    saunas = generate_saunas()
    sessions = generate_availability(saunas)
    store.bulk_upsert_experiences(client, saunas)
    store.bulk_upsert_sessions(client, sessions)
    n_open = sum(1 for s in sessions if s.status == "open")
    print(
        f"Seeded directory: {len(saunas)} saunas, "
        f"{len(sessions)} sessions ({n_open} open)."
    )


# --- purchases (the original SQL-agent demo table, kept for /ask Q&A) ------
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
    seed_marketplace(client)
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
