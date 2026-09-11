from __future__ import annotations

import random
import unittest
from datetime import date, timedelta

from app.scheduler import (
    ASSESS_KNOW_INTERVAL,
    DEFAULT_EASE,
    MIN_EASE,
    apply_assessment,
    apply_grade,
    next_interval,
)
from app.session import (
    CardCandidate,
    SessionFilter,
    build_assessment_queue,
    build_queue,
    new_limit_for_day,
)


def candidate(
    entry_id: int,
    direction: str = "foreign_to_native",
    *,
    is_new: bool = True,
) -> CardCandidate:
    return CardCandidate(
        entry_id=entry_id,
        direction=direction,
        language="en",
        form=f"w{entry_id}",
        part_of_speech="noun",
        part_of_speech_code="n",
        transcription=None,
        gender=None,
        translations=("т",),
        is_new=is_new,
        due_on=None if is_new else date(2026, 9, 11),
        interval_days=0.0 if is_new else 1.0,
        ease=DEFAULT_EASE,
    )


class SchedulerTests(unittest.TestCase):
    def test_new_good_due_tomorrow(self) -> None:
        today = date(2026, 9, 11)
        state = apply_grade(None, True, today)
        self.assertEqual(state.due_on, today + timedelta(days=1))
        self.assertEqual(state.interval_days, 1.0)
        self.assertEqual(state.ease, DEFAULT_EASE)
        self.assertEqual(state.introduced_on, today)

    def test_new_again_due_tomorrow(self) -> None:
        today = date(2026, 9, 11)
        state = apply_grade(None, False, today)
        self.assertEqual(state.due_on, today + timedelta(days=1))
        self.assertEqual(state.interval_days, 1.0)

    def test_intervals_grow(self) -> None:
        self.assertEqual(next_interval(1, 2.5), 3.0)
        self.assertEqual(next_interval(3, 2.5), 8.0)

    def test_again_resets_interval_and_lowers_ease(self) -> None:
        today = date(2026, 9, 11)
        first = apply_grade(None, True, today)
        grown = apply_grade(first, True, today + timedelta(days=1))
        self.assertEqual(grown.interval_days, 3.0)
        failed = apply_grade(grown, False, today + timedelta(days=4))
        self.assertEqual(failed.interval_days, 1.0)
        self.assertEqual(failed.due_on, today + timedelta(days=5))
        self.assertAlmostEqual(failed.ease, DEFAULT_EASE - 0.2)
        self.assertGreaterEqual(failed.ease, MIN_EASE)


class AssessmentSchedulerTests(unittest.TestCase):
    def test_know_interval_seven(self) -> None:
        today = date(2026, 9, 11)
        state = apply_assessment("know", today)
        self.assertEqual(state.interval_days, float(ASSESS_KNOW_INTERVAL))
        self.assertEqual(state.due_on, today + timedelta(days=ASSESS_KNOW_INTERVAL))
        self.assertEqual(state.ease, DEFAULT_EASE)

    def test_doubt_and_unknown_due_tomorrow(self) -> None:
        today = date(2026, 9, 11)
        for verdict in ("doubt", "unknown"):
            state = apply_assessment(verdict, today)
            self.assertEqual(state.interval_days, 1.0)
            self.assertEqual(state.due_on, today + timedelta(days=1))


class QueueTests(unittest.TestCase):
    def test_due_before_new(self) -> None:
        due = [candidate(1, is_new=False), candidate(2, is_new=False)]
        new = [candidate(10), candidate(11), candidate(12)]
        picked = build_queue(due, new, new_limit=2, rng=random.Random(0))
        self.assertEqual(len(picked), 4)
        self.assertTrue(all(not c.is_new for c in picked[:2]))
        self.assertTrue(all(c.is_new for c in picked[2:]))

    def test_new_limit(self) -> None:
        new = [candidate(i) for i in range(20)]
        picked = build_queue([], new, new_limit=15, rng=random.Random(1))
        self.assertEqual(len(picked), 15)

    def test_new_limit_for_day(self) -> None:
        self.assertEqual(new_limit_for_day(0), 15)
        self.assertEqual(new_limit_for_day(10), 5)
        self.assertEqual(new_limit_for_day(15), 0)
        self.assertEqual(new_limit_for_day(20), 0)

    def test_assessment_batch(self) -> None:
        new = [candidate(i) for i in range(100)]
        picked = build_assessment_queue(new, batch=40, rng=random.Random(2))
        self.assertEqual(len(picked), 40)


class FilterTests(unittest.TestCase):
    def test_language_required(self) -> None:
        with self.assertRaises(ValueError):
            SessionFilter(language="de")


if __name__ == "__main__":
    unittest.main()
