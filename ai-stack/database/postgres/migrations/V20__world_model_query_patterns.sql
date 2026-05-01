-- V20: World Model — Query Sequence Patterns
-- Phase 20: Predictive Context Warming
-- Apply: psql $POSTGRES_URL -f V20__world_model_query_patterns.sql

CREATE TABLE IF NOT EXISTS query_sequence_patterns (
  id               SERIAL PRIMARY KEY,
  query_hash       TEXT NOT NULL,
  query_summary    TEXT NOT NULL,
  hour_of_day      INT  NOT NULL,
  day_of_week      INT  NOT NULL,
  follow_on_hashes TEXT[],
  occurrence_count INT  DEFAULT 1,
  last_seen        TIMESTAMPTZ DEFAULT NOW(),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qsp_hash ON query_sequence_patterns(query_hash);
CREATE INDEX IF NOT EXISTS idx_qsp_hour ON query_sequence_patterns(hour_of_day);
CREATE INDEX IF NOT EXISTS idx_qsp_last_seen ON query_sequence_patterns(last_seen);
