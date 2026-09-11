from __future__ import annotations

import os
import random
import unittest

from app.db import connect
from app.repository import fetch_due_candidates, fetch_new_candidates
from app.scheduler import NEW_PER_DAY
from app.session import SessionFilter, build_queue, new_limit_for_day


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class RepositoryTests(unittest.TestCase):
    def test_starlight_pool_covers_all_directions(self) -> None:
        flt = SessionFilter(language="en", textbooks=("Starlight 6",))
        with connect() as conn:
            due = fetch_due_candidates(conn, flt)
            new = fetch_new_candidates(conn, flt)
            total = conn.execute(
                """
                SELECT count(*) FROM entries e
                JOIN entry_textbooks et ON et.entry_id = e.id
                JOIN textbooks t ON t.id = et.textbook_id
                WHERE t.name = 'Starlight 6'
                """
            ).fetchone()[0]
            scheduled_future = conn.execute(
                """
                SELECT count(*)
                FROM card_progress p
                JOIN entries e ON e.id = p.entry_id
                JOIN entry_textbooks et ON et.entry_id = e.id
                JOIN textbooks t ON t.id = et.textbook_id
                WHERE t.name = 'Starlight 6'
                  AND e.language = 'en'
                  AND p.due_on > CURRENT_DATE
                """
            ).fetchone()[0]
        self.assertEqual(len(due) + len(new) + scheduled_future, total * 2)
        picked = build_queue(due, new, NEW_PER_DAY, random.Random(0))
        self.assertLessEqual(len(picked), NEW_PER_DAY + len(due))
        self.assertTrue(all(c.form for c in picked))

    def test_unknown_textbook_is_empty(self) -> None:
        flt = SessionFilter(language="en", textbooks=("No Such Book",))
        with connect() as conn:
            due = fetch_due_candidates(conn, flt)
            new = fetch_new_candidates(conn, flt)
        self.assertEqual(due, [])
        self.assertEqual(new, [])

    def test_new_limit_helper(self) -> None:
        self.assertEqual(new_limit_for_day(0), 15)
