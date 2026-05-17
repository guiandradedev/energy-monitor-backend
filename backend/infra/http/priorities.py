from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from infra.database.postgres import get_engine, text
from services.config_cache import config_cache


priorities_bp = Blueprint("priorities", __name__, url_prefix="/api/priorities")


def _serialize(row):
    return {"id": row.id, "label": row.label, "rank": row.rank}


def _validate_payload(data, require_all=True):
    errors = []
    label = data.get("label")
    rank = data.get("rank")

    if require_all or label is not None:
        if not isinstance(label, str) or not label.strip():
            errors.append("label deve ser uma string não vazia")
    if require_all or rank is not None:
        if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
            errors.append("rank deve ser um inteiro positivo")
    return errors


@priorities_bp.get("")
def list_priorities():
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT id, label, rank FROM priority_level ORDER BY rank DESC"
        )).fetchall()
    return jsonify({"data": [_serialize(r) for r in rows]})


@priorities_bp.post("")
def create_priority():
    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, require_all=True)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    try:
        with get_engine().begin() as conn:
            row = conn.execute(text("""
                INSERT INTO priority_level (label, rank)
                VALUES (:label, :rank)
                RETURNING id, label, rank
            """), {"label": data["label"].strip(), "rank": data["rank"]}).first()
    except IntegrityError as exc:
        return jsonify({"error": "label ou rank já existem"}), 409

    config_cache.refresh()
    return jsonify({"data": _serialize(row)}), 201


@priorities_bp.put("/<int:priority_id>")
def update_priority(priority_id):
    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, require_all=False)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    if "label" not in data and "rank" not in data:
        return jsonify({"error": "informe ao menos label ou rank"}), 400

    sets = []
    params = {"id": priority_id}
    if "label" in data:
        sets.append("label = :label")
        params["label"] = data["label"].strip()
    if "rank" in data:
        sets.append("rank = :rank")
        params["rank"] = data["rank"]

    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                text(f"""
                    UPDATE priority_level SET {", ".join(sets)}
                    WHERE id = :id
                    RETURNING id, label, rank
                """),
                params,
            ).first()
    except IntegrityError:
        return jsonify({"error": "label ou rank já existem"}), 409

    if row is None:
        return jsonify({"error": "prioridade não encontrada"}), 404

    config_cache.refresh()
    return jsonify({"data": _serialize(row)})


@priorities_bp.delete("/<int:priority_id>")
def delete_priority(priority_id):
    try:
        with get_engine().begin() as conn:
            result = conn.execute(
                text("DELETE FROM priority_level WHERE id = :id"),
                {"id": priority_id},
            )
    except IntegrityError:
        return jsonify({"error": "prioridade em uso por algum dispositivo"}), 409

    if result.rowcount == 0:
        return jsonify({"error": "prioridade não encontrada"}), 404

    config_cache.refresh()
    return "", 204
