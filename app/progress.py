from __future__ import annotations

from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.scheduler import ScheduleState, apply_grade
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


def save_grade(
    conn: psycopg.Connection,
    card: CardCandidate,
    remembered: bool,
    today: date | None = None,
) -> ScheduleState:
    today = today or date.today()
    current = _load_state(conn, card.entry_id, card.direction)
    nxt = apply_grade(current, remembered, today)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO card_progress (
              entry_id, direction, due_on, interval_days, ease, introduced_on
            ) VALUES (%s, %s, %s, %s, %s, %s)
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
            ),
        )
    conn.commit()
    return nxt


def count_introduced_today(
    conn: psycopg.Connection,
    language: str,
    today: date | None = None,
) -> int:
    today = today or date.today()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM card_progress p
            JOIN entries e ON e.id = p.entry_id
            WHERE e.language = %s AND p.introduced_on = %s
            """,
            (language, today),
        )
        return int(cur.fetchone()[0])
