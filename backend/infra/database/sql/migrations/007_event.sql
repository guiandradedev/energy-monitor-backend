CREATE TABLE IF NOT EXISTS event (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    type TEXT NOT NULL,
    device_id INTEGER REFERENCES device(id) ON DELETE SET NULL,
    payload JSONB
);

CREATE INDEX IF NOT EXISTS event_ts_idx ON event (ts DESC);
CREATE INDEX IF NOT EXISTS event_type_ts_idx ON event (type, ts DESC);
