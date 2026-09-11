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


@dataclass(frozen=True)
class User:
    id: int
    login: str
    display_name: str | None

    @property
    def label(self) -> str:
        return self.display_name or self.login


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


def validate_login(login: str) -> str:
    login = login.strip()
    if not login or not LOGIN_RE.match(login):
        raise ValueError("login must be [a-zA-Z0-9_-]+")
    return login


def get_user_by_login(conn: psycopg.Connection, login: str) -> tuple[User, str] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, login, display_name, password_hash
            FROM users WHERE login = %s
            """,
            (login,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    user = User(
        id=int(row["id"]),
        login=row["login"],
        display_name=row["display_name"],
    )
    return user, row["password_hash"]


def get_user_by_id(conn: psycopg.Connection, user_id: int) -> User | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, login, display_name
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        login=row["login"],
        display_name=row["display_name"],
    )


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
    row = conn.execute(
        """
        INSERT INTO users (login, password_hash, display_name)
        VALUES (%s, %s, %s)
        RETURNING id, login, display_name
        """,
        (login, hash_password(password), display_name),
    ).fetchone()
    conn.commit()
    return User(id=int(row[0]), login=row[1], display_name=row[2])


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
