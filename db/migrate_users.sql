-- Multi-user: accounts + progress scoped by user_id.

CREATE TABLE IF NOT EXISTS users (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  login TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT users_login_format CHECK (login ~ '^[a-zA-Z0-9_-]+$')
);

-- Applied by scripts/docker_entrypoint.py when upgrading existing DBs:
-- ADD user_id, backfill, switch PK on card_progress.
