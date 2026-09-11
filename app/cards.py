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
    answer: str
    answer_hint: str
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


def card_view(card: CardCandidate) -> CardView:
    pos = POS_LABELS.get(card.part_of_speech, card.part_of_speech)
    gender = GENDER_LABELS.get(card.gender or "", "")
    translations = ", ".join(card.translations)
    transcription = card.transcription or ""
    flags = direction_flags(card.language, card.direction)
    if card.direction == "foreign_to_native":
        return CardView(
            prompt=card.form,
            hint=_hint_parts(pos, gender, transcription),
            answer=translations,
            answer_hint="",
            direction_label="иностранный → русский",
            direction_flags=flags,
        )
    return CardView(
        prompt=translations,
        hint=pos,
        answer=card.form,
        answer_hint=_hint_parts(gender, transcription),
        direction_label="русский → иностранный",
        direction_flags=flags,
    )
