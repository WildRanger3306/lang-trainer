#!/usr/bin/env python3
"""Create a user or set password. Optionally attach orphan progress."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect
from app.users import assign_orphan_progress, create_user, set_password, validate_login


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default=None)
    parser.add_argument(
        "--set-password",
        action="store_true",
        help="update password for existing user instead of creating",
    )
    parser.add_argument(
        "--claim-orphans",
        action="store_true",
        help="assign card_progress/reviews with NULL user_id to this user",
    )
    args = parser.parse_args()
    login = validate_login(args.login)

    with connect() as conn:
        if args.set_password:
            set_password(conn, login, args.password)
            user_id = conn.execute(
                "SELECT id FROM users WHERE login = %s", (login,)
            ).fetchone()[0]
            print(f"password updated for {login} (id={user_id})")
        else:
            user = create_user(
                conn, login, args.password, display_name=args.display_name
            )
            user_id = user.id
            print(f"created user {user.login} id={user.id}")

        if args.claim_orphans:
            prog, rev = assign_orphan_progress(conn, int(user_id))
            print(f"claimed orphans: progress={prog} reviews={rev}")


if __name__ == "__main__":
    main()
