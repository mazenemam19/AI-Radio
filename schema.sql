-- AI Radio — Echo Database Schema
-- Single source of truth for Local (SQLite) and Production (Supabase)

CREATE TABLE IF NOT EXISTS memory_log (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  headline           TEXT NOT NULL,
  original_headline  TEXT,
  source             TEXT,
  topic_tags         TEXT,     -- Parsed as text affinity in SQLite, native array compatible on Supabase
  my_take            TEXT,
  summary            TEXT,
  post_text          TEXT,
  audio_script       TEXT,
  audio_url          TEXT,
  video_url          TEXT,
  confidence         TEXT CHECK (confidence IN ('high', 'medium', 'low')),
  related_ids        TEXT,     -- Stored as JSON string for cross-environment safety
  likes              INTEGER DEFAULT 0,
  plays              INTEGER DEFAULT 0,
  broadcast_duration INTEGER DEFAULT 0,
  healer_used        BOOLEAN DEFAULT FALSE,
  writer_model       TEXT,
  narrator_model     TEXT
);

-- Performance index for chronological retention cleanup (delete_old_episodes)
CREATE INDEX IF NOT EXISTS idx_memory_log_created_at ON memory_log (created_at);
