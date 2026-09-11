#!/usr/bin/env python3
"""Wait for Postgres, migrate, seed if empty, then start uvicorn."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import psycopg

from app.db import connect, database_url

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "docs" / "words" / "json" / "starlight_6"


def wait_for_db() -> None:
    url = database_url()
    last_error: Exception | None = None
    for _ in range(40):
        try:
            with psycopg.connect(url) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 — retry until ready
            last_error = exc
            time.sleep(0.5)
    raise SystemExit(f"database not ready: {last_error}")


def migrate() -> None:
    with connect() as conn:
        conn.execute(
            """
            DO $$ BEGIN
              CREATE TYPE card_direction AS ENUM (
                'foreign_to_native',
                'native_to_foreign'
              );
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_progress (
              entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
              direction card_direction NOT NULL,
              streak INTEGER NOT NULL DEFAULT 0 CHECK (streak >= 0),
              PRIMARY KEY (entry_id, direction)
            )
            """
        )
        conn.execute(
            """
            DO $$ BEGIN
              CREATE TYPE noun_gender AS ENUM ('m', 'f');
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$
            """
        )
        conn.execute(
            "ALTER TABLE entries ADD COLUMN IF NOT EXISTS gender noun_gender"
        )
        conn.commit()


def seed_if_empty() -> None:
    with connect() as conn:
        count = conn.execute("SELECT count(*) FROM entries").fetchone()[0]
    if count:
        print(f"entries already present: {count}", flush=True)
        return
    print(f"loading {SEED_DIR}", flush=True)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "load_entries.py"), str(SEED_DIR)],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    wait_for_db()
    migrate()
    seed_if_empty()
    raise SystemExit(
        subprocess.run(
            ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        ).returncode
    )


if __name__ == "__main__":
    main()
