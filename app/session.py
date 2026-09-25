from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

DIRECTIONS = ("foreign_to_native", "native_to_foreign")
# Irregular verb card: translation → three forms (§015). Offered instead of
# native_to_foreign when the filter includes FORMS_TEXTBOOK.
FORMS = "forms"
FORMS_TEXTBOOK = "Irregular verbs"


@dataclass(frozen=True)
class SessionFilter:
    language: str
    levels: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    textbooks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.language not in ("en", "fr"):
            raise ValueError("language must be en or fr")

    @property
    def forms_enabled(self) -> bool:
        return FORMS_TEXTBOOK in self.textbooks


@dataclass(frozen=True)
class VerbForms:
    past: tuple[str, ...]
    past_ipa: tuple[str, ...]
    past_participle: tuple[str, ...]
    past_participle_ipa: tuple[str, ...]
    cue: str | None = None


@dataclass(frozen=True)
class CardCandidate:
    entry_id: int
    direction: str
    language: str
    form: str
    part_of_speech: str
    part_of_speech_code: str | None
    transcription: str | None
    gender: str | None
    translations: tuple[str, ...]
    is_new: bool
    due_on: date | None
    interval_days: float
    ease: float
    forms: VerbForms | None = None

    @property
    def key(self) -> tuple[int, str]:
        return (self.entry_id, self.direction)


@dataclass(frozen=True)
class QueuePreview:
    due_count: int
    new_available: int
    new_remaining_today: int
    introduced_today: int


def _direction_group(direction: str) -> str:
    return "native_to_foreign" if direction == FORMS else direction


def order_by_direction(
    cards: list[CardCandidate],
    preferred: str | None,
    rng: random.Random,
) -> list[CardCandidate]:
    """Shuffle within groups; preferred direction first when set.

    `forms` asks from the native side, so it groups with native_to_foreign.
    """
    if not preferred:
        out = list(cards)
        rng.shuffle(out)
        return out
    pref = [c for c in cards if _direction_group(c.direction) == preferred]
    other = [c for c in cards if _direction_group(c.direction) != preferred]
    rng.shuffle(pref)
    rng.shuffle(other)
    return pref + other


def build_queue(
    due: list[CardCandidate],
    new: list[CardCandidate],
    new_limit: int,
    rng: random.Random,
    preferred: str | None = None,
) -> list[CardCandidate]:
    """All due first, then up to new_limit new cards. Direction bias inside each group."""
    due_cards = order_by_direction(due, preferred, rng)
    new_cards = order_by_direction(new, preferred, rng)
    return due_cards + new_cards[: max(0, new_limit)]


def build_assessment_queue(
    new: list[CardCandidate],
    batch: int,
    rng: random.Random,
    preferred: str | None = None,
) -> list[CardCandidate]:
    """Up to `batch` cards without progress; preferred direction first."""
    cards = order_by_direction(new, preferred, rng)
    return cards[: max(0, batch)]


def new_limit_for_day(introduced_today: int, per_day: int) -> int:
    return max(0, per_day - introduced_today)
