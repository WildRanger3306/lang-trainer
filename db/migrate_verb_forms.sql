-- Irregular verb forms (§015). Idempotent; the app entrypoint runs the same steps.
ALTER TYPE card_direction ADD VALUE IF NOT EXISTS 'forms';

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
);

-- Irregular verbs mode (§016): its answers are counted apart from train.
ALTER TABLE card_progress DROP CONSTRAINT IF EXISTS card_progress_introduced_via_check;
ALTER TABLE card_progress ADD CONSTRAINT card_progress_introduced_via_check
  CHECK (introduced_via IN ('train', 'assess', 'verbs'));
ALTER TABLE card_reviews DROP CONSTRAINT IF EXISTS card_reviews_source_check;
ALTER TABLE card_reviews ADD CONSTRAINT card_reviews_source_check
  CHECK (source IN ('train', 'assess', 'verbs'));
