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

-- Uniqueness: one entry per (language, lower(form), part_of_speech).
-- Multiple textbooks/topics hang off the same row via link tables.
CREATE UNIQUE INDEX uq_entries_lang_form_pos
  ON entries (language, lower(form), part_of_speech);

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

CREATE TABLE users (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  login TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_language language_code,
  CONSTRAINT users_login_format CHECK (login ~ '^[a-zA-Z0-9_-]+$')
);

CREATE TABLE user_language_filters (
  user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  language language_code NOT NULL,
  textbooks TEXT[] NOT NULL DEFAULT '{}',
  topics TEXT[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (user_id, language)
);

CREATE TABLE user_load_limits (
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
);

CREATE TABLE load_advice_days (
  user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  language language_code NOT NULL,
  day DATE NOT NULL,
  status TEXT NOT NULL,
  suggested INT NOT NULL,
  PRIMARY KEY (user_id, language, day),
  CHECK (status IN ('lower', 'keep', 'raise')),
  CHECK (suggested > 0)
);

CREATE TABLE card_progress (
  user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  direction card_direction NOT NULL,
  due_on DATE NOT NULL,
  interval_days DOUBLE PRECISION NOT NULL DEFAULT 1
    CHECK (interval_days >= 1),
  stability DOUBLE PRECISION NOT NULL DEFAULT 0.1
    CHECK (stability > 0),
  difficulty DOUBLE PRECISION NOT NULL DEFAULT 5.0
    CHECK (difficulty >= 1 AND difficulty <= 10),
  fsrs_state SMALLINT NOT NULL DEFAULT 2,
  fsrs_step SMALLINT,
  last_review TIMESTAMPTZ,
  introduced_on DATE NOT NULL,
  introduced_via TEXT NOT NULL DEFAULT 'train'
    CHECK (introduced_via IN ('train', 'assess')),
  PRIMARY KEY (user_id, entry_id, direction)
);

CREATE INDEX idx_card_progress_due_on ON card_progress (due_on);
CREATE INDEX idx_card_progress_introduced_on ON card_progress (introduced_on);
CREATE INDEX idx_card_progress_user ON card_progress (user_id);

CREATE TABLE card_reviews (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  entry_id BIGINT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
  direction card_direction NOT NULL,
  answered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  answered_on DATE NOT NULL DEFAULT CURRENT_DATE,
  remembered BOOLEAN NOT NULL,
  was_new BOOLEAN NOT NULL,
  interval_before DOUBLE PRECISION NOT NULL DEFAULT 0
    CHECK (interval_before >= 0),
  interval_after DOUBLE PRECISION NOT NULL
    CHECK (interval_after >= 0),
  source TEXT NOT NULL DEFAULT 'train'
    CHECK (source IN ('train', 'assess')),
  rating SMALLINT
    CHECK (rating IS NULL OR rating BETWEEN 1 AND 4)
);

CREATE INDEX idx_card_reviews_answered_at ON card_reviews (answered_at);
CREATE INDEX idx_card_reviews_answered_on ON card_reviews (answered_on);
CREATE INDEX idx_card_reviews_entry ON card_reviews (entry_id, direction);
CREATE INDEX idx_card_reviews_user ON card_reviews (user_id);
