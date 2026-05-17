from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from infra.database.postgres import get_engine, text
from infra.broker.mqtt import get_mqtt_client
from services.config_cache import config_cache
from services.events import record_event


devices_bp = Blueprint("devices", __name__, url_prefix="/api/devices")


def _serialize(row):
    return {
        "id": row.id,
        "device_id": row.device_id,
        "name": row.name,
        "priority": {
            "id": row.priority_id,
            "label": row.priority_label,
            "rank": row.priority_rank,
        },
        "state": {
            "state": row.state,
            "source": row.source,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            "last_changed_at": row.last_changed_at.isoformat() if row.last_changed_at else None,
        },
    }


LIST_SQL = """
    SELECT
        d.id, d.device_id, d.name,
        p.id AS priority_id, p.label AS priority_label, p.rank AS priority_rank,
        s.state, s.source, s.last_seen, s.last_changed_at
    FROM device d
    INNER JOIN priority_level p ON d.priority_id = p.id
    LEFT JOIN device_state s ON d.id = s.device_id
"""


@devices_bp.get("")
def list_devices():
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            LIST_SQL + " ORDER BY p.rank DESC, d.name"
        )).fetchall()
    return jsonify({"data": [_serialize(r) for r in rows]})


@devices_bp.post("")
def create_device():
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")
    name = data.get("name")
    priority_id = data.get("priority_id")

    errors = []
    if not isinstance(device_id, str) or not device_id.strip():
        errors.append("device_id deve ser uma string não vazia")
    if not isinstance(name, str) or not name.strip():
        errors.append("name deve ser uma string não vazia")
    if not isinstance(priority_id, int) or isinstance(priority_id, bool) or priority_id <= 0:
        errors.append("priority_id deve ser um inteiro positivo")
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    try:
        with get_engine().begin() as conn:
            new_id_row = conn.execute(text("""
                INSERT INTO device (device_id, name, priority_id)
                VALUES (:device_id, :name, :priority_id)
                RETURNING id
            """), {
                "device_id": device_id.strip(),
                "name": name.strip(),
                "priority_id": priority_id,
            }).first()
            new_id = new_id_row.id

            conn.execute(text("""
                INSERT INTO device_state (device_id, state, source)
                VALUES (:device_id, 'unknown', 'manual')
            """), {"device_id": new_id})

            row = conn.execute(
                text(LIST_SQL + " WHERE d.id = :id"),
                {"id": new_id},
            ).first()
    except IntegrityError as exc:
        msg = str(exc.orig).lower() if exc.orig else ""
        if "device_id" in msg:
            return jsonify({"error": "device_id já cadastrado"}), 409
        if "priority_id" in msg or "foreign key" in msg:
            return jsonify({"error": "priority_id inexistente"}), 400
        return jsonify({"error": "violação de integridade"}), 409

    return jsonify({"data": _serialize(row)}), 201


@devices_bp.put("/<int:device_pk>")
def update_device(device_pk):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    priority_id = data.get("priority_id")

    errors = []
    if name is not None and (not isinstance(name, str) or not name.strip()):
        errors.append("name deve ser uma string não vazia")
    if priority_id is not None:
        if not isinstance(priority_id, int) or isinstance(priority_id, bool) or priority_id <= 0:
            errors.append("priority_id deve ser um inteiro positivo")
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    if name is None and priority_id is None:
        return jsonify({"error": "informe ao menos name ou priority_id"}), 400

    sets = ["updated_at = NOW()"]
    params = {"id": device_pk}
    if name is not None:
        sets.append("name = :name")
        params["name"] = name.strip()
    if priority_id is not None:
        sets.append("priority_id = :priority_id")
        params["priority_id"] = priority_id

    try:
        with get_engine().begin() as conn:
            updated = conn.execute(
                text(f"UPDATE device SET {', '.join(sets)} WHERE id = :id RETURNING id"),
                params,
            ).first()
            if updated is None:
                return jsonify({"error": "dispositivo não encontrado"}), 404
            row = conn.execute(
                text(LIST_SQL + " WHERE d.id = :id"),
                {"id": device_pk},
            ).first()
    except IntegrityError:
        return jsonify({"error": "priority_id inexistente"}), 400

    return jsonify({"data": _serialize(row)})


@devices_bp.delete("/<int:device_pk>")
def delete_device(device_pk):
    with get_engine().begin() as conn:
        result = conn.execute(
            text("DELETE FROM device WHERE id = :id"),
            {"id": device_pk},
        )
    if result.rowcount == 0:
        return jsonify({"error": "dispositivo não encontrado"}), 404
    return "", 204


@devices_bp.post("/<int:device_pk>/cmd")
def send_cmd(device_pk):
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("on", "off"):
        return jsonify({"error": "action deve ser 'on' ou 'off'"}), 400

    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, device_id FROM device WHERE id = :id"),
            {"id": device_pk},
        ).first()
    if row is None:
        return jsonify({"error": "dispositivo não encontrado"}), 404

    try:
        req_id, rc = get_mqtt_client().publish_cmd(row.device_id, action, reason="manual")
    except Exception as exc:
        return jsonify({"error": f"falha ao publicar cmd: {exc}"}), 502

    with get_engine().begin() as conn:
        record_event(
            "cmd_sent",
            device_pk,
            {
                "action": action,
                "reason": "manual",
                "req_id": req_id,
                "mqtt_rc": rc,
            },
            conn=conn,
        )

    return jsonify({"data": {"req_id": req_id, "queued": rc == 0}}), 202
