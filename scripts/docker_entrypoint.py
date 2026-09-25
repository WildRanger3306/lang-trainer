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
    ROOT / "docs" / "words" / "json" / "starlight_5",
    ROOT / "docs" / "words" / "json" / "starlight_6",
    ROOT / "docs" / "words" / "json" / "starlight_7",
    ROOT / "docs" / "words" / "json" / "loiseau_blue_5",
    ROOT / "docs" / "words" / "json" / "loiseau_blue_6",
    ROOT / "docs" / "words" / "json" / "fr_trainer",
]
IRREGULAR_EN = ROOT / "docs" / "words" / "irregular" / "en.json"


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
        migrate_user_filters()
        migrate_fsrs()
        migrate_load_limits()
        migrate_phrasal_verb_pos()
        migrate_verb_forms()
        seed_display_names()


KNOWN_DISPLAY_NAMES = {
    "serafima": "Серафима",
    "pavel": "Павел",
}


def migrate_phrasal_verb_pos() -> None:
    """Add phrasal_verb enum and recode entries with textbook code phr v."""
    with connect() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'part_of_speech' AND e.enumlabel = 'phrasal_verb'
            """
        ).fetchone()
        if not exists:
            # ADD VALUE cannot run inside a transaction block on older PG;
            # commit first, then add, then update in a new connection scope.
            conn.commit()
            conn.execute("ALTER TYPE part_of_speech ADD VALUE 'phrasal_verb'")
            conn.commit()
            print("part_of_speech enum +phrasal_verb", flush=True)
        updated = conn.execute(
            """
            UPDATE entries
            SET part_of_speech = 'phrasal_verb'
            WHERE part_of_speech_code = 'phr v'
              AND part_of_speech IS DISTINCT FROM 'phrasal_verb'
            """
        )
        conn.commit()
        print(
            f"phrasal_verb POS recode: {updated.rowcount} rows",
            flush=True,
        )


def migrate_verb_forms() -> None:
    """Irregular verb forms table and the `forms` card direction (§015)."""
    with connect() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'card_direction' AND e.enumlabel = 'forms'
            """
        ).fetchone()
        if not exists:
            conn.commit()
            conn.execute("ALTER TYPE card_direction ADD VALUE 'forms'")
            conn.commit()
            print("card_direction enum +forms", flush=True)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verb_forms (
              entry_id BIGINT PRIMARY KEY REFERENCES entries (id) ON DELETE CASCADE,
              past TEXT[] NOT NULL,
              past_ipa TEXT[] NOT NULL,
              past_participle TEXT[] NOT NULL,
              past_participle_ipa TEXT[] NOT NULL,
              pattern TEXT,
              rank INT,
              cue TEXT,
              CHECK (cardinality(past) >= 1 AND cardinality(past) = cardinality(past_ipa)),
              CHECK (
                cardinality(past_participle) >= 1
                AND cardinality(past_participle) = cardinality(past_participle_ipa)
              )
            )
            """
        )
        # Irregular verbs mode (§016): answers counted apart from train.
        conn.execute(
            """
            ALTER TABLE card_progress
              DROP CONSTRAINT IF EXISTS card_progress_introduced_via_check,
              ADD CONSTRAINT card_progress_introduced_via_check
                CHECK (introduced_via IN ('train', 'assess', 'verbs'))
            """
        )
        conn.execute(
            """
            ALTER TABLE card_reviews
              DROP CONSTRAINT IF EXISTS card_reviews_source_check,
              ADD CONSTRAINT card_reviews_source_check
                CHECK (source IN ('train', 'assess', 'verbs'))
            """
        )
        conn.commit()


def seed_display_names() -> None:
    with connect() as conn:
        for login, name in KNOWN_DISPLAY_NAMES.items():
            conn.execute(
                "UPDATE users SET display_name = %s WHERE login = %s",
                (name, login),
            )
        conn.commit()


def migrate_load_limits() -> None:
    """Per-user×language new_per_day and advice history for adaptive load (§011)."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_load_limits (
              user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
              language language_code NOT NULL,
              new_per_day INT NOT NULL,
              base_new_per_day INT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_via TEXT NOT NULL DEFAULT 'default',
              last_change_on DATE,
              PRIMARY KEY (user_id, language),
              CHECK (new_per_day > 0),
              CHECK (base_new_per_day > 0),
              CHECK (updated_via IN ('default', 'auto', 'manual'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS load_advice_days (
              user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
              language language_code NOT NULL,
              day DATE NOT NULL,
              status TEXT NOT NULL,
              suggested INT NOT NULL,
              PRIMARY KEY (user_id, language, day),
              CHECK (status IN ('lower', 'keep', 'raise')),
              CHECK (suggested > 0)
            )
            """
        )
        conn.commit()
        print("user_load_limits ready", flush=True)


def migrate_fsrs() -> None:
    """Add FSRS columns and convert legacy interval/ease when needed."""
    with connect() as conn:
        conn.execute(
            """
            ALTER TABLE card_progress
              ADD COLUMN IF NOT EXISTS stability DOUBLE PRECISION,
              ADD COLUMN IF NOT EXISTS difficulty DOUBLE PRECISION,
              ADD COLUMN IF NOT EXISTS fsrs_state SMALLINT,
              ADD COLUMN IF NOT EXISTS fsrs_step SMALLINT,
              ADD COLUMN IF NOT EXISTS last_review TIMESTAMPTZ
            """
        )
        conn.execute(
            """
            ALTER TABLE card_reviews
              ADD COLUMN IF NOT EXISTS rating SMALLINT
            """
        )
        # Convert rows that still lack FSRS fields (legacy Anki-lite).
        has_ease = conn.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'card_progress' AND column_name = 'ease'
            """
        ).fetchone()
        if has_ease:
            conn.execute(
                """
                UPDATE card_progress SET
                  stability = GREATEST(0.1, interval_days),
                  difficulty = LEAST(10.0, GREATEST(1.0, 11.0 - ease * 2.0)),
                  fsrs_state = 2,
                  fsrs_step = NULL,
                  last_review = (
                    (due_on - (GREATEST(0, floor(interval_days))::int
                      * INTERVAL '1 day')) AT TIME ZONE 'UTC'
                  )
                WHERE stability IS NULL
                """
            )
        else:
            conn.execute(
                """
                UPDATE card_progress SET
                  stability = GREATEST(0.1, COALESCE(stability, interval_days, 0.1)),
                  difficulty = COALESCE(difficulty, 5.0),
                  fsrs_state = COALESCE(fsrs_state, 2)
                WHERE stability IS NULL OR difficulty IS NULL OR fsrs_state IS NULL
                """
            )
        conn.execute(
            """
            UPDATE card_progress SET
              stability = COALESCE(stability, 0.1),
              difficulty = COALESCE(difficulty, 5.0),
              fsrs_state = COALESCE(fsrs_state, 2)
            """
        )
        conn.execute(
            """
            ALTER TABLE card_progress
              ALTER COLUMN stability SET DEFAULT 0.1,
              ALTER COLUMN difficulty SET DEFAULT 5.0,
              ALTER COLUMN fsrs_state SET DEFAULT 2
            """
        )
        conn.execute(
            "ALTER TABLE card_progress ALTER COLUMN stability SET NOT NULL"
        )
        conn.execute(
            "ALTER TABLE card_progress ALTER COLUMN difficulty SET NOT NULL"
        )
        conn.execute(
            "ALTER TABLE card_progress ALTER COLUMN fsrs_state SET NOT NULL"
        )
        conn.commit()
        print("fsrs columns ready", flush=True)


def migrate_user_filters() -> None:
    """Per-user filter prefs and last selected language."""
    with connect() as conn:
        conn.execute(
            """
            ALTER TABLE users
              ADD COLUMN IF NOT EXISTS last_language language_code
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_language_filters (
              user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
              language language_code NOT NULL,
              textbooks TEXT[] NOT NULL DEFAULT '{}',
              topics TEXT[] NOT NULL DEFAULT '{}',
              PRIMARY KEY (user_id, language)
            )
            """
        )
        conn.commit()
        print("user_language_filters ready", flush=True)


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
            user = create_user(
                conn, "serafima", "serafima123", display_name="Серафима"
            )
            user_id = user.id
            print(f"created default user serafima id={user_id}", flush=True)
        else:
            user_id = int(row[0])
            conn.execute(
                "UPDATE users SET display_name = %s WHERE login = %s",
                ("Серафима", "serafima"),
            )
            conn.commit()

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


def seed_irregular_if_missing() -> None:
    """Load the irregular verbs list into an existing DB once (merge, no truncate)."""
    with connect() as conn:
        count = conn.execute("SELECT count(*) FROM verb_forms").fetchone()[0]
    if count or not IRREGULAR_EN.is_file():
        return
    print(f"loading {IRREGULAR_EN}", flush=True)
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "load_entries.py"),
        "--append",
        str(IRREGULAR_EN),
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    wait_for_db()
    migrate()
    seed_if_empty()
    seed_irregular_if_missing()
    raise SystemExit(
        subprocess.run(
            ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        ).returncode
    )


if __name__ == "__main__":
    main()
