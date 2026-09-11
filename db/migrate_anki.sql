DO $$ BEGIN
  CREATE TYPE card_direction AS ENUM ('foreign_to_native', 'native_to_foreign');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DROP TABLE IF EXISTS card_progress;

CREATE TABLE card_progress (
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  direction card_direction NOT NULL,
  due_on DATE NOT NULL,
  interval_days DOUBLE PRECISION NOT NULL DEFAULT 1
    CHECK (interval_days >= 1),
  ease DOUBLE PRECISION NOT NULL DEFAULT 2.5
    CHECK (ease >= 1.3),
  introduced_on DATE NOT NULL,
  PRIMARY KEY (entry_id, direction)
);

CREATE INDEX idx_card_progress_due_on ON card_progress (due_on);
CREATE INDEX idx_card_progress_introduced_on ON card_progress (introduced_on);
