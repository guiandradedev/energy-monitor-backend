from flask import Blueprint, request, jsonify

from infra.database.postgres import get_engine, text


events_bp = Blueprint("events", __name__, url_prefix="/api/events")


@events_bp.get("")
def list_events():
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
    except ValueError:
        return jsonify({"error": "limit inválido"}), 400

    since = request.args.get("since")
    event_type = request.args.get("type")
    device_id = request.args.get("device_id")

    where = []
    params = {"limit": limit}
    if since:
        where.append("e.ts >= :since")
        params["since"] = since
    if event_type:
        where.append("e.type = :type")
        params["type"] = event_type
    if device_id:
        try:
            params["device_id"] = int(device_id)
            where.append("e.device_id = :device_id")
        except ValueError:
            return jsonify({"error": "device_id deve ser inteiro"}), 400

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = text(f"""
        SELECT e.id, e.ts, e.type, e.device_id, e.payload,
               d.device_id AS device_id_str, d.name AS device_name
        FROM event e
        LEFT JOIN device d ON e.device_id = d.id
        {where_sql}
        ORDER BY e.ts DESC
        LIMIT :limit
    """)

    with get_engine().connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    return jsonify({"data": [
        {
            "id": r.id,
            "ts": r.ts.isoformat(),
            "type": r.type,
            "device": (
                {
                    "id": r.device_id,
                    "device_id": r.device_id_str,
                    "name": r.device_name,
                }
                if r.device_id is not None else None
            ),
            "payload": r.payload,
        }
        for r in rows
    ]})
