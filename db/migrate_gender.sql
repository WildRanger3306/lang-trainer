DO $$ BEGIN
  CREATE TYPE noun_gender AS ENUM ('m', 'f');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS gender noun_gender;
