from __future__ import annotations

import random
from datetime import date

from app.progress import count_introduced_today
from app.repository import fetch_due_candidates, fetch_new_candidates
from app.scheduler import ASSESS_BATCH, new_per_day, preferred_direction
from app.session import SessionFilter, build_assessment_queue, build_queue, new_limit_for_day


def build_session_cards(
    conn,
    flt: SessionFilter,
    user_id: int,
    rng: random.Random,
    today: date | None = None,
):
    today = today or date.today()
    due = fetch_due_candidates(conn, flt, user_id, today)
    new = fetch_new_candidates(conn, flt, user_id)
    introduced = count_introduced_today(conn, user_id, flt.language, today)
    limit = new_limit_for_day(introduced, new_per_day(flt.language))
    preferred = preferred_direction(flt.language)
    picked = build_queue(due, new, limit, rng, preferred=preferred)
    return picked, len(due), min(limit, len(new))


def build_assessment_cards(
    conn,
    flt: SessionFilter,
    user_id: int,
    rng: random.Random,
    batch: int = ASSESS_BATCH,
):
    """Unassessed cards with language direction bias."""
    new = fetch_new_candidates(conn, flt, user_id)
    preferred = preferred_direction(flt.language)
    picked = build_assessment_queue(new, batch, rng, preferred=preferred)
    return picked, len(new)
