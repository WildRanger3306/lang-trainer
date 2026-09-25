from __future__ import annotations

from datetime import date, datetime, timezone

import psycopg
from psycopg.rows import dict_row

from app.scheduler import (
    ProgressState,
    TRAIN_RATINGS,
    apply_assessment,
    apply_rating,
)
from app.session import CardCandidate


def _load_state(
    conn: psycopg.Connection,
    user_id: int,
    entry_id: int,
    direction: str,
) -> ProgressState | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT due_on, interval_days, stability, difficulty,
                   fsrs_state, fsrs_step, last_review, introduced_on
            FROM card_progress
            WHERE user_id = %s AND entry_id = %s AND direction = %s
            """,
            (user_id, entry_id, direction),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return ProgressState(
        due_on=row["due_on"],
        interval_days=float(row["interval_days"]),
        stability=float(row["stability"]),
        difficulty=float(row["difficulty"]),
        fsrs_state=int(row["fsrs_state"]),
        fsrs_step=row["fsrs_step"],
        last_review=row["last_review"],
        introduced_on=row["introduced_on"],
    )


def _upsert_progress(
    conn: psycopg.Connection,
    user_id: int,
    card: CardCandidate,
    nxt: ProgressState,
    *,
    introduced_via: str,
    remembered: bool,
    was_new: bool,
    interval_before: float,
    source: str,
    answered_at: datetime,
    today: date,
    rating: int | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO card_progress (
              user_id, entry_id, direction, due_on, interval_days,
              stability, difficulty, fsrs_state, fsrs_step, last_review,
              introduced_on, introduced_via
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, entry_id, direction)
            DO UPDATE SET
              due_on = EXCLUDED.due_on,
              interval_days = EXCLUDED.interval_days,
              stability = EXCLUDED.stability,
              difficulty = EXCLUDED.difficulty,
              fsrs_state = EXCLUDED.fsrs_state,
              fsrs_step = EXCLUDED.fsrs_step,
              last_review = EXCLUDED.last_review
            """,
            (
                user_id,
                card.entry_id,
                card.direction,
                nxt.due_on,
                nxt.interval_days,
                nxt.stability,
                nxt.difficulty,
                nxt.fsrs_state,
                nxt.fsrs_step,
                nxt.last_review,
                nxt.introduced_on,
                introduced_via,
            ),
        )
        cur.execute(
            """
            INSERT INTO card_reviews (
              user_id, entry_id, direction, answered_at, answered_on, remembered,
              was_new, interval_before, interval_after, source, rating
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                card.entry_id,
                card.direction,
                answered_at,
                today,
                remembered,
                was_new,
                interval_before,
                nxt.interval_days,
                source,
                rating,
            ),
        )


def save_grade(
    conn: psycopg.Connection,
    user_id: int,
    card: CardCandidate,
    rating_name: str,
    today: date | None = None,
    answered_at: datetime | None = None,
    *,
    source: str = "train",
) -> ProgressState:
    """FSRS grade. `source` is train or verbs (§016: verbs mode stays out of
    the new-card quota, adaptive load and train stats)."""
    if rating_name not in TRAIN_RATINGS:
        raise ValueError(f"unknown rating: {rating_name}")
    today = today or date.today()
    answered_at = answered_at or datetime.now(timezone.utc)
    current = _load_state(conn, user_id, card.entry_id, card.direction)
    was_new = current is None
    interval_before = 0.0 if current is None else float(current.interval_days)
    nxt = apply_rating(current, rating_name, today, now=answered_at)
    rating_int = {"again": 1, "hard": 2, "good": 3, "easy": 4}[rating_name]
    _upsert_progress(
        conn,
        user_id,
        card,
        nxt,
        introduced_via=source,
        remembered=rating_name != "again",
        was_new=was_new,
        interval_before=interval_before,
        source=source,
        answered_at=answered_at,
        today=today,
        rating=rating_int,
    )
    conn.commit()
    return nxt


def save_assessment(
    conn: psycopg.Connection,
    user_id: int,
    card: CardCandidate,
    verdict: str,
    today: date | None = None,
    answered_at: datetime | None = None,
) -> ProgressState:
    """Introduce a new card via assessment. Does not count toward daily new quota."""
    today = today or date.today()
    answered_at = answered_at or datetime.now(timezone.utc)
    current = _load_state(conn, user_id, card.entry_id, card.direction)
    if current is not None:
        raise ValueError("assessment only applies to cards without progress")
    nxt = apply_assessment(verdict, today)
    remembered = verdict != "unknown"
    _upsert_progress(
        conn,
        user_id,
        card,
        nxt,
        introduced_via="assess",
        remembered=remembered,
        was_new=True,
        interval_before=0.0,
        source="assess",
        answered_at=answered_at,
        today=today,
        rating=None,
    )
    conn.commit()
    return nxt


def count_introduced_today(
    conn: psycopg.Connection,
    user_id: int,
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
            WHERE p.user_id = %s
              AND e.language = %s
              AND p.introduced_on = %s
              AND p.introduced_via = 'train'
            """,
            (user_id, language, today),
        )
        return int(cur.fetchone()[0])
