from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.scheduler import new_per_day
from app.session import DIRECTIONS, CardCandidate, QueuePreview, SessionFilter


@dataclass(frozen=True)
class FilterOptions:
    textbooks: tuple[str, ...]
    topics: tuple[str, ...]
    levels: tuple[str, ...]


def fetch_filter_options(conn: psycopg.Connection) -> FilterOptions:
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM textbooks ORDER BY name")
        textbooks = tuple(row[0] for row in cur.fetchall())
        cur.execute("SELECT name FROM topics ORDER BY name")
        topics = tuple(row[0] for row in cur.fetchall())
        cur.execute(
            "SELECT DISTINCT level FROM entries WHERE level IS NOT NULL ORDER BY level"
        )
        levels = tuple(row[0] for row in cur.fetchall())
    return FilterOptions(textbooks=textbooks, topics=topics, levels=levels)


def _filter_clause() -> str:
    return """
        WHERE e.language = %s
          AND (
            cardinality(%s::cefr_level[]) = 0
            OR e.level = ANY(%s::cefr_level[])
          )
          AND (
            cardinality(%s::text[]) = 0
            OR EXISTS (
              SELECT 1
              FROM entry_textbooks et
              JOIN textbooks tb ON tb.id = et.textbook_id
              WHERE et.entry_id = e.id AND tb.name = ANY(%s)
            )
          )
          AND (
            cardinality(%s::text[]) = 0
            OR EXISTS (
              SELECT 1
              FROM entry_topics eto
              JOIN topics tp ON tp.id = eto.topic_id
              WHERE eto.entry_id = e.id AND tp.name = ANY(%s)
            )
          )
    """


def _filter_params(flt: SessionFilter) -> tuple:
    levels = list(flt.levels)
    textbooks = list(flt.textbooks)
    topics = list(flt.topics)
    return (
        flt.language,
        levels,
        levels,
        textbooks,
        textbooks,
        topics,
        topics,
    )


def _row_to_card(row: dict, *, is_new: bool) -> CardCandidate:
    return CardCandidate(
        entry_id=row["entry_id"],
        direction=row["direction"],
        language=row["language"],
        form=row["form"],
        part_of_speech=row["part_of_speech"],
        part_of_speech_code=row["part_of_speech_code"],
        transcription=row["transcription"],
        gender=row["gender"],
        translations=tuple(row["translations"]),
        is_new=is_new,
        due_on=row.get("due_on"),
        interval_days=float(row["interval_days"]) if row.get("interval_days") is not None else 0.0,
        ease=float(row["ease"]) if row.get("ease") is not None else 2.5,
    )


def fetch_due_candidates(
    conn: psycopg.Connection,
    flt: SessionFilter,
    user_id: int,
    today: date | None = None,
) -> list[CardCandidate]:
    today = today or date.today()
    query = f"""
        SELECT
          e.id AS entry_id,
          d.direction,
          e.language::text AS language,
          e.form,
          e.part_of_speech,
          e.part_of_speech_code,
          e.transcription,
          e.gender,
          p.due_on,
          p.interval_days,
          p.ease,
          array_agg(tr.text ORDER BY tr.position) AS translations
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
        {_filter_clause()}
          AND p.due_on <= %s
        GROUP BY e.id, d.direction, p.due_on, p.interval_days, p.ease
        ORDER BY e.id, d.direction
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query, (list(DIRECTIONS), user_id, *_filter_params(flt), today)
        )
        rows = cur.fetchall()
    return [_row_to_card(row, is_new=False) for row in rows]


def fetch_new_candidates(
    conn: psycopg.Connection,
    flt: SessionFilter,
    user_id: int,
) -> list[CardCandidate]:
    query = f"""
        SELECT
          e.id AS entry_id,
          d.direction,
          e.language::text AS language,
          e.form,
          e.part_of_speech,
          e.part_of_speech_code,
          e.transcription,
          e.gender,
          NULL::date AS due_on,
          NULL::double precision AS interval_days,
          NULL::double precision AS ease,
          array_agg(tr.text ORDER BY tr.position) AS translations
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        LEFT JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
        {_filter_clause()}
          AND p.entry_id IS NULL
        GROUP BY e.id, d.direction
        ORDER BY e.id, d.direction
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (list(DIRECTIONS), user_id, *_filter_params(flt)))
        rows = cur.fetchall()
    return [_row_to_card(row, is_new=True) for row in rows]


def fetch_queue_preview(
    conn: psycopg.Connection,
    flt: SessionFilter,
    user_id: int,
    today: date | None = None,
) -> QueuePreview:
    from app.progress import count_introduced_today
    from app.session import new_limit_for_day

    today = today or date.today()
    due = fetch_due_candidates(conn, flt, user_id, today)
    new = fetch_new_candidates(conn, flt, user_id)
    introduced = count_introduced_today(conn, user_id, flt.language, today)
    remaining = new_limit_for_day(introduced, new_per_day(flt.language))
    return QueuePreview(
        due_count=len(due),
        new_available=len(new),
        new_remaining_today=remaining,
        introduced_today=introduced,
    )
