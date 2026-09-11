#!/usr/bin/env python3
"""Pick a training session (I2). No UI."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect
from app.repository import fetch_candidates
from app.session import SESSION_SIZE, SessionFilter, pick_cards


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=("en", "fr"))
    parser.add_argument("--textbook", action="append", default=[])
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--level", action="append", default=[])
    parser.add_argument("--size", type=int, default=SESSION_SIZE)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    flt = SessionFilter(
        language=args.language,
        textbooks=tuple(args.textbook),
        topics=tuple(args.topic),
        levels=tuple(args.level),
        size=args.size,
    )
    rng = random.Random(args.seed)
    with connect() as conn:
        pool = fetch_candidates(conn, flt)
        picked = pick_cards(pool, flt.size, rng)

    print(
        json.dumps(
            {
                "pool_size": len(pool),
                "picked": len(picked),
                "cards": [
                    {
                        "entry_id": c.entry_id,
                        "direction": c.direction,
                        "form": c.form,
                        "streak": c.streak,
                        "weight": c.weight,
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
