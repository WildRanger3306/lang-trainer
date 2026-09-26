#!/usr/bin/env python3
"""Disposable test database plus a local app on it. Never touches the live database.

  python scripts/test_db.py setup [--reset]   create <db>_test, migrate, seed, add test users
  python scripts/test_db.py run [--port 8001] local app on the test database
  python scripts/test_db.py test              all tests, including the DB ones
  python scripts/test_db.py env               show the test database URL (password hidden)

The test database lives on the same Postgres server as the live one, named
<POSTGRES_DB>_test. Test users: serafima / serafima123, pavel / pavel123.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

TEST_USERS = (
    ("serafima", "Серафима", "serafima123"),
    ("pavel", "Павел", "pavel123"),
)


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def test_url() -> str:
    from app.db import DEFAULT_URL

    parts = urlsplit(os.environ.get("DATABASE_URL", DEFAULT_URL))
    name = parts.path.lstrip("/")
    if not name.endswith("_test"):
        name += "_test"
    return urlunsplit(parts._replace(path=f"/{name}"))


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def admin_url(url: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path="/postgres"))


def masked(url: str) -> str:
    parts = urlsplit(url)
    if parts.password:
        parts = parts._replace(netloc=parts.netloc.replace(f":{parts.password}@", ":***@"))
    return urlunsplit(parts)


def create_database(url: str, reset: bool) -> None:
    name = database_name(url)
    assert name.endswith("_test"), "refusing to touch a non-test database"
    with psycopg.connect(admin_url(url), autocommit=True) as admin:
        if reset:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if not exists:
            admin.execute(f'CREATE DATABASE "{name}"')
            print(f"created database {name}", flush=True)
    with psycopg.connect(url) as conn:
        if conn.execute("SELECT to_regclass('public.entries')").fetchone()[0] is None:
            conn.execute((ROOT / "db" / "schema.sql").read_text())
            conn.commit()
            print("applied db/schema.sql", flush=True)


def setup(reset: bool) -> None:
    url = test_url()
    create_database(url, reset)
    os.environ["DATABASE_URL"] = url
    assert database_name(os.environ["DATABASE_URL"]).endswith("_test")

    import docker_entrypoint
    from app.db import connect
    from app.users import create_user, get_user_by_login

    docker_entrypoint.migrate()
    docker_entrypoint.seed_if_empty()
    docker_entrypoint.seed_irregular_if_missing()
    with connect() as conn:
        for login, display, password in TEST_USERS:
            if get_user_by_login(conn, login) is None:
                create_user(conn, login, password, display_name=display)
                print(f"created test user {login}", flush=True)
    print(f"test database ready: {masked(url)}", flush=True)


def child_env(url: str, **extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update({"DATABASE_URL": url, "PYTHONPATH": str(ROOT), **extra})
    return env


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    setup_cmd = sub.add_parser("setup")
    setup_cmd.add_argument("--reset", action="store_true", help="drop and recreate the test database")
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--port", type=int, default=8001)
    run_cmd.add_argument("--host", default="127.0.0.1")
    sub.add_parser("test")
    sub.add_parser("env")
    args = parser.parse_args()

    url = test_url()
    if args.command == "setup":
        setup(args.reset)
    elif args.command == "env":
        print(masked(url))
    elif args.command == "run":
        print(f"local app on the test database: http://{args.host}:{args.port}  (logins: serafima / serafima123, pavel / pavel123)", flush=True)
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)],
            child_env(url),
        )
    elif args.command == "test":
        code = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT,
            env=child_env(url, RUN_DB_TESTS="1"),
        ).returncode
        raise SystemExit(code)


if __name__ == "__main__":
    main()
