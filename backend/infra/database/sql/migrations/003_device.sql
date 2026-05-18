CREATE TABLE IF NOT EXISTS device (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    priority_id INTEGER NOT NULL REFERENCES priority_level(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS device_priority_id_idx ON device (priority_id);
