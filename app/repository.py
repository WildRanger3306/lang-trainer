from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.load_limits import get_new_per_day
from app.session import DIRECTIONS, CardCandidate, QueuePreview, SessionFilter


@dataclass(frozen=True)
class TextbookBank:
    name: str
    lexemes: int


@dataclass(frozen=True)
class LanguageBanks:
    language: str
    label: str
    textbooks: tuple[TextbookBank, ...]
    unique_total: int


def fetch_textbook_banks(conn: psycopg.Connection) -> tuple[LanguageBanks, ...]:
    """Learner-facing corpus sizes; skip FR Trainer and similar service sets."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT e.language::text AS language, t.name, count(DISTINCT e.id) AS lexemes
            FROM textbooks t
            JOIN entry_textbooks et ON et.textbook_id = t.id
            JOIN entries e ON e.id = et.entry_id
            WHERE t.name NOT ILIKE '%trainer%'
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
        by_lang: dict[str, list[TextbookBank]] = {"en": [], "fr": []}
        for row in cur.fetchall():
            lang = str(row["language"])
            if lang not in by_lang:
                continue
            by_lang[lang].append(
                TextbookBank(name=str(row["name"]), lexemes=int(row["lexemes"]))
            )

        out: list[LanguageBanks] = []
        labels = {"en": "Английский (Starlight)", "fr": "Французский (Loiseau Blue)"}
        for lang, label in labels.items():
            cur.execute(
                """
                SELECT count(*) FROM entries e
                WHERE e.language = %s
                  AND EXISTS (
                    SELECT 1
                    FROM entry_textbooks et
                    JOIN textbooks t ON t.id = et.textbook_id
                    WHERE et.entry_id = e.id
                      AND t.name NOT ILIKE '%%trainer%%'
                  )
                """,
                (lang,),
            )
            unique_total = int(cur.fetchone()["count"])
            out.append(
                LanguageBanks(
                    language=lang,
                    label=label,
                    textbooks=tuple(by_lang.get(lang, [])),
                    unique_total=unique_total,
                )
            )
    return tuple(out)


@dataclass(frozen=True)
class TopicOption:
    name: str
    count: int


@dataclass(frozen=True)
class FilterOptions:
    textbooks: tuple[str, ...]
    topics: tuple[TopicOption, ...]
    levels: tuple[str, ...]


def fetch_filter_options(conn: psycopg.Connection, language: str) -> FilterOptions:
    """Options scoped to entries of the selected language (EN→Starlight, FR→Loiseau Blue)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT tb.name
            FROM textbooks tb
            JOIN entry_textbooks et ON et.textbook_id = tb.id
            JOIN entries e ON e.id = et.entry_id
            WHERE e.language = %s
            ORDER BY tb.name
            """,
            (language,),
        )
        textbooks = tuple(row[0] for row in cur.fetchall())
        cur.execute(
            """
            SELECT tp.name, COUNT(DISTINCT e.id)::int
            FROM topics tp
            JOIN entry_topics eto ON eto.topic_id = tp.id
            JOIN entries e ON e.id = eto.entry_id
            WHERE e.language = %s
            GROUP BY tp.name
            ORDER BY tp.name
            """,
            (language,),
        )
        topics = tuple(TopicOption(name=row[0], count=row[1]) for row in cur.fetchall())
        cur.execute(
            """
            SELECT DISTINCT level
            FROM entries
            WHERE language = %s AND level IS NOT NULL
            ORDER BY level
            """,
            (language,),
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
        ease=float(row["difficulty"]) if row.get("difficulty") is not None else 0.0,
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
          p.stability,
          p.difficulty,
          array_agg(tr.text ORDER BY tr.position) AS translations
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
        {_filter_clause()}
          AND p.due_on <= %s
        GROUP BY e.id, d.direction, p.due_on, p.interval_days, p.stability, p.difficulty
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
          NULL::double precision AS stability,
          NULL::double precision AS difficulty,
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
    remaining = new_limit_for_day(
        introduced, get_new_per_day(conn, user_id, flt.language)
    )
    return QueuePreview(
        due_count=len(due),
        new_available=len(new),
        new_remaining_today=remaining,
        introduced_today=introduced,
    )
