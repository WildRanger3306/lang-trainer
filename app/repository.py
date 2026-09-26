from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.load_limits import get_new_per_day
from app.session import (
    DIRECTIONS,
    FORMS,
    FORMS_TEXTBOOK,
    NO_TOPIC,
    CardCandidate,
    QueuePreview,
    SessionFilter,
    VerbForms,
)


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


# Word progress buckets match the stats page: interval of the word's weakest card.
KNOWN_DAYS = 21
CONSOLIDATING_DAYS = 7

_PROGRESS_CTE = """
    WITH prog AS (
      SELECT entry_id, MIN(interval_days) AS iv
      FROM card_progress WHERE user_id = %s GROUP BY entry_id
    )
"""
_PROGRESS_COLUMNS = f"""
    COUNT(DISTINCT e.id)::int,
    COUNT(DISTINCT e.id) FILTER (WHERE p.iv >= {KNOWN_DAYS})::int,
    COUNT(DISTINCT e.id) FILTER (WHERE p.iv >= {CONSOLIDATING_DAYS} AND p.iv < {KNOWN_DAYS})::int,
    COUNT(DISTINCT e.id) FILTER (WHERE p.iv < {CONSOLIDATING_DAYS})::int
"""


@dataclass(frozen=True)
class WordProgress:
    """How many of `words` the user knows firmly / is consolidating / is still learning."""

    words: int
    known: int
    consolidating: int
    learning: int

    @property
    def started(self) -> int:
        return self.known + self.consolidating + self.learning

    def shares(self) -> tuple[float, float, float]:
        """Cumulative percent stops (known, +consolidating, +learning) for the bar."""
        if not self.words:
            return (0.0, 0.0, 0.0)
        known = self.known * 100 / self.words
        mid = known + self.consolidating * 100 / self.words
        return (round(known, 1), round(mid, 1), round(self.started * 100 / self.words, 1))


@dataclass(frozen=True)
class TopicChip:
    """A topic (or the virtual "no topic" chip) inside one textbook."""

    name: str
    progress: WordProgress

    @property
    def words(self) -> int:
        return self.progress.words


@dataclass(frozen=True)
class FilterBank:
    """One textbook with the words in it and the chips that slice it."""

    name: str
    progress: WordProgress
    chips: tuple[TopicChip, ...]
    no_topic: TopicChip | None

    @property
    def words(self) -> int:
        return self.progress.words


def fetch_filter_banks(
    conn: psycopg.Connection, language: str, user_id: int
) -> tuple[FilterBank, ...]:
    """Textbooks of the language with word counts, this user's progress and topics.

    A topic is listed only under its home textbook (the one holding most of its words);
    words shared with other textbooks stay reachable through those textbooks' own topics.
    """
    with conn.cursor() as cur:
        cur.execute(
            _PROGRESS_CTE
            + f"""
            SELECT tb.name, {_PROGRESS_COLUMNS}
            FROM textbooks tb
            JOIN entry_textbooks et ON et.textbook_id = tb.id
            JOIN entries e ON e.id = et.entry_id
            LEFT JOIN prog p ON p.entry_id = e.id
            WHERE e.language = %s
            GROUP BY tb.name
            """,
            (user_id, language),
        )
        books = {row[0]: WordProgress(*row[1:]) for row in cur.fetchall()}
        cur.execute(
            _PROGRESS_CTE
            + f"""
            SELECT tb.name, tp.name, {_PROGRESS_COLUMNS}
            FROM textbooks tb
            JOIN entry_textbooks et ON et.textbook_id = tb.id
            JOIN entries e ON e.id = et.entry_id
            JOIN entry_topics eto ON eto.entry_id = e.id
            JOIN topics tp ON tp.id = eto.topic_id
            LEFT JOIN prog p ON p.entry_id = e.id
            WHERE e.language = %s
            GROUP BY tb.name, tp.name
            """,
            (user_id, language),
        )
        pairs = [(row[0], row[1], WordProgress(*row[2:])) for row in cur.fetchall()]
        cur.execute(
            _PROGRESS_CTE
            + f"""
            SELECT tb.name, {_PROGRESS_COLUMNS}
            FROM textbooks tb
            JOIN entry_textbooks et ON et.textbook_id = tb.id
            JOIN entries e ON e.id = et.entry_id
            LEFT JOIN prog p ON p.entry_id = e.id
            WHERE e.language = %s
              AND NOT EXISTS (SELECT 1 FROM entry_topics x WHERE x.entry_id = e.id)
            GROUP BY tb.name
            """,
            (user_id, language),
        )
        untopiced = {row[0]: TopicChip(NO_TOPIC, WordProgress(*row[1:])) for row in cur.fetchall()}

    home: dict[str, tuple[int, str]] = {}
    for book, topic, progress in pairs:
        best = home.get(topic)
        if best is None or (progress.words, book) > best:
            home[topic] = (progress.words, book)
    chips: dict[str, list[TopicChip]] = {name: [] for name in books}
    for book, topic, progress in sorted(pairs, key=lambda r: r[1]):
        if home[topic][1] == book:
            chips[book].append(TopicChip(topic, progress))

    ordered = sorted(books, key=lambda name: (name == FORMS_TEXTBOOK, name))
    return tuple(
        FilterBank(
            name=name,
            progress=books[name],
            chips=tuple(chips[name]),
            no_topic=untopiced.get(name),
        )
        for name in ordered
    )


