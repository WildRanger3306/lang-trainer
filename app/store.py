from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.session import CardCandidate


@dataclass
class TrainingSession:
    cards: list[CardCandidate]
    index: int = 0
    known: int = 0
    unknown: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    @property
    def current(self) -> CardCandidate | None:
        if self.index >= len(self.cards):
            return None
        return self.cards[self.index]

    @property
    def done(self) -> bool:
        return self.index >= len(self.cards)

    @property
    def number(self) -> int:
        return self.index + 1

    @property
    def total(self) -> int:
        return len(self.cards)

    @property
    def duration_seconds(self) -> int:
        end = self.finished_at or datetime.now()
        return max(0, int((end - self.started_at).total_seconds()))

    @property
    def answered(self) -> int:
        return self.known + self.unknown

    def finish(self) -> None:
        self.index = len(self.cards)
        if self.finished_at is None:
            self.finished_at = datetime.now()


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, TrainingSession] = {}

    def create(self, cards: list[CardCandidate]) -> str:
        token = uuid.uuid4().hex
        self._sessions[token] = TrainingSession(cards=cards)
        return token

    def get(self, token: str | None) -> TrainingSession | None:
        if not token:
            return None
        return self._sessions.get(token)
