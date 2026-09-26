from __future__ import annotations

import os
import random
import unittest

from app.db import connect
from app.repository import (
    fetch_due_candidates,
    count_filter_words,
    fetch_filter_banks,
    fetch_new_candidates,
)
from app.scheduler import new_per_day
from app.session import NO_TOPIC, SessionFilter, build_queue, make_pick, new_limit_for_day


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE login = %s", ("serafima",)
            ).fetchone()
            if row is None:
                self.skipTest("user serafima missing")
            self.user_id = int(row[0])

    def test_starlight_pool_covers_all_directions(self) -> None:
        flt = SessionFilter(language="en", textbooks=("Starlight 6",))
        with connect() as conn:
            due = fetch_due_candidates(conn, flt, self.user_id)
            new = fetch_new_candidates(conn, flt, self.user_id)
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
                  AND p.user_id = %s
                  AND p.due_on > CURRENT_DATE
                """,
                (self.user_id,),
            ).fetchone()[0]
        self.assertEqual(len(due) + len(new) + scheduled_future, total * 2)
        cap = new_per_day("en")
        picked = build_queue(due, new, cap, random.Random(0))
        self.assertLessEqual(len(picked), cap + len(due))
        self.assertTrue(all(c.form for c in picked))

    def test_unknown_textbook_is_empty(self) -> None:
        flt = SessionFilter(language="en", textbooks=("No Such Book",))
        with connect() as conn:
            due = fetch_due_candidates(conn, flt, self.user_id)
            new = fetch_new_candidates(conn, flt, self.user_id)
        self.assertEqual(due, [])
        self.assertEqual(new, [])

    def test_new_limit_helper(self) -> None:
        self.assertEqual(new_limit_for_day(0, 10), 10)

    def test_filter_banks_scoped_by_language(self) -> None:
        with connect() as conn:
            en = [b.name for b in fetch_filter_banks(conn, "en", self.user_id)]
            fr = [b.name for b in fetch_filter_banks(conn, "fr", self.user_id)]
        self.assertTrue(any(name.startswith("Starlight") for name in en))
        self.assertFalse(any("Loiseau" in name for name in en))
        self.assertTrue(any(name.startswith("Loiseau Blue") for name in fr))
        self.assertFalse(any("Starlight" in name for name in fr))

    def test_topics_and_untopiced_slice_their_textbook(self) -> None:
        book = "Starlight 7"
        with connect() as conn:
            banks = {b.name: b for b in fetch_filter_banks(conn, "en", self.user_id)}
            bank = banks[book]

            def words(*picks: str, books: tuple[str, ...] = (book,)) -> int:
                flt = SessionFilter(
                    language="en", textbooks=books, topics=tuple(picks)
                )
                return count_filter_words(conn, flt, self.user_id)[0]

            whole = words()
            self.assertEqual(whole, bank.words)
            self.assertTrue(bank.no_topic is not None and bank.chips)
            first = bank.chips[0]
            self.assertEqual(words(make_pick(book, first.name)), first.words)
            self.assertEqual(
                words(make_pick(book, NO_TOPIC)), bank.no_topic.words
            )
            both = words(make_pick(book, first.name), make_pick(book, NO_TOPIC))
            self.assertEqual(both, first.words + bank.no_topic.words)
            # A pick of a textbook that is not selected does nothing.
            other = next(name for name in banks if name != book)
            self.assertEqual(
                words(make_pick(book, first.name), books=(other,)), banks[other].words
            )

    def test_no_textbook_selected_means_no_words(self) -> None:
        with connect() as conn:
            flt = SessionFilter(language="en")
            self.assertEqual(count_filter_words(conn, flt, self.user_id), (0, 0))
            self.assertEqual(fetch_due_candidates(conn, flt, self.user_id), [])
            self.assertEqual(fetch_new_candidates(conn, flt, self.user_id), [])

    def test_progress_buckets_add_up(self) -> None:
        with connect() as conn:
            banks = fetch_filter_banks(conn, "en", self.user_id)
            for bank in banks:
                progress = bank.progress
                self.assertLessEqual(progress.started, progress.words)
                for chip in bank.chips:
                    self.assertLessEqual(chip.progress.started, chip.words)
            book = next(b for b in banks if b.name.startswith("Starlight"))
            direct = conn.execute(
                """
                SELECT count(DISTINCT e.id)
                FROM entries e
                JOIN entry_textbooks et ON et.entry_id = e.id
                JOIN textbooks tb ON tb.id = et.textbook_id
                JOIN card_progress p ON p.entry_id = e.id AND p.user_id = %s
                WHERE tb.name = %s
                """,
                (self.user_id, book.name),
            ).fetchone()[0]
        self.assertEqual(book.progress.started, direct)
