from __future__ import annotations

from datetime import date, datetime, timezone

import psycopg
from psycopg.rows import dict_row

from app.scheduler import ScheduleState, apply_assessment, apply_grade
from app.session import CardCandidate


def _load_state(
    conn: psycopg.Connection, entry_id: int, direction: str
) -> ScheduleState | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT due_on, interval_days, ease, introduced_on
            FROM card_progress
            WHERE entry_id = %s AND direction = %s
            """,
            (entry_id, direction),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return ScheduleState(
        due_on=row["due_on"],
        interval_days=float(row["interval_days"]),
        ease=float(row["ease"]),
        introduced_on=row["introduced_on"],
    )


def _upsert_progress(
    conn: psycopg.Connection,
    card: CardCandidate,
    nxt: ScheduleState,
    *,
    introduced_via: str,
    remembered: bool,
    was_new: bool,
    interval_before: float,
    source: str,
    answered_at: datetime,
    today: date,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO card_progress (
              entry_id, direction, due_on, interval_days, ease,
              introduced_on, introduced_via
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (entry_id, direction)
            DO UPDATE SET
              due_on = EXCLUDED.due_on,
              interval_days = EXCLUDED.interval_days,
              ease = EXCLUDED.ease
            """,
            (
                card.entry_id,
                card.direction,
                nxt.due_on,
                nxt.interval_days,
                nxt.ease,
                nxt.introduced_on,
                introduced_via,
            ),
        )
        cur.execute(
            """
            INSERT INTO card_reviews (
              entry_id, direction, answered_at, answered_on, remembered,
              was_new, interval_before, interval_after, source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                card.entry_id,
                card.direction,
                answered_at,
                today,
                remembered,
                was_new,
                interval_before,
                nxt.interval_days,
                source,
            ),
        )


def save_grade(
    conn: psycopg.Connection,
    card: CardCandidate,
    remembered: bool,
    today: date | None = None,
    answered_at: datetime | None = None,
) -> ScheduleState:
    today = today or date.today()
    answered_at = answered_at or datetime.now(timezone.utc)
    current = _load_state(conn, card.entry_id, card.direction)
    was_new = current is None
    interval_before = 0.0 if current is None else float(current.interval_days)
    nxt = apply_grade(current, remembered, today)
    _upsert_progress(
        conn,
        card,
        nxt,
        introduced_via="train",
        remembered=remembered,
        was_new=was_new,
        interval_before=interval_before,
        source="train",
        answered_at=answered_at,
        today=today,
    )
    conn.commit()
    return nxt


def save_assessment(
    conn: psycopg.Connection,
    card: CardCandidate,
    verdict: str,
    today: date | None = None,
    answered_at: datetime | None = None,
) -> ScheduleState:
    """Introduce a new card via assessment. Does not count toward NEW_PER_DAY."""
    today = today or date.today()
    answered_at = answered_at or datetime.now(timezone.utc)
    current = _load_state(conn, card.entry_id, card.direction)
    if current is not None:
        raise ValueError("assessment only applies to cards without progress")
    nxt = apply_assessment(verdict, today)
    remembered = verdict != "unknown"
    _upsert_progress(
        conn,
        card,
        nxt,
        introduced_via="assess",
        remembered=remembered,
        was_new=True,
        interval_before=0.0,
        source="assess",
        answered_at=answered_at,
        today=today,
    )
    conn.commit()
    return nxt


def count_introduced_today(
    conn: psycopg.Connection,
    language: str,
    today: date | None = None,
) -> int:
    """Daily new quota: training introductions only (assessment excluded)."""
    today = today or date.today()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM card_progress p
            JOIN entries e ON e.id = p.entry_id
            WHERE e.language = %s
              AND p.introduced_on = %s
              AND p.introduced_via = 'train'
            """,
            (language, today),
        )
        return int(cur.fetchone()[0])
