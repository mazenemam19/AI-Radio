-- Enable UUID and any standard extensions if required
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core Memory Log Table
CREATE TABLE IF NOT EXISTS memory_log (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  headline TEXT NOT NULL,
  source TEXT,
  topic_tags TEXT[],
  my_take TEXT,
  post_text TEXT,
  audio_script TEXT,
  audio_url TEXT, -- URL to stream public MP3 hosted in Supabase Storage
  video_url TEXT, -- URL to YouTube Video (or MP4)
  confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
  related_ids INTEGER[],
  likes INTEGER DEFAULT 0,
  plays INTEGER DEFAULT 0,
  original_headline TEXT,
  broadcast_duration INTEGER DEFAULT 0,
  healer_used BOOLEAN DEFAULT FALSE,
  writer_model TEXT,
  narrator_model TEXT
);

-- Comments Table
CREATE TABLE IF NOT EXISTS comments (
  id SERIAL PRIMARY KEY,
  episode_id INTEGER REFERENCES memory_log(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  author_name TEXT DEFAULT 'Anonymous Human',
  comment_text TEXT NOT NULL
);

-- Create Indexes for Speed
CREATE INDEX IF NOT EXISTS idx_memory_log_created_at ON memory_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_episode_id ON comments(episode_id);

-- Atomic Functions for Engagement Counters (avoids race conditions)
CREATE OR REPLACE FUNCTION increment_likes(row_id INT)
RETURNS VOID AS $$
BEGIN
  UPDATE memory_log SET likes = likes + 1 WHERE id = row_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION increment_plays(row_id INT)
RETURNS VOID AS $$
BEGIN
  UPDATE memory_log SET plays = plays + 1 WHERE id = row_id;
END;
$$ LANGUAGE plpgsql;
