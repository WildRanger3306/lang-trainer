from __future__ import annotations

import random
import unittest

from app.session import CardCandidate, SessionFilter, card_weight, pick_cards


def candidate(entry_id: int, direction: str = "foreign_to_native", streak: int = 0) -> CardCandidate:
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
        streak=streak,
    )


class WeightTests(unittest.TestCase):
    def test_new_and_forgotten_have_max_weight(self) -> None:
        self.assertEqual(card_weight(0), 1.0)

    def test_streak_lowers_weight(self) -> None:
        self.assertEqual(card_weight(1), 0.5)
        self.assertEqual(card_weight(3), 0.25)


class PickTests(unittest.TestCase):
    def test_takes_all_when_pool_smaller_than_n(self) -> None:
        pool = [candidate(1), candidate(1, "native_to_foreign")]
        picked = pick_cards(pool, 20, random.Random(0))
        self.assertEqual(len(picked), 2)
        self.assertEqual({c.key for c in picked}, {(1, "foreign_to_native"), (1, "native_to_foreign")})

    def test_no_duplicate_cards(self) -> None:
        pool = [candidate(i, d) for i in range(30) for d in ("foreign_to_native", "native_to_foreign")]
        picked = pick_cards(pool, 20, random.Random(1))
        self.assertEqual(len(picked), 20)
        self.assertEqual(len({c.key for c in picked}), 20)

    def test_same_seed_same_order(self) -> None:
        pool = [candidate(i) for i in range(40)]
        a = pick_cards(pool, 20, random.Random(42))
        b = pick_cards(pool, 20, random.Random(42))
        self.assertEqual([c.key for c in a], [c.key for c in b])

    def test_low_streak_picked_more_often(self) -> None:
        pool = [candidate(1, streak=0), candidate(2, streak=8)]
        counts = {1: 0, 2: 0}
        trials = 400
        for seed in range(trials):
            picked = pick_cards(pool, 1, random.Random(seed))
            counts[picked[0].entry_id] += 1
        self.assertGreater(counts[1], counts[2])
        self.assertGreater(counts[1], trials * 0.7)


class FilterTests(unittest.TestCase):
    def test_language_required(self) -> None:
        with self.assertRaises(ValueError):
            SessionFilter(language="de")


if __name__ == "__main__":
    unittest.main()
