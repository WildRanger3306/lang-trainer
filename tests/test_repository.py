from __future__ import annotations

import os
import random
import unittest

from app.db import connect
from app.repository import fetch_candidates
from app.session import SessionFilter, pick_cards


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class RepositoryTests(unittest.TestCase):
    def test_starlight_pool_is_two_directions_per_entry(self) -> None:
        flt = SessionFilter(language="en", textbooks=("Starlight 6",))
        with connect() as conn:
            pool = fetch_candidates(conn, flt)
        self.assertEqual(len(pool), 184)
        self.assertEqual(len({c.key for c in pool}), 184)
        picked = pick_cards(pool, 20, random.Random(0))
        self.assertEqual(len(picked), 20)
        self.assertTrue(all(c.form for c in picked))

    def test_unknown_textbook_is_empty(self) -> None:
        flt = SessionFilter(language="en", textbooks=("Starlight 7",))
        with connect() as conn:
            pool = fetch_candidates(conn, flt)
        self.assertEqual(pool, [])
