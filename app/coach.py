"""Home coach: short template messages for the main page (docs/13-home-coach.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg

from app.stats import LoadAdvice, LoadStats, PerformanceStats
from app.users import User

# «Давно не виделись» только если пауза не короче этого.
ABSENCE_DAYS = 3


@dataclass(frozen=True)
class CoachMessage:
    tone: str  # calm | push | boost | soft | neutral | welcome | start
    text: str


def days_since_activity(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date | None = None,
) -> int | None:
    """Days since last train review / last_review / introduced_on for this language.

    None = never touched this language.
    """
    today = today or date.today()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT GREATEST(
              (SELECT max(r.answered_on)
               FROM card_reviews r
               JOIN entries e ON e.id = r.entry_id
               WHERE r.user_id = %s AND e.language = %s AND r.source = 'train'),
              (SELECT max((p.last_review AT TIME ZONE 'UTC')::date)
               FROM card_progress p
               JOIN entries e ON e.id = p.entry_id
               WHERE p.user_id = %s AND e.language = %s),
              (SELECT max(p.introduced_on)
               FROM card_progress p
               JOIN entries e ON e.id = p.entry_id
               WHERE p.user_id = %s AND e.language = %s)
            )
            """,
            (user_id, language, user_id, language, user_id, language),
        )
        row = cur.fetchone()
    last = row[0] if row else None
    if last is None:
        return None
    return max(0, (today - last).days)


def coach_message(
    user: User,
    *,
    language: str,
    load: LoadStats,
    advice: LoadAdvice,
    performance: PerformanceStats,
    days_since_active: int | None,
    adapt_note: str | None = None,
) -> CoachMessage:
    name = user.label
    due = load.due_today
    new_left = max(0, load.new_per_day - load.introduced_today)
    lang = "английскому" if language == "en" else "французскому"

    if adapt_note:
        return CoachMessage(
            tone="soft",
            text=(
                f"{name}, лимит новых только что подстроился. "
                f"Сегодня по {lang}: {due} due и ещё {new_left} новых."
            ),
        )

    # Never trained this language → start, not «давно».
    if days_since_active is None:
        return CoachMessage(
            tone="start",
            text=(
                f"{name}, по {lang} ещё не начинали — "
                f"сегодня можно взять due {due} и до {new_left} новых."
            ),
        )

    # Real pause of several calendar days.
    if days_since_active >= ABSENCE_DAYS:
        return CoachMessage(
            tone="welcome",
            text=(
                f"{name}, давно не виделись ({days_since_active} дн.). "
                f"Начни с due — сегодня {due} повторов и до {new_left} новых."
            ),
        )

    if performance.reviews_7 < 20:
        return CoachMessage(
            tone="neutral",
            text=(
                f"{name}, сегодня по {lang}: {due} повторов и до {new_left} новых. "
                f"Удачной сессии!"
            ),
        )

    if advice.status == "lower":
        return CoachMessage(
            tone="soft",
            text=(
                f"{name}, неделька была плотная — ты молодец. "
                f"Сегодня лучше добить due ({due}), новых осталось {new_left}."
            ),
        )

    if advice.status == "raise":
        return CoachMessage(
            tone="boost",
            text=(
                f"{name}, повторы стабильные — можно чуть прибавить. "
                f"Сегодня due мало ({due}), новых до {new_left}."
            ),
        )

    if due <= 15:
        return CoachMessage(
            tone="calm",
            text=(
                f"{name}, сегодня спокойный день: {due} повторов "
                f"и ещё {new_left} новых. Ты отлично справляешься."
            ),
        )

    return CoachMessage(
        tone="push",
        text=(
            f"{name}, due поднажало ({due}) — ты справишься. "
            f"Новых сегодня до {new_left}."
        ),
    )
