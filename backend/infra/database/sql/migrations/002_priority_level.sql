-- rank maior = prioridade mais alta (religa primeiro, desliga por último)
CREATE TABLE IF NOT EXISTS priority_level (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    rank INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
