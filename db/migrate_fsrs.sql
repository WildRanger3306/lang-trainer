-- FSRS fields on card_progress; rating on card_reviews.
-- Convert legacy interval/ease → stability/difficulty (rough).

ALTER TABLE card_progress
  ADD COLUMN IF NOT EXISTS stability DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS difficulty DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS fsrs_state SMALLINT,
  ADD COLUMN IF NOT EXISTS fsrs_step SMALLINT,
  ADD COLUMN IF NOT EXISTS last_review TIMESTAMPTZ;

ALTER TABLE card_reviews
  ADD COLUMN IF NOT EXISTS rating SMALLINT
    CHECK (rating IS NULL OR rating BETWEEN 1 AND 4);

-- Backfill from legacy Anki-lite columns when present.
UPDATE card_progress SET
  stability = GREATEST(0.1, interval_days),
  difficulty = LEAST(10.0, GREATEST(1.0, 11.0 - ease * 2.0)),
  fsrs_state = 2,
  fsrs_step = NULL,
  last_review = (
    (due_on - (GREATEST(0, floor(interval_days))::int * INTERVAL '1 day'))
    AT TIME ZONE 'UTC'
  )
WHERE stability IS NULL;

ALTER TABLE card_progress
  ALTER COLUMN stability SET DEFAULT 0.1,
  ALTER COLUMN difficulty SET DEFAULT 5.0,
  ALTER COLUMN fsrs_state SET DEFAULT 2;

ALTER TABLE card_progress
  ALTER COLUMN stability SET NOT NULL,
  ALTER COLUMN difficulty SET NOT NULL,
  ALTER COLUMN fsrs_state SET NOT NULL;

-- ease no longer used by scheduler; keep column for compatibility if present.
