CREATE TABLE IF NOT EXISTS guidance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    mode TEXT NOT NULL CHECK (mode IN ('advisor', 'career')),
    education TEXT NOT NULL,
    stream TEXT,
    interest TEXT NOT NULL,
    skills TEXT NOT NULL,
    goal TEXT NOT NULL,
    budget TEXT,
    -- Keep the complete response so the API can later show a useful recent-history summary.
    recommendation_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_guidance_sessions_created_at
    ON guidance_sessions(created_at DESC);
