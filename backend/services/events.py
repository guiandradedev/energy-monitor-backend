"""Helper para registrar eventos do mecanismo (shedding, restore, lifecycle de carga, etc)."""
import json
from typing import Optional

from infra.database.postgres import get_engine, text


def record_event(
    event_type: str,
    device_id: Optional[int] = None,
    payload: Optional[dict] = None,
    conn=None,
):
    """Insere uma linha em `event`. Se `conn` for fornecido, participa da transação corrente;
    caso contrário, abre uma transação própria."""
    sql = text("""
        INSERT INTO event (type, device_id, payload)
        VALUES (:type, :device_id, CAST(:payload AS jsonb))
    """)
    params = {
        "type": event_type,
        "device_id": device_id,
        "payload": json.dumps(payload) if payload is not None else None,
    }
    if conn is not None:
        conn.execute(sql, params)
        return
    with get_engine().begin() as c:
        c.execute(sql, params)
