"""Popula dados de referência iniciais. Idempotente.

O seed do `breaker` (telemetria do medidor) gera 20 dias × 86400 pontos via COPY
e leva ~30-60s. Roda apenas se a tabela estiver vazia para o breaker_id alvo na
janela de 20 dias. Para regerar, faça `TRUNCATE breaker` manualmente."""
import csv
import io
import math
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

from infra.database.postgres import get_engine, text


PRIORITIES = [
    {"label": "Baixa", "rank": 1},
    {"label": "Média", "rank": 2},
    {"label": "Alta", "rank": 3},
]

SAFETY_LIMITS = [
    {
        "breaker_id": "1",
        "nominal_current_a": 20.0,
        "shed_threshold_pct": 90.0,
        "restore_threshold_pct": 70.0,
    },
]

PARAMETERS = [
    ("heartbeat_interval_s", "30", "Intervalo entre pings do backend aos ESPs de carga"),
    ("heartbeat_timeout_s", "90", "Tempo sem resposta para considerar uma carga offline"),
    ("cache_refresh_s", "300", "Intervalo de refresh do cache de parâmetros/limites/prioridades"),
    ("restore_guard_time_s", "30", "Intervalo mínimo entre religamentos automáticos"),
    ("shed_duration_s", "5", "Tempo acima do limiar antes de disparar desligamento"),
]

BREAKER_ID = "1"
BREAKER_DAYS = 20
BREAKER_CHUNK_SECONDS = 100_000


def seed_priorities(conn):
    for p in PRIORITIES:
        conn.execute(
            text("""
                INSERT INTO priority_level (label, rank)
                VALUES (:label, :rank)
                ON CONFLICT (label) DO NOTHING
            """),
            p,
        )


def seed_safety_limits(conn):
    for s in SAFETY_LIMITS:
        conn.execute(
            text("""
                INSERT INTO safety_limit (
                    breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
                ) VALUES (
                    :breaker_id, :nominal_current_a, :shed_threshold_pct, :restore_threshold_pct
                )
                ON CONFLICT (breaker_id) DO NOTHING
            """),
            s,
        )


def seed_parameters(conn):
    for key, value, description in PARAMETERS:
        conn.execute(
            text("""
                INSERT INTO parameter (key, value, description)
                VALUES (:key, :value, :description)
                ON CONFLICT (key) DO NOTHING
            """),
            {"key": key, "value": value, "description": description},
        )


def _simulate_currents(t: datetime) -> tuple[float, float]:
    """Curva diária com pico noturno (~20h) e pico secundário matinal (~7h),
    suavemente reduzida nos finais de semana, com ruído por amostra."""
    hour = t.hour + t.minute / 60 + t.second / 3600
    base = 1.5
    evening = 11.0 * math.exp(-((hour - 20) ** 2) / 12)
    morning = 4.0 * math.exp(-((hour - 7) ** 2) / 4)
    total = base + evening + morning
    if t.weekday() >= 5:
        total *= 0.85
    total += random.uniform(-0.4, 0.4)
    sct1 = max(0.0, total / 2 + random.uniform(-0.2, 0.2))
    sct2 = max(0.0, total / 2 + random.uniform(-0.2, 0.2))
    return sct1, sct2


def _simulate_voltages() -> tuple[float, float]:
    base = 127.0
    return (
        base + random.uniform(-2.5, 2.5),
        base + random.uniform(-2.5, 2.5),
    )


def seed_breaker():
    """Gera telemetria simulada (1 ponto/segundo, BREAKER_DAYS dias) via COPY."""
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(
            text("""
                SELECT COUNT(*) FROM breaker
                WHERE breaker_id = :bid
                  AND timestamp >= NOW() - make_interval(days => :days)
            """),
            {"bid": BREAKER_ID, "days": BREAKER_DAYS},
        ).scalar()

    if count and count > 0:
        print(
            f"breaker já tem {count:,} pontos nos últimos {BREAKER_DAYS} dias "
            f"para breaker_id={BREAKER_ID!r}, pulando. "
            f"(Para regerar: TRUNCATE breaker;)"
        )
        return

    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=BREAKER_DAYS)
    total = int((end - start).total_seconds())
    print(
        f"Gerando {total:,} pontos de telemetria simulada "
        f"({BREAKER_DAYS} dias × 86400 pts/dia) via COPY..."
    )

    random.seed(42)
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        chunk_start = start
        rows_done = 0
        while chunk_start < end:
            chunk_end = min(
                chunk_start + timedelta(seconds=BREAKER_CHUNK_SECONDS),
                end,
            )
            buf = io.StringIO()
            writer = csv.writer(buf)
            t = chunk_start
            while t < chunk_end:
                sct1, sct2 = _simulate_currents(t)
                zmpt1, zmpt2 = _simulate_voltages()
                writer.writerow([
                    t.isoformat(),
                    BREAKER_ID,
                    f"{sct1:.3f}",
                    f"{sct2:.3f}",
                    f"{zmpt1:.3f}",
                    f"{zmpt2:.3f}",
                ])
                t += timedelta(seconds=1)
            buf.seek(0)
            cursor.copy_expert(
                "COPY breaker (timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2) "
                "FROM STDIN WITH CSV",
                buf,
            )
            rows_done += int((chunk_end - chunk_start).total_seconds())
            print(f"  {rows_done:,} / {total:,} pontos inseridos")
            chunk_start = chunk_end
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        cursor.close()
        raw_conn.close()

    print(f"breaker seed concluído: {rows_done:,} pontos.")


def main():
    engine = get_engine()
    with engine.begin() as conn:
        seed_priorities(conn)
        seed_safety_limits(conn)
        seed_parameters(conn)
    seed_breaker()
    print("Seed concluído.")


if __name__ == "__main__":
    main()
