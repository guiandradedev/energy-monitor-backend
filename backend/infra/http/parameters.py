from flask import Blueprint, request, jsonify

from infra.database.postgres import get_engine, text
from services.config_cache import config_cache


parameters_bp = Blueprint("parameters", __name__, url_prefix="/api/parameters")


def _serialize(row):
    return {
        "key": row.key,
        "value": row.value,
        "description": row.description,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@parameters_bp.get("")
def list_parameters():
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT key, value, description, updated_at
            FROM parameter
            ORDER BY key
        """)).fetchall()
    return jsonify({"data": [_serialize(r) for r in rows]})


@parameters_bp.put("/<string:key>")
def update_parameter(key):
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    if not isinstance(value, str) or not value.strip():
        return jsonify({"error": "value deve ser uma string não vazia"}), 400

    with get_engine().begin() as conn:
        row = conn.execute(text("""
            UPDATE parameter
            SET value = :value, updated_at = NOW()
            WHERE key = :key
            RETURNING key, value, description, updated_at
        """), {"key": key, "value": value.strip()}).first()

    if row is None:
        return jsonify({"error": "parâmetro não encontrado"}), 404

    config_cache.refresh()
    return jsonify({"data": _serialize(row)})
