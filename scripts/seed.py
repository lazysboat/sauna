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

# Real sauna photos from Wikimedia Commons, grouped to match the template
# archetypes (raft photos for raft cruises, savusauna photos for smoke saunas…).
_WM = "https://upload.wikimedia.org/wikipedia/commons"
IMAGES = {
    "raft": [
        f"{_WM}/thumb/6/63/Saunalautta_-_Saunaboat_-_panoramio.jpg/1280px-Saunalautta_-_Saunaboat_-_panoramio.jpg",
        f"{_WM}/thumb/7/7f/Saunalautta.jpg/1280px-Saunalautta.jpg",
        f"{_WM}/thumb/d/d3/Koivurannan_saunalautta_Oulu_20191005.jpg/1280px-Koivurannan_saunalautta_Oulu_20191005.jpg",
        f"{_WM}/thumb/c/c4/Koivurannan_saunalautta_Oulu_20201003_02.jpg/1280px-Koivurannan_saunalautta_Oulu_20201003_02.jpg",
        f"{_WM}/thumb/6/6a/Saarelan_saunalautta_Oulu_20250501.jpg/1280px-Saarelan_saunalautta_Oulu_20250501.jpg",
        f"{_WM}/thumb/2/2f/Saunalautta_Vuoksella_juhannusy%C3%B6n%C3%A4.JPG/1280px-Saunalautta_Vuoksella_juhannusy%C3%B6n%C3%A4.JPG",
        f"{_WM}/thumb/f/f0/Saunalautta_Vuoksella_juhannusaattona.JPG/1280px-Saunalautta_Vuoksella_juhannusaattona.JPG",
        f"{_WM}/thumb/d/dc/Saunalautta_2883-20-2.jpg/1280px-Saunalautta_2883-20-2.jpg",
        f"{_WM}/thumb/9/9e/Saunalaiva_hietalahti.jpg/1280px-Saunalaiva_hietalahti.jpg",
        f"{_WM}/thumb/8/85/Floating_Sauna_Pyhalahti_Fishing_Port.jpg/1280px-Floating_Sauna_Pyhalahti_Fishing_Port.jpg",
        f"{_WM}/thumb/b/be/Sauna%2C_Finland%2C_Turku%2C_sauna%2C_skinny_dipping%2C_houseboat%2C_20220910%2C_picture_1.jpg/1280px-Sauna%2C_Finland%2C_Turku%2C_sauna%2C_skinny_dipping%2C_houseboat%2C_20220910%2C_picture_1.jpg",
        f"{_WM}/thumb/7/78/Sauna%2C_Finland%2C_Turku%2C_sauna%2C_skinny_dipping%2C_houseboat%2C_20220910%2C_picture_2.jpg/1280px-Sauna%2C_Finland%2C_Turku%2C_sauna%2C_skinny_dipping%2C_houseboat%2C_20220910%2C_picture_2.jpg",
    ],
    "smoke": [
        f"{_WM}/9/9d/Suomalainen_savusauna.jpg",
        f"{_WM}/0/00/Finnish_Smoke_sauna.jpg",
        f"{_WM}/5/58/Finnish_smoke_sauna.jpg",
        f"{_WM}/thumb/0/0b/Traditional_Finnish_smoke_sauna.jpg/1280px-Traditional_Finnish_smoke_sauna.jpg",
        f"{_WM}/thumb/3/34/Savusauna.jpg/1280px-Savusauna.jpg",
        f"{_WM}/thumb/6/62/Savusauna_rovaniemi.jpg/1280px-Savusauna_rovaniemi.jpg",
        f"{_WM}/thumb/b/b5/Smoke_sauna_Muuratsalo_Experimental_House.jpg/1280px-Smoke_sauna_Muuratsalo_Experimental_House.jpg",
        f"{_WM}/thumb/5/5c/Smoke_Sauna_%28395139052%29.jpg/1280px-Smoke_Sauna_%28395139052%29.jpg",
        f"{_WM}/thumb/4/4a/Smoke_sauna_-_panoramio.jpg/1280px-Smoke_sauna_-_panoramio.jpg",
        f"{_WM}/thumb/b/b8/Smoke_Sauna_%2830765202172%29.jpg/1280px-Smoke_Sauna_%2830765202172%29.jpg",
        f"{_WM}/thumb/a/a1/Smoke_sauna%2C_Siida_Museum%2C_Inari%2C_Finland_%281%29_%2836637910296%29.jpg/1280px-Smoke_sauna%2C_Siida_Museum%2C_Inari%2C_Finland_%281%29_%2836637910296%29.jpg",
        f"{_WM}/thumb/e/e3/Tarvasp%C3%A4%C3%A4n_savusauna.jpg/1280px-Tarvasp%C3%A4%C3%A4n_savusauna.jpg",
        f"{_WM}/thumb/5/50/Myllym%C3%A4en_torpan_savusauna.jpg/1280px-Myllym%C3%A4en_torpan_savusauna.jpg",
        f"{_WM}/thumb/0/05/Public_Smoke_Sauna_at_Kuusij%C3%A4rvi%2C_Vantaa%2C_Finland%2C_January_2021.jpg/1280px-Public_Smoke_Sauna_at_Kuusij%C3%A4rvi%2C_Vantaa%2C_Finland%2C_January_2021.jpg",
        f"{_WM}/thumb/7/7f/Interior_of_a_smoke_sauna%2C_Uusikaupunki%2C_Finland_-_20030510.jpg/1280px-Interior_of_a_smoke_sauna%2C_Uusikaupunki%2C_Finland_-_20030510.jpg",
        f"{_WM}/thumb/7/7b/J%C3%A4rvenp%C3%A4%C3%A4_-_Suviranta_-_Smoke_Sauna_-_panoramio.jpg/1280px-J%C3%A4rvenp%C3%A4%C3%A4_-_Suviranta_-_Smoke_Sauna_-_panoramio.jpg",
        f"{_WM}/9/9e/2012-08-31_18.52.22_Savusauna.jpg",
    ],
    "public": [
        f"{_WM}/b/b7/Kotiharjun_yleinen_sauna_%28Kotiharju_public_sauna_in_Helsinki%29_Helsingin_Torkkelinm%C3%A4ell%C3%A4_Kalliossa_01.jpg",
        f"{_WM}/1/13/Kotiharjun_yleinen_sauna_%28Kotiharju_public_sauna_in_Helsinki%29_Helsingin_Torkkelinm%C3%A4ell%C3%A4_Kalliossa_02.jpg",
        f"{_WM}/b/bb/Kotiharjun_yleinen_sauna_%28Kotiharju_public_sauna_in_Helsinki%29_Helsingin_Torkkelinm%C3%A4ell%C3%A4_Kalliossa_03.jpg",
        f"{_WM}/thumb/5/5b/Rajaportin_sis%C3%A4%C3%A4nk%C3%A4ynti.jpg/1280px-Rajaportin_sis%C3%A4%C3%A4nk%C3%A4ynti.jpg",
        f"{_WM}/thumb/c/cf/Rajaportilla_vilvotellaan.jpg/1280px-Rajaportilla_vilvotellaan.jpg",
        f"{_WM}/thumb/d/dc/Saunabar%2C_Helsingfors.jpg/1280px-Saunabar%2C_Helsingfors.jpg",
        f"{_WM}/thumb/4/45/Clarion_Hotel_Helsinki%2C_Sauna%2C_20231215_-_03.jpg/1280px-Clarion_Hotel_Helsinki%2C_Sauna%2C_20231215_-_03.jpg",
        f"{_WM}/thumb/5/59/Finnish_Sauna_Society.jpg/1280px-Finnish_Sauna_Society.jpg",
    ],
    "shore": [
        f"{_WM}/thumb/4/44/Sauna_Sunset_%2830811239481%29.jpg/1280px-Sauna_Sunset_%2830811239481%29.jpg",
        f"{_WM}/thumb/7/7b/Fishing_hut_and_sauna_on_the_sea_%2893039%29.jpg/1280px-Fishing_hut_and_sauna_on_the_sea_%2893039%29.jpg",
        f"{_WM}/thumb/2/23/Seaside_sauna_in_Kirkkonummi.jpg/1280px-Seaside_sauna_in_Kirkkonummi.jpg",
        f"{_WM}/thumb/9/99/Selfmade_finnish_log_sauna.jpg/1280px-Selfmade_finnish_log_sauna.jpg",
        f"{_WM}/thumb/1/19/Wooden_sauna_building_not_in_use_in_Uutela%2C_Vuosaari%2C_Helsinki%2C_Finland%2C_2018_February.jpg/1280px-Wooden_sauna_building_not_in_use_in_Uutela%2C_Vuosaari%2C_Helsinki%2C_Finland%2C_2018_February.jpg",
        f"{_WM}/thumb/2/2b/Tarvo_sauna_%28May_2026%29.jpg/1280px-Tarvo_sauna_%28May_2026%29.jpg",
        f"{_WM}/thumb/7/7c/Suomenlinna-B60.jpg/1280px-Suomenlinna-B60.jpg",
        f"{_WM}/e/eb/Ruuhonsaaren-sauna.jpg",
        f"{_WM}/thumb/1/17/Rantasauna_Pyh%C3%A4lahti_Keitele_beach_%28Konnevesi%29.jpg/1280px-Rantasauna_Pyh%C3%A4lahti_Keitele_beach_%28Konnevesi%29.jpg",
        f"{_WM}/thumb/6/65/Saunas_of_Varala_Sports_Institute_in_Tahmela_20130206.jpg/1280px-Saunas_of_Varala_Sports_Institute_in_Tahmela_20130206.jpg",
        f"{_WM}/thumb/c/c2/Tynnyrisauna.JPG/1280px-Tynnyrisauna.JPG",
        f"{_WM}/thumb/d/d6/Bastun%2C_Mariehamn%2C_aland.jpg/1280px-Bastun%2C_Mariehamn%2C_aland.jpg",
        f"{_WM}/thumb/5/55/Inside_a_sauna_trailer_in_Haukilahti.jpg/1280px-Inside_a_sauna_trailer_in_Haukilahti.jpg",
        f"{_WM}/thumb/4/4e/Sauna-l%C3%B6yly.jpg/1280px-Sauna-l%C3%B6yly.jpg",
        f"{_WM}/9/94/Cooling_down_near_sauna.jpg",
        f"{_WM}/thumb/4/4b/Finnish_Sauna_-_panoramio.jpg/1280px-Finnish_Sauna_-_panoramio.jpg",
    ],
}

