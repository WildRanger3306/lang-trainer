CREATE TYPE language_code AS ENUM ('en', 'fr');
CREATE TYPE part_of_speech AS ENUM (
  'noun',
  'adjective',
  'verb',
  'pronoun',
  'numeral',
  'adverb',
  'phrase',
  'other'
);
CREATE TYPE cefr_level AS ENUM ('A1', 'A2', 'B1', 'B2');
CREATE TYPE noun_gender AS ENUM ('m', 'f');

CREATE TABLE entries (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  language language_code NOT NULL,
  form TEXT NOT NULL,
  part_of_speech part_of_speech NOT NULL,
  part_of_speech_code TEXT,
  transcription TEXT,
  gender noun_gender,
  level cefr_level
);

CREATE TABLE entry_translations (
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  position SMALLINT NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (entry_id, position)
);

CREATE TABLE topics (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE textbooks (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE entry_topics (
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  topic_id BIGINT NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
  PRIMARY KEY (entry_id, topic_id)
);

CREATE TABLE entry_textbooks (
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  textbook_id BIGINT NOT NULL REFERENCES textbooks (id) ON DELETE CASCADE,
  PRIMARY KEY (entry_id, textbook_id)
);

CREATE INDEX idx_entries_language ON entries (language);
CREATE INDEX idx_entries_level ON entries (level);
CREATE INDEX idx_entries_part_of_speech ON entries (part_of_speech);

CREATE TYPE card_direction AS ENUM ('foreign_to_native', 'native_to_foreign');

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

CREATE TABLE card_reviews (
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

CREATE INDEX idx_card_reviews_answered_at ON card_reviews (answered_at);
CREATE INDEX idx_card_reviews_answered_on ON card_reviews (answered_on);
CREATE INDEX idx_card_reviews_entry ON card_reviews (entry_id, direction);
