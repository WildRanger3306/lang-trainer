from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from app.db import connect
from app.main import app
from app.scheduler import NEW_PER_DAY


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class TrainFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        with connect() as conn:
            conn.execute("TRUNCATE card_reviews RESTART IDENTITY")
            conn.execute("TRUNCATE card_progress")
            conn.commit()

    def test_filter_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("английский", response.text)
        self.assertIn("Starlight 6", response.text)
        self.assertIn("due", response.text)

    def test_grade_writes_progress(self) -> None:
        start = self.client.post(
            "/start",
            data={"language": "en", "textbook": "Starlight 6"},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 303)
        self.assertEqual(start.headers["location"], "/train")

        train = self.client.get("/train")
        self.assertEqual(train.status_code, 200)
        self.assertIn(f"1 /", train.text)

        with connect() as conn:
            before = conn.execute("SELECT count(*) FROM card_progress").fetchone()[0]

        grade = self.client.post(
            "/grade",
            data={"remembered": "1"},
            follow_redirects=False,
        )
        self.assertEqual(grade.status_code, 303)
        self.assertEqual(grade.headers["location"], "/train")

        with connect() as conn:
            after = conn.execute("SELECT count(*) FROM card_progress").fetchone()[0]
            reviews = conn.execute("SELECT count(*) FROM card_reviews").fetchone()[0]
            row = conn.execute(
                """
                SELECT remembered, was_new, interval_before, interval_after
                FROM card_reviews
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            # join progress
            prog = conn.execute(
                """
                SELECT interval_days, ease
                FROM card_progress
                ORDER BY introduced_on DESC, entry_id DESC
                LIMIT 1
                """
            ).fetchone()
        self.assertGreaterEqual(after, before)
        self.assertGreaterEqual(after, 1)
        self.assertGreaterEqual(reviews, 1)
        self.assertTrue(row[0])  # remembered
        self.assertTrue(row[1])  # was_new
        self.assertEqual(float(row[2]), 0.0)
        self.assertEqual(float(row[3]), 1.0)
        self.assertEqual(float(prog[0]), 1.0)
        self.assertEqual(float(prog[1]), 2.5)

    def test_stats_page_renders(self) -> None:
        response = self.client.get("/stats?language=en")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Сводка", response.text)
        self.assertIn("Корпус", response.text)
        self.assertIn("Нагрузка", response.text)
        self.assertIn("Горизонт", response.text)

    def test_session_respects_new_cap(self) -> None:
        response = self.client.get("/session?language=en&textbook=Starlight%206&seed=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertLessEqual(payload["new_in_session"], NEW_PER_DAY)
        self.assertEqual(payload["due_count"] + payload["new_in_session"], len(payload["cards"]))

    def test_assessment_know_skips_new_quota(self) -> None:
        start = self.client.post(
            "/assess/start",
            data={"language": "en", "textbook": "Starlight 6"},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 303)
        self.assertEqual(start.headers["location"], "/assess")

        page = self.client.get("/assess")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Знаю", page.text)

        grade = self.client.post(
            "/assess/grade",
            data={"verdict": "know"},
            follow_redirects=False,
        )
        self.assertEqual(grade.status_code, 303)

        with connect() as conn:
            prog = conn.execute(
                """
                SELECT interval_days, introduced_via
                FROM card_progress
                ORDER BY introduced_on DESC, entry_id DESC
                LIMIT 1
                """
            ).fetchone()
            review = conn.execute(
                """
                SELECT source, remembered, interval_after
                FROM card_reviews
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            introduced = conn.execute(
                """
                SELECT count(*)
                FROM card_progress
                WHERE introduced_on = CURRENT_DATE AND introduced_via = 'train'
                """
            ).fetchone()[0]
        self.assertEqual(float(prog[0]), 7.0)
        self.assertEqual(prog[1], "assess")
        self.assertEqual(review[0], "assess")
        self.assertTrue(review[1])
        self.assertEqual(float(review[2]), 7.0)
        self.assertEqual(introduced, 0)
