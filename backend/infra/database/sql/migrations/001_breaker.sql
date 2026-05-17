CREATE TABLE IF NOT EXISTS breaker (
    timestamp TIMESTAMPTZ NOT NULL,
    breaker_id TEXT,
    rms_sct1 REAL,
    rms_sct2 REAL,
    rms_zmpt1 REAL,
    rms_zmpt2 REAL
);

SELECT create_hypertable('breaker', 'timestamp', 'breaker_id', 4, if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS breaker_breaker_id_timestamp_idx ON breaker (breaker_id, timestamp DESC);
