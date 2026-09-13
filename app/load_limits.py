"""Per-user adaptive new_per_day (§011 / docs/11-adaptive-load.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from app.scheduler import NEW_PER_DAY_BY_LANGUAGE

# min, default, max
LOAD_BOUNDS: dict[str, tuple[int, int, int]] = {
    "en": (5, 10, 20),
    "fr": (10, 20, 30),
}
LOAD_STEP = 5
HYSTERESIS_DAYS = 3


def default_new_per_day(language: str) -> int:
    try:
        return NEW_PER_DAY_BY_LANGUAGE[language]
    except KeyError as exc:
        raise ValueError("language must be en or fr") from exc


def load_bounds(language: str) -> tuple[int, int, int]:
    try:
        return LOAD_BOUNDS[language]
    except KeyError as exc:
        raise ValueError("language must be en or fr") from exc


def clamp_new_per_day(language: str, value: int) -> int:
    lo, _default, hi = load_bounds(language)
    return max(lo, min(hi, int(value)))


@dataclass(frozen=True)
class LoadLimitRow:
    new_per_day: int
    base_new_per_day: int
    updated_via: str
    last_change_on: date | None


@dataclass(frozen=True)
class AdaptResult:
    new_per_day: int
    changed: bool
    note: str | None


def ensure_load_limit(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
) -> LoadLimitRow:
    default = default_new_per_day(language)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO user_load_limits (
              user_id, language, new_per_day, base_new_per_day, updated_via
            ) VALUES (%s, %s, %s, %s, 'default')
            ON CONFLICT (user_id, language) DO NOTHING
            """,
            (user_id, language, default, default),
        )
        cur.execute(
            """
            SELECT new_per_day, base_new_per_day, updated_via, last_change_on
            FROM user_load_limits
            WHERE user_id = %s AND language = %s
            """,
            (user_id, language),
        )
        row = cur.fetchone()
    assert row is not None
    return LoadLimitRow(
        new_per_day=int(row["new_per_day"]),
        base_new_per_day=int(row["base_new_per_day"]),
        updated_via=str(row["updated_via"]),
        last_change_on=row["last_change_on"],
    )


def get_new_per_day(conn: psycopg.Connection, user_id: int, language: str) -> int:
    return ensure_load_limit(conn, user_id, language).new_per_day


def record_advice_day(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    day: date,
    status: str,
    suggested: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO load_advice_days (user_id, language, day, status, suggested)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, language, day)
            DO UPDATE SET status = EXCLUDED.status, suggested = EXCLUDED.suggested
            """,
            (user_id, language, day, status, suggested),
        )


def _statuses_for_hysteresis(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
) -> list[str] | None:
    """Statuses for today and the previous HYSTERESIS_DAYS-1 calendar days."""
    days = [today - timedelta(days=i) for i in range(HYSTERESIS_DAYS)]
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT day, status
            FROM load_advice_days
            WHERE user_id = %s AND language = %s AND day = ANY(%s)
            """,
            (user_id, language, days),
        )
        by_day = {row["day"]: str(row["status"]) for row in cur.fetchall()}
    out: list[str] = []
    for d in days:
        if d not in by_day:
            return None
        out.append(by_day[d])
    return out


def advice_streak(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    *,
    lookback: int = 14,
) -> tuple[str | None, int]:
    """Consecutive calendar days ending at today with the same lower/raise status.

    Returns (status, days). If today is missing or is keep, (None, 0).
    """
    days = [today - timedelta(days=i) for i in range(lookback)]
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT day, status
            FROM load_advice_days
            WHERE user_id = %s AND language = %s AND day = ANY(%s)
            """,
            (user_id, language, days),
        )
        by_day = {row["day"]: str(row["status"]) for row in cur.fetchall()}
    today_status = by_day.get(today)
    if today_status not in ("lower", "raise"):
        return None, 0
    n = 0
    for d in days:
        if by_day.get(d) != today_status:
            break
        n += 1
    return today_status, n


def fetch_advice_series(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    days: int = 30,
) -> tuple[tuple[date, str | None], ...]:
    since = today - timedelta(days=days - 1)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT day, status
            FROM load_advice_days
            WHERE user_id = %s AND language = %s
              AND day >= %s AND day <= %s
            """,
            (user_id, language, since, today),
        )
        by_day = {row["day"]: str(row["status"]) for row in cur.fetchall()}
    out: list[tuple[date, str | None]] = []
    for i in range(days):
        day = since + timedelta(days=i)
        out.append((day, by_day.get(day)))
    return tuple(out)


def try_apply_hysteresis(
    conn: psycopg.Connection,
    user_id: int,
    language: str,
    today: date,
    *,
    current: int,
    today_suggested: int,
) -> AdaptResult:
    """Apply ±5 if same lower/raise status for 3 calendar days; at most once per day."""
    row = ensure_load_limit(conn, user_id, language)
    if row.last_change_on == today:
        return AdaptResult(new_per_day=row.new_per_day, changed=False, note=None)

    statuses = _statuses_for_hysteresis(conn, user_id, language, today)
    if statuses is None:
        return AdaptResult(new_per_day=current, changed=False, note=None)

    streak = statuses[0]
    if streak not in ("lower", "raise"):
        return AdaptResult(new_per_day=current, changed=False, note=None)
    if any(s != streak for s in statuses):
        return AdaptResult(new_per_day=current, changed=False, note=None)

    target = clamp_new_per_day(language, today_suggested)
    if target == current:
        return AdaptResult(new_per_day=current, changed=False, note=None)

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE user_load_limits SET
              new_per_day = %s,
              updated_at = %s,
              updated_via = 'auto',
              last_change_on = %s
            WHERE user_id = %s AND language = %s
            """,
            (target, datetime.now(timezone.utc), today, user_id, language),
        )
    note = (
        f"авто: {language.upper()} {current}→{target} "
        f"({HYSTERESIS_DAYS} дн. подряд «{streak}»)"
    )
    return AdaptResult(new_per_day=target, changed=True, note=note)
