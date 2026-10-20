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

CREATE TABLE IF NOT EXISTS push_subscriptions (
    endpoint TEXT PRIMARY KEY,
    subscription_json TEXT NOT NULL,
    reminder_time TEXT NOT NULL,
    timezone TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    last_sent_date TEXT
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_enabled
    ON push_subscriptions(enabled);
