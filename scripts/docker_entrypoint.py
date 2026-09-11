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
SEED_DIRS = [
    ROOT / "docs" / "words" / "json" / "starlight_6",
    ROOT / "docs" / "words" / "json" / "starlight_7",
    ROOT / "docs" / "words" / "json" / "loiseau_blue_5",
    ROOT / "docs" / "words" / "json" / "loiseau_blue_6",
]


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
        # Anki progress replaces streak-based table.
        conn.execute(
            """
            DO $$ BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'card_progress' AND column_name = 'streak'
              ) THEN
                DROP TABLE card_progress;
              END IF;
            END $$
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_progress (
              entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
              direction card_direction NOT NULL,
              due_on DATE NOT NULL,
              interval_days DOUBLE PRECISION NOT NULL DEFAULT 1
                CHECK (interval_days >= 1),
              ease DOUBLE PRECISION NOT NULL DEFAULT 2.5
                CHECK (ease >= 1.3),
              introduced_on DATE NOT NULL,
              PRIMARY KEY (entry_id, direction)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_card_progress_due_on ON card_progress (due_on)"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_progress_introduced_on
            ON card_progress (introduced_on)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_reviews (
              id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
              entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
              direction card_direction NOT NULL,
              answered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              answered_on DATE NOT NULL DEFAULT CURRENT_DATE,
              remembered BOOLEAN NOT NULL,
              was_new BOOLEAN NOT NULL,
              interval_before DOUBLE PRECISION NOT NULL DEFAULT 0
                CHECK (interval_before >= 0),
              interval_after DOUBLE PRECISION NOT NULL
                CHECK (interval_after >= 0)
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE card_reviews
              ADD COLUMN IF NOT EXISTS answered_on DATE NOT NULL DEFAULT CURRENT_DATE
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_reviews_answered_at
            ON card_reviews (answered_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_reviews_answered_on
            ON card_reviews (answered_on)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_card_reviews_entry
            ON card_reviews (entry_id, direction)
            """
        )
        conn.execute(
            """
            ALTER TABLE card_progress
              ADD COLUMN IF NOT EXISTS introduced_via TEXT NOT NULL DEFAULT 'train'
            """
        )
        conn.execute(
            """
            ALTER TABLE card_reviews
              ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'train'
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_entries_lang_form_pos
            ON entries (language, lower(form), part_of_speech)
            """
        )
        conn.commit()
    migrate_users()


def migrate_users() -> None:
    """Create users table and attach user_id to progress/reviews."""
    from app.users import assign_orphan_progress, create_user

    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
              login TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              display_name TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE card_progress
              ADD COLUMN IF NOT EXISTS user_id BIGINT
            """
        )
        conn.execute(
            """
            ALTER TABLE card_reviews
              ADD COLUMN IF NOT EXISTS user_id BIGINT
            """
        )
        conn.commit()

        # Ensure default user exists (personal deploy).
        row = conn.execute(
            "SELECT id FROM users WHERE login = %s", ("serafima",)
        ).fetchone()
        if row is None:
            user = create_user(conn, "serafima", "serafima123")
            user_id = user.id
            print(f"created default user serafima id={user_id}", flush=True)
        else:
            user_id = int(row[0])

        prog, rev = assign_orphan_progress(conn, user_id)
        if prog or rev:
            print(
                f"claimed orphan progress={prog} reviews={rev} → user {user_id}",
                flush=True,
            )

        # Make user_id NOT NULL and fix PK if still old shape.
        pk = conn.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'card_progress'::regclass AND i.indisprimary
            ORDER BY a.attnum
            """
        ).fetchall()
        pk_cols = [r[0] for r in pk]
        if pk_cols == ["entry_id", "direction"] or (
            "user_id" not in pk_cols and pk_cols
        ):
            # Drop rows that somehow still lack user_id (should be none).
            conn.execute("DELETE FROM card_progress WHERE user_id IS NULL")
            conn.execute("DELETE FROM card_reviews WHERE user_id IS NULL")
            conn.execute(
                """
                ALTER TABLE card_progress
                  DROP CONSTRAINT IF EXISTS card_progress_pkey
                """
            )
            conn.execute(
                """
                ALTER TABLE card_progress
                  ALTER COLUMN user_id SET NOT NULL
                """
            )
            conn.execute(
                """
                ALTER TABLE card_progress
                  ADD PRIMARY KEY (user_id, entry_id, direction)
                """
            )
            conn.execute(
                """
                DO $$ BEGIN
                  ALTER TABLE card_progress
                    ADD CONSTRAINT card_progress_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$
                """
            )
            conn.commit()
            print("card_progress PK → (user_id, entry_id, direction)", flush=True)
        else:
            # Still allow NOT NULL if all rows filled.
            nulls = conn.execute(
                "SELECT count(*) FROM card_progress WHERE user_id IS NULL"
            ).fetchone()[0]
            if nulls == 0:
                conn.execute(
                    """
                    ALTER TABLE card_progress
                      ALTER COLUMN user_id SET NOT NULL
                    """
                )
                conn.commit()

        # Reviews: NOT NULL when empty nulls
        null_rev = conn.execute(
            "SELECT count(*) FROM card_reviews WHERE user_id IS NULL"
        ).fetchone()[0]
        if null_rev == 0:
            conn.execute(
                """
                ALTER TABLE card_reviews
                  ALTER COLUMN user_id SET NOT NULL
                """
            )
            conn.execute(
                """
                DO $$ BEGIN
                  ALTER TABLE card_reviews
                    ADD CONSTRAINT card_reviews_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_card_reviews_user
                ON card_reviews (user_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_card_progress_user
                ON card_progress (user_id)
                """
            )
            conn.commit()


def seed_if_empty() -> None:
    with connect() as conn:
        count = conn.execute("SELECT count(*) FROM entries").fetchone()[0]
    if count:
        print(f"entries already present: {count}", flush=True)
        return
    first = True
    for seed_dir in SEED_DIRS:
        if not seed_dir.is_dir():
            print(f"skip missing seed {seed_dir}", flush=True)
            continue
        print(f"loading {seed_dir}", flush=True)
        cmd = [sys.executable, str(ROOT / "scripts" / "load_entries.py")]
        if not first:
            cmd.append("--append")
        cmd.append(str(seed_dir))
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        first = False


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
