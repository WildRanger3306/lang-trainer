-- One lexical unit per language + form + part of speech (case-insensitive form).
-- Cross-book duplicates in JSON dumps are merged at load time into one row + tags.

CREATE UNIQUE INDEX IF NOT EXISTS uq_entries_lang_form_pos
  ON entries (language, lower(form), part_of_speech);
