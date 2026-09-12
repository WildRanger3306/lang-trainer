"""Per-user saved session filters (textbook + topics) by language."""

from __future__ import annotations

import psycopg

from app.session import SessionFilter


def get_last_language(conn: psycopg.Connection, user_id: int) -> str | None:
    row = conn.execute(
        "SELECT last_language FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])


def set_last_language(conn: psycopg.Connection, user_id: int, language: str) -> None:
    if language not in ("en", "fr"):
        raise ValueError("language must be en or fr")
    conn.execute(
        "UPDATE users SET last_language = %s::language_code WHERE id = %s",
        (language, user_id),
    )
    conn.commit()


def get_user_filter(
    conn: psycopg.Connection, user_id: int, language: str
) -> SessionFilter:
    if language not in ("en", "fr"):
        raise ValueError("language must be en or fr")
    row = conn.execute(
        """
        SELECT textbooks, topics
        FROM user_language_filters
        WHERE user_id = %s AND language = %s::language_code
        """,
        (user_id, language),
    ).fetchone()
    if row is None:
        return SessionFilter(language=language)
    textbooks = tuple(row[0] or ())
    topics = tuple(row[1] or ())
    return SessionFilter(language=language, textbooks=textbooks, topics=topics)


def save_user_filter(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    textbooks: list[str] | tuple[str, ...],
    topics: list[str] | tuple[str, ...],
) -> SessionFilter:
    if language not in ("en", "fr"):
        raise ValueError("language must be en or fr")
    books = list(textbooks)
    tops = list(topics)
    conn.execute(
        """
        INSERT INTO user_language_filters (user_id, language, textbooks, topics)
        VALUES (%s, %s::language_code, %s::text[], %s::text[])
        ON CONFLICT (user_id, language) DO UPDATE SET
          textbooks = EXCLUDED.textbooks,
          topics = EXCLUDED.topics
        """,
        (user_id, language, books, tops),
    )
    conn.commit()
    return SessionFilter(
        language=language, textbooks=tuple(books), topics=tuple(tops)
    )


def filter_summary(flt: SessionFilter) -> str:
    """Short human-readable active filter for the home screen."""
    parts: list[str] = []
    if flt.textbooks:
        parts.append(", ".join(flt.textbooks))
    if flt.topics:
        parts.append(", ".join(flt.topics))
    if not parts:
        return "весь язык"
    return " · ".join(parts)
