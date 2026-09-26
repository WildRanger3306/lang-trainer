"""Per-user saved session filters (textbook + topics) by language."""

from __future__ import annotations

import psycopg

from app.session import NO_TOPIC, SessionFilter, make_pick, split_pick
from app.topics import WHOLE_BANK, compress_topics


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


def _topic_homes(conn: psycopg.Connection, language: str) -> dict[str, str]:
    """topic -> textbook that holds most of its words."""
    rows = conn.execute(
        """
        SELECT tp.name, tb.name, COUNT(DISTINCT e.id)
        FROM topics tp
        JOIN entry_topics eto ON eto.topic_id = tp.id
        JOIN entries e ON e.id = eto.entry_id
        JOIN entry_textbooks et ON et.entry_id = e.id
        JOIN textbooks tb ON tb.id = et.textbook_id
        WHERE e.language = %s
        GROUP BY tp.name, tb.name
        """,
        (language,),
    ).fetchall()
    best: dict[str, tuple[int, str]] = {}
    for topic, book, words in rows:
        if topic not in best or (words, book) > best[topic]:
            best[topic] = (int(words), book)
    return {topic: book for topic, (_words, book) in best.items()}


def _upgrade_legacy_topics(
    conn: psycopg.Connection,
    language: str,
    textbooks: tuple[str, ...],
    topics: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Old saves kept bare topic names; move each under its home textbook."""
    if all("/" in topic for topic in topics):
        return textbooks, topics
    homes = _topic_homes(conn, language)
    books = list(textbooks)
    picks: list[str] = []
    for topic in topics:
        if "/" in topic:
            picks.append(topic)
            continue
        home = homes.get(topic)
        if home is None:
            continue
        if home not in books:
            books.append(home)
        picks.append(make_pick(home, topic))
    return tuple(books), tuple(picks)


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
    textbooks, topics = _upgrade_legacy_topics(
        conn, language, tuple(row[0] or ()), tuple(row[1] or ())
    )
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
    books = list(dict.fromkeys(textbooks))
    # A topic only counts inside a selected textbook.
    tops = [pick for pick in dict.fromkeys(topics) if split_pick(pick)[0] in books]
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
    if not flt.textbooks:
        return "учебник не выбран"
    picks: dict[str, list[str]] = {}
    for pick in flt.topics:
        book, topic = split_pick(pick)
        picks.setdefault(book, []).append(topic)
    parts: list[str] = []
    for book in flt.textbooks:
        topics = picks.get(book, [])
        if not topics:
            parts.append(book)
            continue
        regular = [t for t in topics if t != NO_TOPIC and t not in WHOLE_BANK]
        labels = [compress_topics(regular)] if regular else []
        if NO_TOPIC in topics:
            labels.append("без темы")
        parts.append(f"{book} ({', '.join(labels)})" if labels else book)
    return " · ".join(parts)
