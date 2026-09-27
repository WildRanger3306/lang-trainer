#!/usr/bin/env python3
"""Grant or revoke the admin role for an existing user."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connect
from app.users import set_admin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--admin", action="store_true", help="grant the admin role")
    group.add_argument("--no-admin", action="store_true", help="revoke the admin role")
    args = parser.parse_args()

    with connect() as conn:
        set_admin(conn, args.login, args.admin)
    print(f"{args.login}: is_admin = {args.admin}")


if __name__ == "__main__":
    main()
