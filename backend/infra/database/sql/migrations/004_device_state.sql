CREATE TABLE IF NOT EXISTS device_state (
    device_id INTEGER PRIMARY KEY REFERENCES device(id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('on', 'off', 'unknown')),
    source TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
    last_seen TIMESTAMPTZ,
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
