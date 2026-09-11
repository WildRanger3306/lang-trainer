from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from app.scheduler import NEW_PER_DAY

DIRECTIONS = ("foreign_to_native", "native_to_foreign")


@dataclass(frozen=True)
class SessionFilter:
    language: str
    levels: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    textbooks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.language not in ("en", "fr"):
            raise ValueError("language must be en or fr")


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

    @property
    def key(self) -> tuple[int, str]:
        return (self.entry_id, self.direction)


@dataclass(frozen=True)
class QueuePreview:
    due_count: int
    new_available: int
    new_remaining_today: int
    introduced_today: int


def build_queue(
    due: list[CardCandidate],
    new: list[CardCandidate],
    new_limit: int,
    rng: random.Random,
) -> list[CardCandidate]:
    """All due first, then up to new_limit new cards. Both groups shuffled."""
    due_cards = list(due)
    new_cards = list(new)
    rng.shuffle(due_cards)
    rng.shuffle(new_cards)
    return due_cards + new_cards[: max(0, new_limit)]


def build_assessment_queue(
    new: list[CardCandidate],
    batch: int,
    rng: random.Random,
) -> list[CardCandidate]:
    """Up to `batch` cards without progress, shuffled."""
    cards = list(new)
    rng.shuffle(cards)
    return cards[: max(0, batch)]


def new_limit_for_day(introduced_today: int, per_day: int = NEW_PER_DAY) -> int:
    return max(0, per_day - introduced_today)
