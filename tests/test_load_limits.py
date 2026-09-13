from __future__ import annotations

import os
import unittest
from datetime import date, timedelta

from app.db import connect
from app.load_limits import (
    clamp_new_per_day,
    ensure_load_limit,
    get_new_per_day,
    record_advice_day,
    try_apply_hysteresis,
)


class ClampTests(unittest.TestCase):
    def test_en_bounds(self) -> None:
        self.assertEqual(clamp_new_per_day("en", 0), 5)
        self.assertEqual(clamp_new_per_day("en", 25), 20)
        self.assertEqual(clamp_new_per_day("en", 10), 10)

    def test_fr_bounds(self) -> None:
        self.assertEqual(clamp_new_per_day("fr", 5), 10)
        self.assertEqual(clamp_new_per_day("fr", 40), 30)


@unittest.skipUnless(os.environ.get("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class HysteresisDbTests(unittest.TestCase):
    def setUp(self) -> None:
        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE login = %s", ("serafima",)
            ).fetchone()
            if row is None:
                self.skipTest("user serafima missing")
            self.user_id = int(row[0])
            conn.execute(
                "DELETE FROM load_advice_days WHERE user_id = %s", (self.user_id,)
            )
            conn.execute(
                "DELETE FROM user_load_limits WHERE user_id = %s", (self.user_id,)
            )
            conn.commit()

    def test_default_limit_and_hysteresis_lower(self) -> None:
        today = date(2026, 9, 12)
        with connect() as conn:
            self.assertEqual(get_new_per_day(conn, self.user_id, "en"), 10)
            conn.commit()

            for i in range(3):
                day = today - timedelta(days=i)
                record_advice_day(conn, self.user_id, "en", day, "lower", 5)
            conn.commit()

            result = try_apply_hysteresis(
                conn,
                self.user_id,
                "en",
                today,
                current=10,
                today_suggested=5,
            )
            conn.commit()
            self.assertTrue(result.changed)
            self.assertEqual(result.new_per_day, 5)
            self.assertIn("10→5", result.note or "")

            again = try_apply_hysteresis(
                conn,
                self.user_id,
                "en",
                today,
                current=5,
                today_suggested=5,
            )
            self.assertFalse(again.changed)
            self.assertEqual(ensure_load_limit(conn, self.user_id, "en").new_per_day, 5)

    def test_no_change_without_streak(self) -> None:
        today = date(2026, 9, 12)
        with connect() as conn:
            get_new_per_day(conn, self.user_id, "fr")
            record_advice_day(conn, self.user_id, "fr", today, "raise", 25)
            record_advice_day(
                conn, self.user_id, "fr", today - timedelta(days=1), "keep", 20
            )
            record_advice_day(
                conn, self.user_id, "fr", today - timedelta(days=2), "raise", 25
            )
            result = try_apply_hysteresis(
                conn,
                self.user_id,
                "fr",
                today,
                current=20,
                today_suggested=25,
            )
            conn.commit()
            self.assertFalse(result.changed)
            self.assertEqual(get_new_per_day(conn, self.user_id, "fr"), 20)


if __name__ == "__main__":
    unittest.main()
