from __future__ import annotations

import unittest
from datetime import date

from app.cards import card_view
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
        is_new=True,
        due_on=None,
        interval_days=0.0,
        ease=0.0,
    )
    data.update(kwargs)
    return CardCandidate(**data)


class CardViewTests(unittest.TestCase):
    def test_foreign_to_native_shows_transcription_on_front(self) -> None:
        view = card_view(card())
        self.assertEqual(view.prompt, "bag")
        self.assertEqual(view.hint, "существительное")
        self.assertEqual(view.ipa, "[bæg]")
        self.assertEqual(view.answer, "сумка")
        self.assertEqual(view.answer_hint, "")
        self.assertEqual(view.answer_ipa, "")

    def test_native_to_foreign_hides_transcription_on_front(self) -> None:
        view = card_view(card(direction="native_to_foreign", translations=("сумка", "пакет")))
        self.assertEqual(view.prompt, "сумка, пакет")
        self.assertEqual(view.hint, "существительное")
        self.assertEqual(view.ipa, "")
        self.assertEqual(view.answer, "bag")
        self.assertEqual(view.answer_hint, "")
        self.assertEqual(view.answer_ipa, "[bæg]")

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

    def test_fr_noun_fr_to_ru_shows_article_and_gender(self) -> None:
        view = card_view(
            card(
                language="fr",
                form="chat",
                transcription="ʃa",
                gender="m",
                translations=("кот",),
            )
        )
        self.assertEqual(view.prompt, "le chat")
        self.assertEqual(view.hint, "существительное · m")
        self.assertEqual(view.ipa, "[ʃa]")
        self.assertEqual(view.answer, "кот")

    def test_fr_noun_la_on_front(self) -> None:
        view = card_view(
            card(
                language="fr",
                form="maison",
                transcription=None,
                gender="f",
                translations=("дом",),
            )
        )
        self.assertEqual(view.prompt, "la maison")
        self.assertEqual(view.hint, "существительное · f")

    def test_fr_noun_plural_les(self) -> None:
        view = card_view(
            card(
                language="fr",
                form="parents",
                part_of_speech_code="pl n",
                transcription=None,
                gender="m",
                translations=("родители",),
            )
        )
        self.assertEqual(view.prompt, "les parents")
        self.assertEqual(view.hint, "существительное · m")

    def test_fr_noun_ru_to_fr_hides_article_on_front(self) -> None:
        view = card_view(
            card(
                language="fr",
                direction="native_to_foreign",
                form="maison",
                transcription="mɛzɔ̃",
                gender="f",
                translations=("дом",),
            )
        )
        self.assertEqual(view.prompt, "дом")
        self.assertEqual(view.hint, "существительное")
        self.assertEqual(view.ipa, "")
        self.assertNotIn("la", view.hint)
        self.assertNotIn("f", view.hint)
        self.assertEqual(view.answer, "la maison")
        self.assertEqual(view.answer_hint, "f")
        self.assertEqual(view.answer_ipa, "[mɛzɔ̃]")

    def test_fr_verb_no_article(self) -> None:
        view = card_view(
            card(
                language="fr",
                form="manger",
                part_of_speech="verb",
                part_of_speech_code="v",
                transcription=None,
                gender=None,
                translations=("есть",),
            )
        )
        self.assertEqual(view.prompt, "manger")

    def test_fr_noun_without_gender_no_article(self) -> None:
        view = card_view(
            card(
                language="fr",
                form="truc",
                transcription=None,
                gender=None,
                translations=("штука",),
            )
        )
        self.assertEqual(view.prompt, "truc")

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
