from __future__ import annotations

from dataclasses import dataclass

from app.session import CardCandidate

POS_LABELS = {
    "noun": "существительное",
    "adjective": "прилагательное",
    "verb": "глагол",
    "pronoun": "местоимение",
    "numeral": "числительное",
    "adverb": "наречие",
    "phrase": "фраза",
    "other": "другое",
}

GENDER_LABELS = {
    "m": "m",
    "f": "f",
}

FLAGS = {
    "ru": "🇷🇺",
    "fr": "🇫🇷",
    "en": "🇬🇧",
}


@dataclass(frozen=True)
class CardView:
    prompt: str
    hint: str
    ipa: str
    answer: str
    answer_hint: str
    answer_ipa: str
    direction_label: str
    direction_flags: str


def _hint_parts(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


def direction_flags(language: str, direction: str) -> str:
    foreign = FLAGS.get(language, language)
    native = FLAGS["ru"]
    if direction == "foreign_to_native":
        return f"{foreign} → {native}"
    return f"{native} → {foreign}"


def _is_plural_code(code: str | None) -> bool:
    if not code:
        return False
    return "pl" in code.casefold()


def definite_article(gender: str | None, *, plural: bool) -> str | None:
    """MVP: le / la / les only (no elision)."""
    if plural:
        return "les"
    if gender == "m":
        return "le"
    if gender == "f":
        return "la"
    return None


def display_form(card: CardCandidate) -> str:
    """Foreign form as shown on the card; FR nouns may get le/la/les."""
    if (
        card.language == "fr"
        and card.part_of_speech == "noun"
        and card.gender
    ):
        article = definite_article(
            card.gender, plural=_is_plural_code(card.part_of_speech_code)
        )
        if article:
            return f"{article} {card.form}"
    return card.form


def card_view(card: CardCandidate) -> CardView:
    pos = POS_LABELS.get(card.part_of_speech, card.part_of_speech)
    gender = GENDER_LABELS.get(card.gender or "", "")
    translations = ", ".join(card.translations)
    ipa = f"[{card.transcription}]" if card.transcription else ""
    flags = direction_flags(card.language, card.direction)
    shown = display_form(card)
    if card.direction == "foreign_to_native":
        return CardView(
            prompt=shown,
            hint=_hint_parts(pos, gender),
            ipa=ipa,
            answer=translations,
            answer_hint="",
            answer_ipa="",
            direction_label="иностранный → русский",
            direction_flags=flags,
        )
    return CardView(
        prompt=translations,
        hint=pos,
        ipa="",
        answer=shown,
        answer_hint=gender,
        answer_ipa=ipa,
        direction_label="русский → иностранный",
        direction_flags=flags,
    )
