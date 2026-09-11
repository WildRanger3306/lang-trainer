#!/usr/bin/env python3
"""Pick a training session queue (due + new). No UI."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect
from app.progress import count_introduced_today
from app.queue import build_session_cards
from app.scheduler import new_per_day, preferred_direction
from app.session import SessionFilter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=("en", "fr"))
    parser.add_argument("--user", required=True, help="login of the learner")
    parser.add_argument("--textbook", action="append", default=[])
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--level", action="append", default=[])
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    flt = SessionFilter(
        language=args.language,
        textbooks=tuple(args.textbook),
        topics=tuple(args.topic),
        levels=tuple(args.level),
    )
    rng = random.Random(args.seed)
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE login = %s", (args.user,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"user not found: {args.user}")
        user_id = int(row[0])
        picked, due_n, new_n = build_session_cards(conn, flt, user_id, rng)
        introduced = count_introduced_today(conn, user_id, flt.language)

    print(
        json.dumps(
            {
                "user": args.user,
                "due_count": due_n,
                "new_in_session": new_n,
                "introduced_today": introduced,
                "new_per_day": new_per_day(flt.language),
                "preferred_direction": preferred_direction(flt.language),
                "picked": len(picked),
                "cards": [
                    {
                        "entry_id": c.entry_id,
                        "direction": c.direction,
                        "form": c.form,
                        "is_new": c.is_new,
                        "due_on": c.due_on.isoformat() if c.due_on else None,
                        "interval_days": c.interval_days,
                        "ease": c.ease,
                    }
                    for c in picked
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
