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
);

ALTER TABLE card_reviews
  ADD COLUMN IF NOT EXISTS answered_on DATE NOT NULL DEFAULT CURRENT_DATE;

CREATE INDEX IF NOT EXISTS idx_card_reviews_answered_at ON card_reviews (answered_at);
CREATE INDEX IF NOT EXISTS idx_card_reviews_answered_on ON card_reviews (answered_on);
CREATE INDEX IF NOT EXISTS idx_card_reviews_entry ON card_reviews (entry_id, direction);
