CREATE TABLE breaker (
    created_at TIMESTAMPTZ NOT NULL,
    device_id TEXT,
    rms_sct1 REAL,
    rms_sct2 REAL,
    rms_zmpt1 REAL,
    rms_zmpt2 REAL
);

SELECT create_hypertable('breaker', 'created_at', 'device_id', 4); -- Transforma em hypertable com particionamento extra

CREATE INDEX ON breaker (device_id, created_at DESC); -- cria index 

-- SELECT add_retention_policy('breaker', INTERVAL '7 days'); -- política de retenção (exclui dados mais antigos que 7 dias)

INSERT INTO breaker (created_at, device_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2) VALUES (NOW(), 'device1', 1.0, 2.0, 3.0, 4.0); -- Insere um dado de exemplo

SELECT * FROM breaker ORDER BY created_at DESC; -- consulta os dados ordenados por tempo decrescente
