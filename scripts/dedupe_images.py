"""One-off cleanup: remove saunas that share an imageUrl with another sauna,
keeping exactly one per distinct image (preferring a published one), and
tombstone the removed saunas' sessions.

For data seeded before the seed gave every sauna a unique image. A fresh
`make seed` no longer produces duplicates, so new deployments don't need this.

Uses the app's ReplacingMergeTree tombstone pattern (store.delete_*), so the
removals are invisible to every FINAL + _deleted = 0 read.

    make install
    .venv/bin/python -m scripts.dedupe_images            # dry run (prints plan)
    .venv/bin/python -m scripts.dedupe_images --apply     # execute
"""
import sys
from collections import defaultdict

from app import store
from app.db import get_client


def plan(client):
    rows = client.query(
        "SELECT id, status, imageUrl FROM experiences FINAL WHERE _deleted = 0"
    ).result_rows

    groups = defaultdict(list)
    for exp_id, status, url in rows:
        groups[url].append((exp_id, status))

    remove = []
    for members in groups.values():
        # keeper: published first, then lowest id — deterministic
        keeper, *rest = sorted(members, key=lambda m: (m[1] != "published", m[0]))
        remove.extend(exp_id for exp_id, _ in rest)
    return rows, remove


def main():
    apply = "--apply" in sys.argv
    client = get_client()
    rows, remove = plan(client)

    sess = client.query(
        "SELECT id FROM sessions FINAL WHERE _deleted = 0 AND experienceId IN %(ids)s",
        parameters={"ids": remove or [""]},
    ).result_rows
    sess_ids = [r[0] for r in sess]

    print(f"experiences: {len(rows)} -> remove {len(remove)}, keep {len(rows) - len(remove)}")
    print(f"sessions to tombstone (orphaned by removal): {len(sess_ids)}")

    if not apply:
        print("\nDRY RUN — re-run with --apply to execute.")
        return

    store.ensure_tables(client)
    for exp_id in remove:
        store.delete_experience(client, exp_id)
    for sid in sess_ids:
        store.delete_session(client, sid)

    left = client.query(
        "SELECT count() FROM experiences FINAL WHERE _deleted = 0"
    ).result_rows[0][0]
    dups = client.query(
        "SELECT count() FROM (SELECT imageUrl, count() AS n FROM experiences FINAL "
        "WHERE _deleted = 0 GROUP BY imageUrl HAVING n > 1)"
    ).result_rows[0][0]
    print(f"\nAPPLIED. experiences left: {left} | imageUrls still duplicated: {dups}")


if __name__ == "__main__":
    main()
