from __future__ import annotations

import random
from datetime import date

from app.progress import count_introduced_today
from app.repository import fetch_due_candidates, fetch_new_candidates
from app.scheduler import NEW_PER_DAY
from app.session import SessionFilter, build_queue, new_limit_for_day


def build_session_cards(
    conn,
    flt: SessionFilter,
    rng: random.Random,
    today: date | None = None,
):
    today = today or date.today()
    due = fetch_due_candidates(conn, flt, today)
    new = fetch_new_candidates(conn, flt)
    introduced = count_introduced_today(conn, flt.language, today)
    limit = new_limit_for_day(introduced, NEW_PER_DAY)
    picked = build_queue(due, new, limit, rng)
    return picked, len(due), min(limit, len(new))
