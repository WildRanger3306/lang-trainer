"""FSRS scheduling (train) + assessment triage (unchanged intervals).

Train uses py-fsrs with day-granularity (empty learning/relearning steps),
desired retention 90%, fuzz on. See docs/12-fsrs.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from fsrs import Card, Rating, Scheduler, State

NEW_PER_DAY_BY_LANGUAGE = {
    "en": 10,
    "fr": 20,
}
PREFERRED_DIRECTION_BY_LANGUAGE = {
    "en": "native_to_foreign",
    "fr": "foreign_to_native",
}

DESIRED_RETENTION = 0.9

# Assessment triage (not FSRS on first introduce).
ASSESS_BATCH = 40
ASSESS_KNOW_INTERVAL = 7
ASSESS_VERDICTS = ("know", "doubt", "unknown")

TRAIN_RATINGS = ("again", "hard", "good", "easy")

RATING_BY_NAME = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}

# Mid difficulty for assess-seeded cards (1..10 scale).
ASSESS_SEED_DIFFICULTY = 5.0


def new_per_day(language: str) -> int:
    try:
        return NEW_PER_DAY_BY_LANGUAGE[language]
    except KeyError as exc:
        raise ValueError("language must be en or fr") from exc


def preferred_direction(language: str) -> str:
    try:
        return PREFERRED_DIRECTION_BY_LANGUAGE[language]
    except KeyError as exc:
        raise ValueError("language must be en or fr") from exc


def make_scheduler() -> Scheduler:
    return Scheduler(
        desired_retention=DESIRED_RETENTION,
        enable_fuzzing=True,
        learning_steps=(),
        relearning_steps=(),
    )


@dataclass(frozen=True)
class ProgressState:
    due_on: date
    interval_days: float
    stability: float
    difficulty: float
    fsrs_state: int
    fsrs_step: int | None
    last_review: datetime | None
    introduced_on: date


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def due_date_from_fsrs(card: Card, today: date) -> date:
    """Map FSRS datetime due → calendar day (MVP: no intra-day queue)."""
    due_d = _as_utc(card.due).date()
    if due_d < today:
        return today
    return due_d


def interval_days_for(due_on: date, today: date) -> float:
    """Days until due; at least 1 for DB check / stats."""
    return float(max(1, (due_on - today).days))


def fsrs_card_from_state(state: ProgressState | None, *, now: datetime) -> Card:
    if state is None:
        return Card()
    last = state.last_review
    if last is None:
        last = _day_start(state.introduced_on)
    return Card(
        state=State(state.fsrs_state),
        step=state.fsrs_step,
        stability=state.stability,
        difficulty=state.difficulty,
        due=_day_start(state.due_on),
        last_review=_as_utc(last),
    )


def progress_from_fsrs_card(
    card: Card,
    *,
    today: date,
    introduced_on: date,
) -> ProgressState:
    due_on = due_date_from_fsrs(card, today)
    return ProgressState(
        due_on=due_on,
        interval_days=interval_days_for(due_on, today),
        stability=float(card.stability if card.stability is not None else 0.1),
        difficulty=float(card.difficulty if card.difficulty is not None else ASSESS_SEED_DIFFICULTY),
        fsrs_state=int(card.state),
        fsrs_step=card.step,
        last_review=_as_utc(card.last_review) if card.last_review else None,
        introduced_on=introduced_on,
    )


def apply_rating(
    state: ProgressState | None,
    rating_name: str,
    today: date,
    *,
    now: datetime | None = None,
) -> ProgressState:
    """Grade a train card with FSRS."""
    if rating_name not in RATING_BY_NAME:
        raise ValueError(f"unknown rating: {rating_name}")
    now = _as_utc(now or datetime.now(timezone.utc))
    sched = make_scheduler()
    card = fsrs_card_from_state(state, now=now)
    out, _log = sched.review_card(card, RATING_BY_NAME[rating_name], review_datetime=now)
    introduced = state.introduced_on if state is not None else today
    return progress_from_fsrs_card(out, today=today, introduced_on=introduced)


def apply_assessment(verdict: str, today: date) -> ProgressState:
    """Triage brand-new card outside FSRS; seeds Review state for later train."""
    if verdict not in ASSESS_VERDICTS:
        raise ValueError(f"unknown assessment verdict: {verdict}")
    if verdict == "know":
        interval = float(ASSESS_KNOW_INTERVAL)
        due = today + timedelta(days=ASSESS_KNOW_INTERVAL)
    else:
        interval = 1.0
        due = today + timedelta(days=1)
    return ProgressState(
        due_on=due,
        interval_days=interval,
        stability=max(0.1, interval),
        difficulty=ASSESS_SEED_DIFFICULTY,
        fsrs_state=int(State.Review),
        fsrs_step=None,
        last_review=_day_start(today),
        introduced_on=today,
    )


def convert_legacy_progress(
    *,
    due_on: date,
    interval_days: float,
    ease: float,
    introduced_on: date,
) -> ProgressState:
    """Rough interval/ease → FSRS fields (docs/12-fsrs.md §2)."""
    stability = max(0.1, float(interval_days))
    # Higher ease → easier card → lower difficulty (1..10).
    difficulty = min(10.0, max(1.0, 11.0 - float(ease) * 2.0))
    last = _day_start(due_on - timedelta(days=max(0, int(interval_days))))
    if last.date() > introduced_on:
        # keep
        pass
    else:
        last = _day_start(introduced_on)
    return ProgressState(
        due_on=due_on,
        interval_days=max(1.0, float(interval_days)),
        stability=stability,
        difficulty=difficulty,
        fsrs_state=int(State.Review),
        fsrs_step=None,
        last_review=last,
        introduced_on=introduced_on,
    )
