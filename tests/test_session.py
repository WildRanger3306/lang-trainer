from __future__ import annotations

import random
import unittest
from datetime import date, datetime, timedelta, timezone

from fsrs import State

from app.scheduler import (
    ASSESS_KNOW_INTERVAL,
    apply_assessment,
    apply_rating,
    convert_legacy_progress,
    new_per_day,
    preferred_direction,
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
        ease=0.0,
    )


class SchedulerTests(unittest.TestCase):
    def test_new_good_schedules_future_day(self) -> None:
        today = date(2026, 9, 11)
        now = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
        state = apply_rating(None, "good", today, now=now)
        self.assertGreaterEqual(state.due_on, today + timedelta(days=1))
        self.assertGreaterEqual(state.interval_days, 1.0)
        self.assertEqual(state.introduced_on, today)
        self.assertEqual(state.fsrs_state, int(State.Review))
        self.assertGreater(state.stability, 0)

    def test_new_again_due_tomorrow_and_low_stability(self) -> None:
        today = date(2026, 9, 11)
        now = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
        state = apply_rating(None, "again", today, now=now)
        self.assertEqual(state.due_on, today + timedelta(days=1))
        self.assertEqual(state.interval_days, 1.0)

    def test_good_grows_interval_over_reviews(self) -> None:
        today = date(2026, 9, 11)
        now = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
        first = apply_rating(None, "good", today, now=now)
        later = today + timedelta(days=int(first.interval_days))
        grown = apply_rating(
            first,
            "good",
            later,
            now=datetime.combine(later, datetime.min.time(), tzinfo=timezone.utc),
        )
        self.assertGreaterEqual(grown.stability, first.stability)
        self.assertGreaterEqual(grown.interval_days, 1.0)

    def test_legacy_conversion(self) -> None:
        state = convert_legacy_progress(
            due_on=date(2026, 9, 20),
            interval_days=8.0,
            ease=2.5,
            introduced_on=date(2026, 9, 1),
        )
        self.assertEqual(state.stability, 8.0)
        self.assertEqual(state.fsrs_state, int(State.Review))
        self.assertAlmostEqual(state.difficulty, 6.0)


class AssessmentSchedulerTests(unittest.TestCase):
    def test_know_interval_seven(self) -> None:
        today = date(2026, 9, 11)
        state = apply_assessment("know", today)
        self.assertEqual(state.interval_days, float(ASSESS_KNOW_INTERVAL))
        self.assertEqual(state.due_on, today + timedelta(days=ASSESS_KNOW_INTERVAL))
        self.assertEqual(state.stability, float(ASSESS_KNOW_INTERVAL))

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
        self.assertEqual(new_limit_for_day(0, 10), 10)
        self.assertEqual(new_limit_for_day(7, 10), 3)
        self.assertEqual(new_limit_for_day(10, 10), 0)
        self.assertEqual(new_limit_for_day(20, 20), 0)

    def test_assessment_batch(self) -> None:
        new = [candidate(i) for i in range(100)]
        picked = build_assessment_queue(new, batch=40, rng=random.Random(2))
        self.assertEqual(len(picked), 40)

    def test_preferred_direction_first(self) -> None:
        due = [
            candidate(1, "foreign_to_native", is_new=False),
            candidate(2, "native_to_foreign", is_new=False),
            candidate(3, "foreign_to_native", is_new=False),
        ]
        new = [
            candidate(10, "foreign_to_native"),
            candidate(11, "native_to_foreign"),
            candidate(12, "foreign_to_native"),
            candidate(13, "native_to_foreign"),
        ]
        picked = build_queue(
            due,
            new,
            new_limit=3,
            rng=random.Random(0),
            preferred="native_to_foreign",
        )
        due_part = picked[:3]
        new_part = picked[3:]
        self.assertEqual(due_part[0].direction, "native_to_foreign")
        self.assertTrue(all(c.direction == "native_to_foreign" for c in new_part[:2]))
        self.assertEqual(new_part[2].direction, "foreign_to_native")

    def test_language_caps(self) -> None:
        self.assertEqual(new_per_day("en"), 10)
        self.assertEqual(new_per_day("fr"), 20)
        self.assertEqual(preferred_direction("en"), "native_to_foreign")
        self.assertEqual(preferred_direction("fr"), "foreign_to_native")


class FilterTests(unittest.TestCase):
    def test_language_required(self) -> None:
        with self.assertRaises(ValueError):
            SessionFilter(language="de")


if __name__ == "__main__":
    unittest.main()
