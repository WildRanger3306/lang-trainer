"""Password hashing and user CRUD."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

LOGIN_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
PBKDF2_ROUNDS = 200_000

ALL_LANGUAGES = ("en", "fr")

# Home-screen actions a user can start: train (FSRS session) and assess (know/doubt/
# unknown triage). Distinct from app.main.TRAIN_MODES, which groups train with verbs
# for a different purpose (which sessions use FSRS grading).
USER_MODES = ("train", "assess")


@dataclass(frozen=True)
class User:
    id: int
    login: str
    display_name: str | None
    is_admin: bool = False
    allowed_languages: tuple[str, ...] = ALL_LANGUAGES
    allowed_modes: tuple[str, ...] = USER_MODES

    @property
    def label(self) -> str:
        return self.display_name or self.login

    def can_use(self, language: str) -> bool:
        return language in self.allowed_languages

    @property
    def default_language(self) -> str:
        """First allowed language; "en" if somehow none (shouldn't happen, DB default is both)."""
        return self.allowed_languages[0] if self.allowed_languages else "en"

    def can_start(self, mode: str) -> bool:
        return mode in self.allowed_modes


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ROUNDS,
    )
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_s, salt, digest_hex = stored.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    try:
        rounds = int(rounds_s)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        rounds,
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def clean_languages(codes) -> tuple[str, ...]:
    """Known language codes only, in a stable order, without duplicates."""
    wanted = set(codes)
    return tuple(code for code in ALL_LANGUAGES if code in wanted)


def clean_modes(codes) -> tuple[str, ...]:
    """Known mode codes only, in a stable order, without duplicates."""
    wanted = set(codes)
    return tuple(code for code in USER_MODES if code in wanted)


def validate_login(login: str) -> str:
    login = login.strip()
    if not login or not LOGIN_RE.match(login):
        raise ValueError("login must be [a-zA-Z0-9_-]+")
    return login


def _user_from_row(row: dict) -> User:
    return User(
        id=int(row["id"]),
        login=row["login"],
        display_name=row["display_name"],
        is_admin=bool(row["is_admin"]),
        allowed_languages=tuple(row["allowed_languages"] or ()),
        allowed_modes=tuple(row["allowed_modes"] or ()),
    )


def get_user_by_login(conn: psycopg.Connection, login: str) -> tuple[User, str] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, login, display_name, is_admin, allowed_languages::text[], allowed_modes, password_hash
            FROM users WHERE login = %s
            """,
            (login,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _user_from_row(row), row["password_hash"]


def get_user_by_id(conn: psycopg.Connection, user_id: int) -> User | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, login, display_name, is_admin, allowed_languages::text[], allowed_modes
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _user_from_row(row)


def list_users(conn: psycopg.Connection) -> list[User]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, login, display_name, is_admin, allowed_languages::text[], allowed_modes
            FROM users ORDER BY login
            """
        )
        return [_user_from_row(row) for row in cur.fetchall()]


def create_user(
    conn: psycopg.Connection,
    login: str,
    password: str,
    *,
    display_name: str | None = None,
) -> User:
    login = validate_login(login)
    if not password:
        raise ValueError("password required")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO users (login, password_hash, display_name)
            VALUES (%s, %s, %s)
            RETURNING id, login, display_name, is_admin, allowed_languages::text[], allowed_modes
            """,
            (login, hash_password(password), display_name),
        )
        row = cur.fetchone()
    conn.commit()
    return _user_from_row(row)


def set_admin(conn: psycopg.Connection, login: str, is_admin: bool) -> None:
    cur = conn.execute(
        "UPDATE users SET is_admin = %s WHERE login = %s", (is_admin, login)
    )
    if cur.rowcount == 0:
        raise ValueError(f"user not found: {login}")
    conn.commit()


def set_allowed_languages(
    conn: psycopg.Connection, user_id: int, languages
) -> tuple[str, ...]:
    """At least one language must stay enabled — otherwise the account is unusable."""
    cleaned = clean_languages(languages)
    if not cleaned:
        raise ValueError("at least one language must stay allowed")
    conn.execute(
        "UPDATE users SET allowed_languages = %s::language_code[] WHERE id = %s",
        (list(cleaned), user_id),
    )
    conn.commit()
    return cleaned


def set_allowed_modes(conn: psycopg.Connection, user_id: int, modes) -> tuple[str, ...]:
    """At least one mode must stay enabled — otherwise the account is unusable."""
    cleaned = clean_modes(modes)
    if not cleaned:
        raise ValueError("at least one mode must stay allowed")
    conn.execute(
        "UPDATE users SET allowed_modes = %s::text[] WHERE id = %s",
        (list(cleaned), user_id),
    )
    conn.commit()
    return cleaned


def set_password(conn: psycopg.Connection, login: str, password: str) -> None:
    login = validate_login(login)
    cur = conn.execute(
        """
        UPDATE users SET password_hash = %s WHERE login = %s
        """,
        (hash_password(password), login),
    )
    if cur.rowcount == 0:
        raise ValueError(f"user not found: {login}")
    conn.commit()


def authenticate(conn: psycopg.Connection, login: str, password: str) -> User | None:
    found = get_user_by_login(conn, login.strip())
    if found is None:
        return None
    user, password_hash = found
    if not verify_password(password, password_hash):
        return None
    return user


def assign_orphan_progress(conn: psycopg.Connection, user_id: int) -> tuple[int, int]:
    """Attach progress/reviews with NULL user_id to this user. Returns (progress, reviews)."""
    p = conn.execute(
        """
        UPDATE card_progress SET user_id = %s WHERE user_id IS NULL
        """,
        (user_id,),
    )
    r = conn.execute(
        """
        UPDATE card_reviews SET user_id = %s WHERE user_id IS NULL
        """,
        (user_id,),
    )
    conn.commit()
    return int(p.rowcount or 0), int(r.rowcount or 0)