def count_filter_words(
    conn: psycopg.Connection, flt: SessionFilter, user_id: int
) -> tuple[int, int]:
    """(words matching the filter, of them started by the user)."""
    row = conn.execute(
        f"""
        SELECT COUNT(*)::int,
               COUNT(*) FILTER (WHERE EXISTS (
                 SELECT 1 FROM card_progress p WHERE p.entry_id = e.id AND p.user_id = %s
               ))::int
        FROM entries e
        {_filter_clause()}
        """,
        (user_id, *_filter_params(flt)),
    ).fetchone()
    return int(row[0]), int(row[1])


def _filter_clause() -> str:
    """Selected textbooks are OR-ed; picks narrow each selected textbook on its own.

    A textbook without picks contributes all its words; with picks, only words that
    have a picked topic (or no topic at all for the NO_TOPIC pick). Picks of
    unselected textbooks are ignored. No textbook selected = no words at all.
    """
    return f"""
        WHERE e.language = %s
          AND (
            cardinality(%s::cefr_level[]) = 0
            OR e.level = ANY(%s::cefr_level[])
          )
          AND EXISTS (
              SELECT 1
              FROM unnest(%s::text[]) AS sel(book)
              WHERE EXISTS (
                SELECT 1
                FROM entry_textbooks et
                JOIN textbooks tb ON tb.id = et.textbook_id
                WHERE et.entry_id = e.id AND tb.name = sel.book
              )
              AND (
                NOT EXISTS (
                  SELECT 1 FROM unnest(%s::text[]) AS pk
                  WHERE split_part(pk, '/', 1) = sel.book
                )
                OR EXISTS (
                  SELECT 1 FROM unnest(%s::text[]) AS pk
                  WHERE split_part(pk, '/', 1) = sel.book
                    AND (
                      (
                        split_part(pk, '/', 2) = '{NO_TOPIC}'
                        AND NOT EXISTS (
                          SELECT 1 FROM entry_topics x WHERE x.entry_id = e.id
                        )
                      )
                      OR EXISTS (
                        SELECT 1
                        FROM entry_topics eto
                        JOIN topics tp ON tp.id = eto.topic_id
                        WHERE eto.entry_id = e.id
                          AND tp.name = split_part(pk, '/', 2)
                      )
                    )
                )
              )
            )
    """


def _card_directions() -> list[str]:
    return [*DIRECTIONS, FORMS]


def _direction_clause() -> str:
    """Card set per entry is computed from the filter (§015): with FORMS_TEXTBOOK
    selected, a verb with forms gets `forms` instead of native_to_foreign."""
    return """
          AND CASE d.direction
            WHEN 'forms' THEN %s AND vf.entry_id IS NOT NULL
            WHEN 'native_to_foreign' THEN NOT (%s AND vf.entry_id IS NOT NULL)
            ELSE TRUE
          END
    """


def _direction_params(flt: SessionFilter) -> tuple:
    return (flt.forms_enabled, flt.forms_enabled)


_FORMS_COLUMNS = """
          vf.entry_id AS vf_entry_id,
          vf.past,
          vf.past_ipa,
          vf.past_participle,
          vf.past_participle_ipa,
          vf.cue
"""


def _row_forms(row: dict) -> VerbForms | None:
    if row.get("vf_entry_id") is None:
        return None
    return VerbForms(
        past=tuple(row["past"]),
        past_ipa=tuple(row["past_ipa"]),
        past_participle=tuple(row["past_participle"]),
        past_participle_ipa=tuple(row["past_participle_ipa"]),
        cue=row["cue"],
    )


def _filter_params(flt: SessionFilter) -> tuple:
    levels = list(flt.levels)
    textbooks = list(flt.textbooks)
    topics = list(flt.topics)
    return (
        flt.language,
        levels,
        levels,
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
        forms=_row_forms(row),
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
          array_agg(tr.text ORDER BY tr.position) AS translations,
          {_FORMS_COLUMNS}
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
        LEFT JOIN verb_forms vf ON vf.entry_id = e.id
        {_filter_clause()}
        {_direction_clause()}
          AND p.due_on <= %s
        GROUP BY e.id, d.direction, p.due_on, p.interval_days, p.stability, p.difficulty,
          vf.entry_id
        ORDER BY e.id, d.direction
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (
                _card_directions(),
                user_id,
                *_filter_params(flt),
                *_direction_params(flt),
                today,
            ),
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
          array_agg(tr.text ORDER BY tr.position) AS translations,
          {_FORMS_COLUMNS}
        FROM entries e
        CROSS JOIN unnest(%s::card_direction[]) AS d(direction)
        JOIN entry_translations tr ON tr.entry_id = e.id
        LEFT JOIN card_progress p
          ON p.entry_id = e.id AND p.direction = d.direction AND p.user_id = %s
        LEFT JOIN verb_forms vf ON vf.entry_id = e.id
        {_filter_clause()}
        {_direction_clause()}
          AND p.entry_id IS NULL
        GROUP BY e.id, d.direction, vf.entry_id
        ORDER BY e.id, d.direction
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (
                _card_directions(),
                user_id,
                *_filter_params(flt),
                *_direction_params(flt),
            ),
        )
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
