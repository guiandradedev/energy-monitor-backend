from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, Response, stream_with_context

from infra.database.postgres import get_engine, text


telemetry_bp = Blueprint("telemetry", __name__, url_prefix="/api/telemetry")

VALID_FIELDS = {"rms_sct1", "rms_sct2", "rms_zmpt1", "rms_zmpt2"}
OP_MAP = {"eq": "=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}


def _parse_iso(name: str, value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{name} inválido (use ISO 8601)")


def _parse_filters():
    """Retorna (from_ts, to_ts, breaker_id, field, op, value) ou levanta ValueError."""
    args = request.args
    from_str = args.get("from")
    to_str = args.get("to")
    breaker_id = args.get("breaker_id", "1")
    field = args.get("field") or None
    op = args.get("op") or None
    value_str = args.get("value")

    from_ts = _parse_iso("from", from_str) if from_str else (
        datetime.now(timezone.utc) - timedelta(hours=1)
    )
    to_ts = _parse_iso("to", to_str) if to_str else datetime.now(timezone.utc)

    if from_ts > to_ts:
        raise ValueError("from deve ser anterior a to")

    value = None
    if field or op or value_str:
        if not (field and op and value_str is not None):
            raise ValueError("field, op e value devem ser fornecidos juntos")
        if field not in VALID_FIELDS:
            raise ValueError(
                f"field inválido. Use: {', '.join(sorted(VALID_FIELDS))}"
            )
        if op not in OP_MAP:
            raise ValueError(
                f"op inválido. Use: {', '.join(sorted(OP_MAP.keys()))}"
            )
        try:
            value = float(value_str)
        except ValueError:
            raise ValueError("value deve ser numérico")

    return from_ts, to_ts, breaker_id, field, op, value


def _build_where(from_ts, to_ts, breaker_id, field, op, value):
    where = [
        "timestamp >= :from_ts",
        "timestamp <= :to_ts",
        "breaker_id = :breaker_id",
    ]
    params = {"from_ts": from_ts, "to_ts": to_ts, "breaker_id": breaker_id}
    if field and op and value is not None:
        # Colunas RMS são REAL (float32): o valor armazenado nunca casa
        # exatamente com o decimal exibido. Arredondamos os dois lados para
        # 3 casas (mesma precisão da tabela) antes de comparar — assim o
        # filtro reflete o que o usuário vê.
        where.append(
            f"ROUND(CAST({field} AS numeric), 3) {OP_MAP[op]} "
            f"ROUND(CAST(:filter_value AS numeric), 3)"
        )
        params["filter_value"] = value
    return " AND ".join(where), params


@telemetry_bp.get("")
def list_telemetry():
    try:
        filters = _parse_filters()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        limit = min(max(int(request.args.get("limit", 200)), 1), 5000)
    except ValueError:
        return jsonify({"error": "limit inválido"}), 400
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify({"error": "offset inválido"}), 400

    where_sql, params = _build_where(*filters)

    sql = text(f"""
        SELECT timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2
        FROM breaker
        WHERE {where_sql}
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :offset
    """)
    count_sql = text(f"SELECT COUNT(*) FROM breaker WHERE {where_sql}")

    with get_engine().connect() as conn:
        rows = conn.execute(sql, {**params, "limit": limit, "offset": offset}).fetchall()
        total = conn.execute(count_sql, params).scalar()

    return jsonify({
        "data": [
            {
                "timestamp": r.timestamp.isoformat(),
                "breaker_id": r.breaker_id,
                "rms_sct1": float(r.rms_sct1),
                "rms_sct2": float(r.rms_sct2),
                "rms_zmpt1": float(r.rms_zmpt1),
                "rms_zmpt2": float(r.rms_zmpt2),
            }
            for r in rows
        ],
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    })


@telemetry_bp.get("/recent")
def recent_telemetry():
    breaker_id = request.args.get("breaker_id", "1")
    try:
        n = min(max(int(request.args.get("n", 120)), 1), 5000)
    except ValueError:
        return jsonify({"error": "n inválido"}), 400

    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT timestamp, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2
            FROM breaker
            WHERE breaker_id = :bid
            ORDER BY timestamp DESC
            LIMIT :n
        """), {"bid": breaker_id, "n": n}).fetchall()

    data = [
        {
            "timestamp": r.timestamp.isoformat(),
            "rms_sct1": float(r.rms_sct1),
            "rms_sct2": float(r.rms_sct2),
            "rms_zmpt1": float(r.rms_zmpt1),
            "rms_zmpt2": float(r.rms_zmpt2),
        }
        for r in reversed(rows)
    ]
    return jsonify({"data": data})


@telemetry_bp.get("/hourly")
def hourly_summary():
    """Médias por hora nas últimas N horas, ancoradas no dado mais recente
    disponível (útil quando a coleta não é em tempo real)."""
    breaker_id = request.args.get("breaker_id", "1")
    try:
        hours = min(max(int(request.args.get("hours", 24)), 1), 168)
    except ValueError:
        return jsonify({"error": "hours inválido"}), 400

    sql = text("""
        WITH latest AS (
            SELECT MAX(timestamp) AS ts FROM breaker WHERE breaker_id = :bid
        )
        SELECT
            DATE_TRUNC('hour', b.timestamp) AS hour,
            AVG(b.rms_sct1) AS avg_sct1,
            AVG(b.rms_sct2) AS avg_sct2,
            AVG(b.rms_zmpt1) AS avg_zmpt1,
            AVG(b.rms_zmpt2) AS avg_zmpt2
        FROM breaker b, latest l
        WHERE b.breaker_id = :bid
          AND l.ts IS NOT NULL
          AND b.timestamp >= l.ts - make_interval(hours => :hours)
          AND b.timestamp <= l.ts
        GROUP BY hour
        ORDER BY hour ASC
    """)
    with get_engine().connect() as conn:
        rows = conn.execute(sql, {"bid": breaker_id, "hours": hours}).fetchall()

    return jsonify({"data": [
        {
            "hour": r.hour.isoformat(),
            "avg_sct1": float(r.avg_sct1),
            "avg_sct2": float(r.avg_sct2),
            "avg_zmpt1": float(r.avg_zmpt1),
            "avg_zmpt2": float(r.avg_zmpt2),
        }
        for r in rows
    ]})


@telemetry_bp.get("/export.csv")
def export_csv():
    try:
        filters = _parse_filters()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    where_sql, params = _build_where(*filters)
    sql = text(f"""
        SELECT timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2
        FROM breaker
        WHERE {where_sql}
        ORDER BY timestamp ASC
    """)

    def generate():
        yield "timestamp,breaker_id,rms_sct1,rms_sct2,rms_zmpt1,rms_zmpt2\n"
        engine = get_engine()
        with engine.connect() as conn:
            streaming = conn.execution_options(stream_results=True, yield_per=1000)
            for r in streaming.execute(sql, params):
                yield (
                    f"{r.timestamp.isoformat()},{r.breaker_id},"
                    f"{r.rms_sct1},{r.rms_sct2},{r.rms_zmpt1},{r.rms_zmpt2}\n"
                )

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=telemetria.csv",
            "Cache-Control": "no-store",
        },
    )
