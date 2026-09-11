-- Knowledge assessment: mark introductions so they don't burn the daily new quota.

ALTER TABLE card_progress
  ADD COLUMN IF NOT EXISTS introduced_via TEXT NOT NULL DEFAULT 'train';

ALTER TABLE card_reviews
  ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'train';
