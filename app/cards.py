from __future__ import annotations

from dataclasses import dataclass

from app.session import FORMS, CardCandidate

POS_LABELS = {
    "noun": "существительное",
    "adjective": "прилагательное",
    "verb": "глагол",
    "pronoun": "местоимение",
    "numeral": "числительное",
    "adverb": "наречие",
    "phrase": "фраза",
    "phrasal_verb": "фразовый глагол",
    "other": "другое",
}

GENDER_LABELS = {
    "m": "m",
    "f": "f",
}

@dataclass(frozen=True)
class FormColumn:
    """One column of the forms card back: Inf. / Past Simple / Past Part."""

    label: str
    form: str
    ipa: str
    # Same spelling as the infinitive but a different sound (read [riːd] → [red]).
    ipa_differs: bool = False
    alternates: tuple[str, ...] = ()


@dataclass(frozen=True)
class CardView:
    prompt: str
    hint: str
    ipa: str
    answer: str
    answer_hint: str
    answer_ipa: str
    direction_label: str
    direction_pair: tuple[str, str]
    form_columns: tuple[FormColumn, ...] = ()
    forms_line: str = ""


def _hint_parts(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


def direction_pair(language: str, direction: str) -> tuple[str, str]:
    """(from, to) language codes; the template draws a flag for each."""
    if direction == "foreign_to_native":
        return (language, "ru")
    return ("ru", language)


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


def _bracket(ipa: str | None) -> str:
    return f"[{ipa}]" if ipa else ""


def _form_column(
    label: str,
    forms: tuple[str, ...],
    ipas: tuple[str, ...],
    card: CardCandidate,
) -> FormColumn:
    form, ipa = forms[0], ipas[0]
    return FormColumn(
        label=label,
        form=form,
        ipa=_bracket(ipa),
        ipa_differs=(
            form.casefold() == card.form.casefold()
            and bool(card.transcription)
            and ipa != card.transcription
        ),
        alternates=tuple(
            f"{alt} {_bracket(alt_ipa)}".strip()
            for alt, alt_ipa in zip(forms[1:], ipas[1:])
        ),
    )


def forms_card_view(card: CardCandidate) -> CardView:
    """Translation → three forms (§015). Back: Inf. / Past Simple / Past Part."""
    vf = card.forms
    assert vf is not None
    return CardView(
        prompt=vf.cue or ", ".join(card.translations),
        hint="неправильный глагол · 3 формы",
        ipa="",
        answer=f"{card.form} — {vf.past[0]} — {vf.past_participle[0]}",
        answer_hint="",
        answer_ipa="",
        direction_label="русский → три формы",
        direction_pair=direction_pair(card.language, "native_to_foreign"),
        form_columns=(
            FormColumn(label="Inf.", form=card.form, ipa=_bracket(card.transcription)),
            _form_column("Past Simple", vf.past, vf.past_ipa, card),
            _form_column("Past Part.", vf.past_participle, vf.past_participle_ipa, card),
        ),
    )


def forms_line(card: CardCandidate) -> str:
    """Reference line on regular cards of an irregular verb: buy — bought — bought."""
    if card.forms is None:
        return ""
    return f"{card.form} — {card.forms.past[0]} — {card.forms.past_participle[0]}"


def card_view(card: CardCandidate) -> CardView:
    if card.direction == FORMS:
        return forms_card_view(card)
    pos = POS_LABELS.get(card.part_of_speech, card.part_of_speech)
    gender = GENDER_LABELS.get(card.gender or "", "")
    translations = ", ".join(card.translations)
    ipa = f"[{card.transcription}]" if card.transcription else ""
    pair = direction_pair(card.language, card.direction)
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
            direction_pair=pair,
            forms_line=forms_line(card),
        )
    return CardView(
        prompt=translations,
        hint=pos,
        ipa="",
        answer=shown,
        answer_hint=gender,
        answer_ipa=ipa,
        direction_label="русский → иностранный",
        direction_pair=pair,
        forms_line=forms_line(card),
    )
