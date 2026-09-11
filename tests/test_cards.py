from __future__ import annotations

import unittest

from app.cards import card_view, next_streak
from app.session import CardCandidate


def card(**kwargs) -> CardCandidate:
    data = dict(
        entry_id=1,
        direction="foreign_to_native",
        language="en",
        form="bag",
        part_of_speech="noun",
        part_of_speech_code="n",
        transcription="bæg",
        gender=None,
        translations=("сумка",),
        streak=0,
    )
    data.update(kwargs)
    return CardCandidate(**data)


class StreakTests(unittest.TestCase):
    def test_remember_increments(self) -> None:
        self.assertEqual(next_streak(0, True), 1)
        self.assertEqual(next_streak(2, True), 3)

    def test_forget_resets(self) -> None:
        self.assertEqual(next_streak(4, False), 0)


class CardViewTests(unittest.TestCase):
    def test_foreign_to_native_shows_transcription_on_front(self) -> None:
        view = card_view(card())
        self.assertEqual(view.prompt, "bag")
        self.assertIn("существительное", view.hint)
        self.assertIn("bæg", view.hint)
        self.assertEqual(view.answer, "сумка")
        self.assertEqual(view.answer_hint, "")

    def test_native_to_foreign_hides_transcription_on_front(self) -> None:
        view = card_view(card(direction="native_to_foreign", translations=("сумка", "пакет")))
        self.assertEqual(view.prompt, "сумка, пакет")
        self.assertEqual(view.hint, "существительное")
        self.assertNotIn("bæg", view.hint)
        self.assertEqual(view.answer, "bag")
        self.assertEqual(view.answer_hint, "bæg")

    def test_foreign_to_native_shows_gender_on_front(self) -> None:
        view = card_view(card(form="chat", transcription=None, gender="m", translations=("кот",)))
        self.assertEqual(view.prompt, "chat")
        self.assertEqual(view.hint, "существительное · m")
        self.assertEqual(view.answer, "кот")

    def test_native_to_foreign_hides_gender_on_front(self) -> None:
        view = card_view(
            card(
                direction="native_to_foreign",
                form="maison",
                transcription=None,
                gender="f",
                translations=("дом",),
            )
        )
        self.assertEqual(view.prompt, "дом")
        self.assertEqual(view.hint, "существительное")
        self.assertNotIn("f", view.hint)
        self.assertEqual(view.answer, "maison")
        self.assertEqual(view.answer_hint, "f")

    def test_direction_flags_ru_to_fr(self) -> None:
        view = card_view(
            card(language="fr", direction="native_to_foreign", form="chat", transcription=None)
        )
        self.assertEqual(view.direction_flags, "🇷🇺 → 🇫🇷")

    def test_direction_flags_fr_to_ru(self) -> None:
        view = card_view(card(language="fr", form="chat", transcription=None))
        self.assertEqual(view.direction_flags, "🇫🇷 → 🇷🇺")

    def test_direction_flags_en_to_ru(self) -> None:
        view = card_view(card())
        self.assertEqual(view.direction_flags, "🇬🇧 → 🇷🇺")
