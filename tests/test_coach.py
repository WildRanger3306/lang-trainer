from __future__ import annotations

import unittest

from app.coach import ABSENCE_DAYS, coach_message
from app.stats import LoadAdvice, LoadStats, PerformanceStats
from app.users import User


def load(**kwargs) -> LoadStats:
    data = dict(
        due_today=10,
        due_tomorrow=12,
        due_in_3_days=20,
        introduced_today=2,
        new_per_day=10,
        answers_last_7=80,
        answers_last_30=200,
        median_answers_per_day_7=15.0,
        median_answers_per_day_30=12.0,
        active_days_7=5,
        active_days_30=18,
    )
    data.update(kwargs)
    return LoadStats(**data)


def perf(**kwargs) -> PerformanceStats:
    data = dict(
        reviews_7=40,
        remember_rate_all_7=0.9,
        remember_rate_new_7=0.75,
        remember_rate_review_7=0.92,
        again_rate_7=0.08,
        mature_reviews_7=5,
        mature_again_rate_7=0.0,
        rating_again=3,
        rating_hard=4,
        rating_good=25,
        rating_easy=8,
        rating_unrated=0,
    )
    data.update(kwargs)
    return PerformanceStats(**data)


def advice(status: str = "keep", suggested: int = 10) -> LoadAdvice:
    return LoadAdvice(
        status=status,
        label=status,
        detail="",
        suggested_new_per_day=suggested,
    )


USER = User(id=1, login="serafima", display_name="Серафима")


class CoachTests(unittest.TestCase):
    def test_calm_keep_small_due(self) -> None:
        msg = coach_message(
            USER,
            language="en",
            load=load(due_today=8, introduced_today=2, new_per_day=10),
            advice=advice("keep"),
            performance=perf(),
            days_since_active=0,
        )
        self.assertEqual(msg.tone, "calm")
        self.assertIn("Серафима", msg.text)
        self.assertIn("8 новых", msg.text)

    def test_soft_on_lower(self) -> None:
        msg = coach_message(
            USER,
            language="fr",
            load=load(due_today=40),
            advice=advice("lower", 15),
            performance=perf(),
            days_since_active=1,
        )
        self.assertEqual(msg.tone, "soft")
        self.assertIn("молодец", msg.text)

    def test_boost_on_raise(self) -> None:
        msg = coach_message(
            USER,
            language="en",
            load=load(due_today=5, introduced_today=3),
            advice=advice("raise", 15),
            performance=perf(),
            days_since_active=0,
        )
        self.assertEqual(msg.tone, "boost")
        self.assertIn("прибавить", msg.text)

    def test_welcome_only_after_real_pause(self) -> None:
        msg = coach_message(
            USER,
            language="fr",
            load=load(due_today=12, active_days_7=0, answers_last_7=0),
            advice=advice("keep"),
            performance=perf(reviews_7=0),
            days_since_active=ABSENCE_DAYS,
        )
        self.assertEqual(msg.tone, "welcome")
        self.assertIn("давно не виделись", msg.text)

    def test_yesterday_is_not_welcome(self) -> None:
        msg = coach_message(
            USER,
            language="en",
            load=load(active_days_7=0, answers_last_7=0),
            advice=advice("keep"),
            performance=perf(reviews_7=0),
            days_since_active=1,
        )
        self.assertNotEqual(msg.tone, "welcome")
        self.assertNotIn("давно не виделись", msg.text)

    def test_never_started_is_start_not_welcome(self) -> None:
        msg = coach_message(
            USER,
            language="fr",
            load=load(due_today=0, new_per_day=20, introduced_today=0),
            advice=advice("keep"),
            performance=perf(reviews_7=0),
            days_since_active=None,
        )
        self.assertEqual(msg.tone, "start")
        self.assertNotIn("давно не виделись", msg.text)
        self.assertIn("ещё не начинали", msg.text)

    def test_adapt_note_wins(self) -> None:
        msg = coach_message(
            USER,
            language="en",
            load=load(),
            advice=advice("keep"),
            performance=perf(),
            days_since_active=0,
            adapt_note="авто: EN 10→5",
        )
        self.assertEqual(msg.tone, "soft")
        self.assertIn("подстроился", msg.text)


if __name__ == "__main__":
    unittest.main()
