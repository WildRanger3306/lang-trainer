from __future__ import annotations

import psycopg

from app.cards import next_streak
from app.session import CardCandidate


def save_grade(conn: psycopg.Connection, card: CardCandidate, remembered: bool) -> int:
    streak = next_streak(card.streak, remembered)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO card_progress (entry_id, direction, streak)
            VALUES (%s, %s, %s)
            ON CONFLICT (entry_id, direction)
            DO UPDATE SET streak = EXCLUDED.streak
            """,
            (card.entry_id, card.direction, streak),
        )
    conn.commit()
    return streak
