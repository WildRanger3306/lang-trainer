from __future__ import annotations

import unittest
from datetime import date

from app.stats import (
    CorpusStats,
    LoadStats,
    PerformanceStats,
    advise_load,
    build_horizon,
    corpus_segments,
    days_to_finish,
    format_horizon,
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


class AdviseTests(unittest.TestCase):
    def test_raise_when_stable_and_due_small(self) -> None:
        advice = advise_load(
            corpus(), load(due_today=5, introduced_today=3), perf(), language="en"
        )
        self.assertEqual(advice.status, "raise")
        self.assertEqual(advice.suggested_new_per_day, 20)

    def test_lower_when_again_high(self) -> None:
        advice = advise_load(
            corpus(),
            load(due_today=10),
            perf(remember_rate_review_7=0.7, again_rate_7=0.3),
            language="en",
        )
        self.assertEqual(advice.status, "lower")
        self.assertEqual(advice.suggested_new_per_day, 10)

    def test_keep_when_little_data(self) -> None:
        advice = advise_load(corpus(), load(), perf(reviews_7=5), language="en")
        self.assertEqual(advice.status, "keep")

    def test_keep_at_en_max(self) -> None:
        advice = advise_load(
            corpus(),
            load(due_today=5, introduced_today=3, new_per_day=20),
            perf(),
            language="en",
        )
        self.assertEqual(advice.status, "keep")
        self.assertEqual(advice.suggested_new_per_day, 20)

    def test_fr_lower_clamped_to_min(self) -> None:
        advice = advise_load(
            corpus(),
            load(new_per_day=10),
            perf(remember_rate_review_7=0.7, again_rate_7=0.3),
            language="fr",
        )
        self.assertEqual(advice.status, "keep")
        self.assertEqual(advice.suggested_new_per_day, 10)


class HorizonTests(unittest.TestCase):
    def test_days_to_finish(self) -> None:
        self.assertEqual(days_to_finish(0, 15), 0)
        self.assertEqual(days_to_finish(15, 15), 1)
        self.assertEqual(days_to_finish(16, 15), 2)
        self.assertIsNone(days_to_finish(10, 0))

    def test_format_horizon(self) -> None:
        self.assertEqual(format_horizon(0), "готово")
        self.assertEqual(format_horizon(10), "≈ 10 дн")
        self.assertIn("нед", format_horizon(28))
        self.assertIn("мес", format_horizon(200))

    def test_build_horizon_at_limit(self) -> None:
        h = build_horizon(450, 15, introduced_last_7=70)
        self.assertEqual(h.days_at_limit, 30)
        self.assertEqual(h.pace_new_per_day_7, 10.0)
        self.assertEqual(h.days_at_pace, 45)
        self.assertIn("нед", h.label_at_limit)


class CorpusSegmentsTests(unittest.TestCase):
    def test_splits_intervals(self) -> None:
        seg = corpus_segments(
            corpus(total_cards=1000, new_cards=700, in_system=300, interval_ge_7=120, interval_ge_21=40)
        )
        self.assertEqual(seg.new, 700)
        self.assertEqual(seg.learning, 180)
        self.assertEqual(seg.young, 80)
        self.assertEqual(seg.mature, 40)
        self.assertEqual(seg.total, 1000)


if __name__ == "__main__":
    unittest.main()
