from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.session import DIRECTIONS, CardCandidate, SessionFilter


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


def fetch_candidates(conn: psycopg.Connection, flt: SessionFilter) -> list[CardCandidate]:
    query = """
        SELECT
          e.id AS entry_id,
          d.direction,
          e.language::text AS language,
          e.form,
          e.part_of_speech,
          e.part_of_speech_code,
          e.transcription,
          e.gender,
          COALESCE(p.streak, 0) AS streak,
          array_agg(tr.text ORDER BY tr.position) AS translations
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        LEFT JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction
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
        GROUP BY e.id, d.direction, p.streak
        ORDER BY e.id, d.direction
    """
    levels = list(flt.levels)
    textbooks = list(flt.textbooks)
    topics = list(flt.topics)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (
                list(DIRECTIONS),
                flt.language,
                levels,
                levels,
                textbooks,
                textbooks,
                topics,
                topics,
            ),
        )
        rows = cur.fetchall()
    return [
        CardCandidate(
            entry_id=row["entry_id"],
            direction=row["direction"],
            language=row["language"],
            form=row["form"],
            part_of_speech=row["part_of_speech"],
            part_of_speech_code=row["part_of_speech_code"],
            transcription=row["transcription"],
            gender=row["gender"],
            translations=tuple(row["translations"]),
            streak=row["streak"],
        )
        for row in rows
    ]
