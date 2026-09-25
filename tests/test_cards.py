from __future__ import annotations

import unittest
from datetime import date

from app.cards import card_view
from app.session import CardCandidate, VerbForms


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

    def test_phrasal_verb_hint(self) -> None:
        view = card_view(
            card(
                language="en",
                form="bring up",
                part_of_speech="phrasal_verb",
                part_of_speech_code="phr v",
                transcription=None,
                gender=None,
                translations=("воспитывать (детей)",),
            )
        )
        self.assertEqual(view.hint, "фразовый глагол")
        self.assertEqual(view.prompt, "bring up")

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


def read_forms(**kwargs) -> VerbForms:
    data = dict(
        past=("read",),
        past_ipa=("rˈɛd",),
        past_participle=("read",),
        past_participle_ipa=("rˈɛd",),
        cue=None,
    )
    data.update(kwargs)
    return VerbForms(**data)


def verb(**kwargs) -> CardCandidate:
    data = dict(
        direction="forms",
        form="read",
        part_of_speech="verb",
        part_of_speech_code="v",
        transcription="rˈiːd",
        translations=("читать",),
        forms=read_forms(),
    )
    data.update(kwargs)
    return card(**data)


class FormsCardViewTests(unittest.TestCase):
    def test_front_is_translation_only(self) -> None:
        view = card_view(verb())
        self.assertEqual(view.prompt, "читать")
        self.assertEqual(view.hint, "неправильный глагол · 3 формы")
        self.assertEqual(view.ipa, "")

    def test_cue_replaces_translations_on_front(self) -> None:
        view = card_view(
            verb(
                form="make",
                translations=("делать", "изготавливать"),
                forms=read_forms(cue="делать, изготавливать (торт, чай)"),
            )
        )
        self.assertEqual(view.prompt, "делать, изготавливать (торт, чай)")

    def test_back_has_three_labelled_columns(self) -> None:
        view = card_view(verb())
        self.assertEqual(
            [c.label for c in view.form_columns], ["Inf.", "Past Simple", "Past Part."]
        )
        self.assertEqual([c.form for c in view.form_columns], ["read", "read", "read"])
        self.assertEqual(view.form_columns[0].ipa, "[rˈiːd]")
        self.assertEqual(view.form_columns[1].ipa, "[rˈɛd]")

    def test_same_spelling_other_sound_is_flagged(self) -> None:
        view = card_view(verb())
        self.assertEqual([c.ipa_differs for c in view.form_columns], [False, True, True])

    def test_same_spelling_same_sound_not_flagged(self) -> None:
        view = card_view(
            verb(
                form="cut",
                transcription="kˈʌt",
                forms=read_forms(
                    past=("cut",),
                    past_ipa=("kˈʌt",),
                    past_participle=("cut",),
                    past_participle_ipa=("kˈʌt",),
                ),
            )
        )
        self.assertFalse(any(c.ipa_differs for c in view.form_columns))

    def test_variants_go_below_main_form(self) -> None:
        view = card_view(
            verb(
                form="learn",
                transcription="lˈɜːn",
                forms=read_forms(
                    past=("learnt", "learned"),
                    past_ipa=("lˈɜːnt", "lˈɜːnd"),
                    past_participle=("learnt", "learned"),
                    past_participle_ipa=("lˈɜːnt", "lˈɜːnd"),
                ),
            )
        )
        past = view.form_columns[1]
        self.assertEqual(past.form, "learnt")
        self.assertEqual(past.alternates, ("learned [lˈɜːnd]",))

    def test_forms_flags(self) -> None:
        self.assertEqual(card_view(verb()).direction_flags, "🇷🇺 → 🇬🇧")


class FormsLineTests(unittest.TestCase):
    def test_regular_card_of_irregular_verb_shows_forms_line(self) -> None:
        forms = read_forms(
            past=("bought",),
            past_ipa=("bˈɔːt",),
            past_participle=("bought",),
            past_participle_ipa=("bˈɔːt",),
        )
        for direction in ("foreign_to_native", "native_to_foreign"):
            view = card_view(verb(direction=direction, form="buy", forms=forms))
            self.assertEqual(view.forms_line, "buy — bought — bought")
            self.assertEqual(view.form_columns, ())

    def test_no_forms_no_line(self) -> None:
        self.assertEqual(card_view(card()).forms_line, "")

