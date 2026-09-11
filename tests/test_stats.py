from __future__ import annotations

import unittest
from datetime import date

from app.stats import (
    CorpusStats,
    LoadStats,
    PerformanceStats,
    advise_load,
)


def corpus(**kwargs) -> CorpusStats:
    data = dict(
        total_cards=1000,
        new_cards=800,
        in_system=200,
        interval_ge_7=50,
        interval_ge_21=10,
    )
    data.update(kwargs)
    return CorpusStats(**data)


def load(**kwargs) -> LoadStats:
    data = dict(
        due_today=10,
        due_tomorrow=12,
        due_in_3_days=20,
        introduced_today=5,
        new_per_day=15,
        answers_last_7=100,
        answers_last_30=300,
        median_answers_per_day_7=20.0,
        median_answers_per_day_30=18.0,
        active_days_7=5,
        active_days_30=20,
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
        reset_to_one_7=3,
        mature_reviews_7=5,
        mature_again_rate_7=0.0,
    )
    data.update(kwargs)
    return PerformanceStats(**data)


class AdviseTests(unittest.TestCase):
    def test_raise_when_stable_and_due_small(self) -> None:
        advice = advise_load(corpus(), load(due_today=5, introduced_today=3), perf())
        self.assertEqual(advice.status, "raise")
        self.assertEqual(advice.suggested_new_per_day, 20)

    def test_lower_when_again_high(self) -> None:
        advice = advise_load(
            corpus(),
            load(due_today=10),
            perf(remember_rate_review_7=0.7, again_rate_7=0.3),
        )
        self.assertEqual(advice.status, "lower")
        self.assertEqual(advice.suggested_new_per_day, 10)

    def test_keep_when_little_data(self) -> None:
        advice = advise_load(corpus(), load(), perf(reviews_7=5))
        self.assertEqual(advice.status, "keep")


if __name__ == "__main__":
    unittest.main()
