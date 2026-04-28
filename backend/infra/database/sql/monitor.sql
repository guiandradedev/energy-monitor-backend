CREATE TABLE breaker (
    timestamp TIMESTAMPTZ NOT NULL,
    breaker_id TEXT,
    rms_sct1 REAL,
    rms_sct2 REAL,
    rms_zmpt1 REAL,
    rms_zmpt2 REAL
);

SELECT create_hypertable('breaker', 'timestamp', 'breaker_id', 4); -- Transforma em hypertable com particionamento extra

CREATE INDEX ON breaker (breaker_id, timestamp DESC); -- cria index 

-- SELECT add_retention_policy('breaker', INTERVAL '7 days'); -- política de retenção (exclui dados mais antigos que 7 dias)

INSERT INTO breaker (timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2) VALUES (NOW(), 'device1', 1.0, 2.0, 3.0, 4.0); -- Insere um dado de exemplo

SELECT * FROM breaker ORDER BY timestamp DESC; -- consulta os dados ordenados por tempo decrescente