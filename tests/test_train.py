from __future__ import annotations

import os
import unittest

from fastapi.testclient import TestClient

from app.db import connect
from app.main import app
from app.scheduler import new_per_day


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
@unittest.skipUnless(
    os.environ.get("ALLOW_DB_TRUNCATE") == "1",
    "refuses to wipe live progress; set ALLOW_DB_TRUNCATE=1 only on disposable DB",
)
class TrainFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        with connect() as conn:
            conn.execute("TRUNCATE card_reviews RESTART IDENTITY")
            conn.execute("TRUNCATE card_progress")
            conn.execute("TRUNCATE user_language_filters")
            conn.execute("TRUNCATE load_advice_days")
            conn.execute("TRUNCATE user_load_limits")
            conn.execute("UPDATE users SET last_language = NULL")
            conn.commit()
            row = conn.execute(
                "SELECT id FROM users WHERE login = %s", ("serafima",)
            ).fetchone()
            if row is None:
                self.skipTest("user serafima missing")
        login = self.client.post(
            "/login",
            data={"login": "serafima", "password": "serafima123"},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303)

    def test_filter_page_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("английский", response.text)
        self.assertIn("Фильтры", response.text)
        self.assertIn("весь язык", response.text)
        self.assertNotIn('name="textbook"', response.text)
        self.assertIn("Повтор", response.text)
        self.assertIn("Серафима", response.text)
        self.assertIn("coach-text", response.text)
        self.assertIn("новых", response.text)

        fr = self.client.get("/?language=fr")
        self.assertEqual(fr.status_code, 200)
        self.assertIn("французский", fr.text)
        self.assertIn("Серафима", fr.text)
        self.assertIn("coach-text", fr.text)

    def test_filters_persist_per_user(self) -> None:
        page = self.client.get("/filters?language=en")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Starlight", page.text)
        self.assertIn('name="textbook"', page.text)

        save = self.client.post(
            "/filters",
            data={"language": "en", "textbook": "Starlight 6"},
            follow_redirects=False,
        )
        self.assertEqual(save.status_code, 303)
        self.assertIn("saved=1", save.headers["location"])

        home = self.client.get("/?language=en")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Starlight 6", home.text)

        start = self.client.post(
            "/start",
            data={"language": "en"},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 303)
        self.assertEqual(start.headers["location"], "/train")

        with connect() as conn:
            uid = conn.execute(
                "SELECT id FROM users WHERE login = %s", ("serafima",)
            ).fetchone()[0]
            row = conn.execute(
                """
                SELECT textbooks, topics
                FROM user_language_filters
                WHERE user_id = %s AND language = 'en'
                """,
                (uid,),
            ).fetchone()
        self.assertEqual(list(row[0]), ["Starlight 6"])
        self.assertEqual(list(row[1]), [])

    def test_unauthenticated_redirects(self) -> None:
        bare = TestClient(app)
        response = bare.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

    def test_grade_writes_progress(self) -> None:
        start = self.client.post(
            "/start",
            data={"language": "en"},
            follow_redirects=False,
        )
        self.assertEqual(start.status_code, 303)
        self.assertEqual(start.headers["location"], "/train")

        train = self.client.get("/train")
        self.assertEqual(train.status_code, 200)
        self.assertIn("1 /", train.text)

        with connect() as conn:
            before = conn.execute("SELECT count(*) FROM card_progress").fetchone()[0]

        grade = self.client.post(
            "/grade",
            data={"rating": "good"},
            follow_redirects=False,
        )
        self.assertEqual(grade.status_code, 303)
        self.assertEqual(grade.headers["location"], "/train")

        with connect() as conn:
            after = conn.execute("SELECT count(*) FROM card_progress").fetchone()[0]
            reviews = conn.execute("SELECT count(*) FROM card_reviews").fetchone()[0]
            row = conn.execute(
                """
                SELECT remembered, was_new, interval_before, interval_after, user_id, rating
                FROM card_reviews
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            prog = conn.execute(
                """
                SELECT interval_days, stability, difficulty, fsrs_state, user_id
                FROM card_progress
                ORDER BY introduced_on DESC, entry_id DESC
                LIMIT 1
                """
            ).fetchone()
            uid = conn.execute(
                "SELECT id FROM users WHERE login = %s", ("serafima",)
            ).fetchone()[0]
        self.assertGreaterEqual(after, before)
        self.assertGreaterEqual(after, 1)
        self.assertGreaterEqual(reviews, 1)
        self.assertTrue(row[0])
        self.assertTrue(row[1])
        self.assertEqual(float(row[2]), 0.0)
        self.assertGreaterEqual(float(row[3]), 1.0)
        self.assertEqual(int(row[4]), int(uid))
        self.assertEqual(int(row[5]), 3)
        self.assertGreaterEqual(float(prog[0]), 1.0)
        self.assertGreater(float(prog[1]), 0.0)
        self.assertGreaterEqual(float(prog[2]), 1.0)
        self.assertEqual(int(prog[3]), 2)
        self.assertEqual(int(prog[4]), int(uid))

    def test_stats_page_renders(self) -> None:
        response = self.client.get("/stats?language=en")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Сводка", response.text)
        self.assertIn("Корпус", response.text)
        self.assertIn("Нагрузка", response.text)
        self.assertIn("Горизонт", response.text)
        self.assertIn("Autoload", response.text)
        self.assertIn("Качество", response.text)
        self.assertIn("Сегодня", response.text)

    def test_session_respects_new_cap(self) -> None:
        response = self.client.get("/session?language=en&textbook=Starlight%206&seed=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["new_per_day"], new_per_day("en"))
        self.assertEqual(payload["preferred_direction"], "native_to_foreign")
        self.assertLessEqual(payload["new_in_session"], new_per_day("en"))
        self.assertEqual(
            payload["due_count"] + payload["new_in_session"], len(payload["cards"])
        )

    def test_fr_session_uses_higher_cap(self) -> None:
        response = self.client.get("/session?language=fr&seed=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["new_per_day"], 20)
        self.assertEqual(payload["preferred_direction"], "foreign_to_native")
        self.assertLessEqual(payload["new_in_session"], 20)

    def test_assessment_know_skips_new_quota(self) -> None:
        start = self.client.post(
            "/assess/start",
            data={"language": "en"},
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
                SELECT interval_days, introduced_via, user_id
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
