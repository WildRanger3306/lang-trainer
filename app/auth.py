"""In-memory auth sessions (cookie token → user_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.users import User


@dataclass
class AuthSession:
    user: User


class AuthStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AuthSession] = {}

    def create(self, user: User) -> str:
        token = uuid.uuid4().hex
        self._sessions[token] = AuthSession(user=user)
        return token

    def get(self, token: str | None) -> AuthSession | None:
        if not token:
            return None
        return self._sessions.get(token)

    def destroy(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)
