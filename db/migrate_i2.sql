DO $$ BEGIN
  CREATE TYPE card_direction AS ENUM ('foreign_to_native', 'native_to_foreign');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS card_progress (
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  direction card_direction NOT NULL,
  streak INTEGER NOT NULL DEFAULT 0 CHECK (streak >= 0),
  PRIMARY KEY (entry_id, direction)
);
