CREATE TABLE IF NOT EXISTS safety_limit (
    id SERIAL PRIMARY KEY,
    breaker_id TEXT NOT NULL UNIQUE,
    nominal_current_a REAL NOT NULL CHECK (nominal_current_a > 0),
    shed_threshold_pct REAL NOT NULL CHECK (shed_threshold_pct > 0 AND shed_threshold_pct <= 100),
    restore_threshold_pct REAL NOT NULL CHECK (restore_threshold_pct > 0 AND restore_threshold_pct <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT restore_lt_shed CHECK (restore_threshold_pct < shed_threshold_pct)
);
