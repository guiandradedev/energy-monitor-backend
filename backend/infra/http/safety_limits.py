from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError, DataError

from infra.database.postgres import get_engine, text
from services.config_cache import config_cache


safety_limits_bp = Blueprint("safety_limits", __name__, url_prefix="/api/safety-limits")


def _serialize(row):
    return {
        "id": row.id,
        "breaker_id": row.breaker_id,
        "nominal_current_a": float(row.nominal_current_a),
        "shed_threshold_pct": float(row.shed_threshold_pct),
        "restore_threshold_pct": float(row.restore_threshold_pct),
    }


def _validate(data, require_all=True):
    errors = []
    breaker_id = data.get("breaker_id")
    nominal = data.get("nominal_current_a")
    shed = data.get("shed_threshold_pct")
    restore = data.get("restore_threshold_pct")

    if require_all or breaker_id is not None:
        if not isinstance(breaker_id, str) or not breaker_id.strip():
            errors.append("breaker_id deve ser uma string não vazia")
    if require_all or nominal is not None:
        if not isinstance(nominal, (int, float)) or isinstance(nominal, bool) or nominal <= 0:
            errors.append("nominal_current_a deve ser um número positivo")
    if require_all or shed is not None:
        if not isinstance(shed, (int, float)) or isinstance(shed, bool) or not (0 < shed <= 100):
            errors.append("shed_threshold_pct deve estar em (0, 100]")
    if require_all or restore is not None:
        if not isinstance(restore, (int, float)) or isinstance(restore, bool) or not (0 < restore <= 100):
            errors.append("restore_threshold_pct deve estar em (0, 100]")

    if not errors and shed is not None and restore is not None and restore >= shed:
        errors.append("restore_threshold_pct deve ser menor que shed_threshold_pct")
    return errors


@safety_limits_bp.get("")
def list_safety_limits():
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT id, breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
            FROM safety_limit
            ORDER BY breaker_id
        """)).fetchall()
    return jsonify({"data": [_serialize(r) for r in rows]})


@safety_limits_bp.post("")
def create_safety_limit():
    data = request.get_json(silent=True) or {}
    errors = _validate(data, require_all=True)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    try:
        with get_engine().begin() as conn:
            row = conn.execute(text("""
                INSERT INTO safety_limit (
                    breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
                ) VALUES (
                    :breaker_id, :nominal_current_a, :shed_threshold_pct, :restore_threshold_pct
                )
                RETURNING id, breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
            """), {
                "breaker_id": data["breaker_id"].strip(),
                "nominal_current_a": data["nominal_current_a"],
                "shed_threshold_pct": data["shed_threshold_pct"],
                "restore_threshold_pct": data["restore_threshold_pct"],
            }).first()
    except IntegrityError:
        return jsonify({"error": "breaker_id já existe ou violação de check"}), 409

    config_cache.refresh()
    return jsonify({"data": _serialize(row)}), 201


@safety_limits_bp.put("/<int:limit_id>")
def update_safety_limit(limit_id):
    data = request.get_json(silent=True) or {}
    errors = _validate(data, require_all=False)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    if not any(k in data for k in ("breaker_id", "nominal_current_a", "shed_threshold_pct", "restore_threshold_pct")):
        return jsonify({"error": "informe ao menos um campo para atualização"}), 400

    sets = ["updated_at = NOW()"]
    params = {"id": limit_id}
    for field in ("breaker_id", "nominal_current_a", "shed_threshold_pct", "restore_threshold_pct"):
        if field in data:
            value = data[field].strip() if field == "breaker_id" else data[field]
            sets.append(f"{field} = :{field}")
            params[field] = value

    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                text(f"""
                    UPDATE safety_limit SET {', '.join(sets)}
                    WHERE id = :id
                    RETURNING id, breaker_id, nominal_current_a, shed_threshold_pct, restore_threshold_pct
                """),
                params,
            ).first()
    except IntegrityError:
        return jsonify({"error": "violação de constraint (breaker_id duplicado ou check)"}), 409

    if row is None:
        return jsonify({"error": "limite não encontrado"}), 404

    config_cache.refresh()
    return jsonify({"data": _serialize(row)})


@safety_limits_bp.delete("/<int:limit_id>")
def delete_safety_limit(limit_id):
    with get_engine().begin() as conn:
        result = conn.execute(
            text("DELETE FROM safety_limit WHERE id = :id"),
            {"id": limit_id},
        )
    if result.rowcount == 0:
        return jsonify({"error": "limite não encontrado"}), 404
    config_cache.refresh()
    return "", 204
