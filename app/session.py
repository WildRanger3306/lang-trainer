from __future__ import annotations

import random
from dataclasses import dataclass

SESSION_SIZE = 20
DIRECTIONS = ("foreign_to_native", "native_to_foreign")


@dataclass(frozen=True)
class SessionFilter:
    language: str
    levels: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    textbooks: tuple[str, ...] = ()
    size: int = SESSION_SIZE

    def __post_init__(self) -> None:
        if self.language not in ("en", "fr"):
            raise ValueError("language must be en or fr")
        if self.size < 1:
            raise ValueError("size must be >= 1")


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
    streak: int

    @property
    def key(self) -> tuple[int, str]:
        return (self.entry_id, self.direction)

    @property
    def weight(self) -> float:
        return card_weight(self.streak)


def card_weight(streak: int) -> float:
    """Seen cards: 1 / (1 + streak). New and forgotten (streak 0) share max weight 1."""
    if streak < 0:
        raise ValueError("streak must be >= 0")
    return 1.0 / (1.0 + streak)


def pick_cards(
    pool: list[CardCandidate],
    n: int,
    rng: random.Random,
) -> list[CardCandidate]:
    remaining = list(pool)
    taken: list[CardCandidate] = []
    count = min(n, len(remaining))
    for _ in range(count):
        weights = [card.weight for card in remaining]
        total = sum(weights)
        threshold = rng.random() * total
        acc = 0.0
        index = len(remaining) - 1
        for i, weight in enumerate(weights):
            acc += weight
            if threshold <= acc:
                index = i
                break
        taken.append(remaining.pop(index))
    return taken
