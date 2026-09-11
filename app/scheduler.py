"""Simplified Anki / SM-2 scheduling (Again / Good only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

NEW_PER_DAY = 15
DEFAULT_EASE = 2.5
MIN_EASE = 1.3
EASE_PENALTY = 0.2

# Knowledge assessment (triage of already-known vocab).
ASSESS_BATCH = 40
ASSESS_KNOW_INTERVAL = 7  # false "know" resurfaces in a week, not three
ASSESS_VERDICTS = ("know", "doubt", "unknown")


@dataclass(frozen=True)
class ScheduleState:
    due_on: date
    interval_days: float
    ease: float
    introduced_on: date


def next_interval(interval_days: float, ease: float) -> float:
    """1 → 3 → 8 → … via round(interval × ease)."""
    if interval_days < 1:
        return 1.0
    return float(max(1, int(interval_days * ease + 0.5)))


def apply_grade(
    state: ScheduleState | None,
    remembered: bool,
    today: date,
) -> ScheduleState:
    """Grade a card. None state = brand-new (never introduced)."""
    if state is None:
        return ScheduleState(
            due_on=today + timedelta(days=1),
            interval_days=1.0,
            ease=DEFAULT_EASE,
            introduced_on=today,
        )
    if remembered:
        interval = next_interval(state.interval_days, state.ease)
        return ScheduleState(
            due_on=today + timedelta(days=int(interval)),
            interval_days=interval,
            ease=state.ease,
            introduced_on=state.introduced_on,
        )
    return ScheduleState(
        due_on=today + timedelta(days=1),
        interval_days=1.0,
        ease=max(MIN_EASE, state.ease - EASE_PENALTY),
        introduced_on=state.introduced_on,
    )


def apply_assessment(verdict: str, today: date) -> ScheduleState:
    """Triage a brand-new card outside the daily new quota.

    know → long interval (not in tomorrow's due pile).
    doubt / unknown → due tomorrow as interval 1 (priority without burning new quota).
    """
    if verdict not in ASSESS_VERDICTS:
        raise ValueError(f"unknown assessment verdict: {verdict}")
    if verdict == "know":
        return ScheduleState(
            due_on=today + timedelta(days=ASSESS_KNOW_INTERVAL),
            interval_days=float(ASSESS_KNOW_INTERVAL),
            ease=DEFAULT_EASE,
            introduced_on=today,
        )
    return ScheduleState(
        due_on=today + timedelta(days=1),
        interval_days=1.0,
        ease=DEFAULT_EASE,
        introduced_on=today,
    )