# image group per template (same order as TEMPLATES):
# raft cruise, sea raft, lakeside smoke, smoke world, rapids hot tub,
# public waterfront, downtown groups, big-group smoke
TEMPLATE_IMAGE_GROUP = [
    "raft", "raft", "smoke", "smoke", "shore", "public", "public", "smoke",
]

N_SAUNAS = 100


def generate_saunas():
    from app.models import Experience

    rng = random.Random(42)
    saunas = []
    for i in range(1, N_SAUNAS + 1):
        t_idx = (i - 1) % len(TEMPLATES)
        title, desc, provider_pat, unit, price_rng, cap_rng, hours_rng, loc_pat = (
            TEMPLATES[t_idx]
        )
        city = rng.choice(CITIES)
        exp_id = f"exp-{i:03d}"
        price = rng.randint(*price_rng)
        if unit == "booking":
            price = round(price / 10) * 10  # round bookings to tens of euros
        # archetype-matched real photo; cycles within the group
        group = IMAGES[TEMPLATE_IMAGE_GROUP[t_idx]]
        image = group[((i - 1) // len(TEMPLATES)) % len(group)]
        saunas.append(Experience(
            id=exp_id,
            title=title,
            provider=provider_pat.format(city=city),
            city=city,
            location=loc_pat.format(city=city),
            description=desc,
            imageUrl=image,
            priceAmount=price,
            priceUnit=unit,
            capacity=rng.randint(*cap_rng),
            durationHours=rng.randint(*hours_rng),
            # Growth simulation: the platform launches with 10 saunas;
            # POST /simulate-month onboards (publishes) 10 more at a time.
            status="published" if i <= 10 else "paused",
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
