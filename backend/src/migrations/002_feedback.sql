-- Active learning feedback from users on low-confidence/inconclusive results.
-- Images stored on disk at /app/feedback_images/{analysis_id}.{ext}.
-- IDEMPOTENT: Uses CREATE IF NOT EXISTS + ON CONFLICT DO NOTHING.
-- Safe to run on every startup — required by backend lifespan handler.

CREATE TABLE IF NOT EXISTS user_feedback (
    id              TEXT PRIMARY KEY,
    analysis_id     TEXT NOT NULL UNIQUE,
    user_label      TEXT NOT NULL,
    notes           TEXT,
    original_label  TEXT NOT NULL,
    original_conf   NUMERIC(5,4) NOT NULL,
    prediction_quality TEXT NOT NULL,
    species         TEXT NOT NULL,
    image_path      TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'image/jpeg',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_label ON user_feedback (user_label);
CREATE INDEX IF NOT EXISTS idx_feedback_species ON user_feedback (species);
