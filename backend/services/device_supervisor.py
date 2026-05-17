"""Loop daemon que faz heartbeat (ping) das cargas cadastradas e marca offline
quem ficou sem responder por mais que `heartbeat_timeout_s`."""
import threading
from typing import Optional

from infra.database.postgres import get_engine, text
from services.config_cache import config_cache
from services.events import record_event


class DeviceSupervisor:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._mqtt_client = None

    def attach_mqtt_client(self, mqtt_client):
        self._mqtt_client = mqtt_client

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="device-supervisor",
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _loop(self):
        while not self._stop_event.is_set():
            interval = config_cache.get_parameter_int("heartbeat_interval_s", 30)
            try:
                self._tick()
            except Exception as exc:
                print(f"[device_supervisor] erro no tick: {exc}")
            if self._stop_event.wait(timeout=interval):
                return

    def _tick(self):
        timeout_s = config_cache.get_parameter_int("heartbeat_timeout_s", 90)

        # 1. Lista de dispositivos para pingar
        with get_engine().connect() as conn:
            devices = conn.execute(text(
                "SELECT id, device_id FROM device"
            )).fetchall()

        # 2. Pings (fora da transação para não segurar conexão durante IO)
        if self._mqtt_client is not None:
            for d in devices:
                try:
                    self._mqtt_client.publish_ping(d.device_id)
                except Exception as exc:
                    print(f"[device_supervisor] falha pingando {d.device_id}: {exc}")

        # 3. Marca offline quem está silencioso há mais que timeout
        with get_engine().begin() as conn:
            stale = conn.execute(text("""
                SELECT d.id AS device_pk, d.device_id, s.state, s.source, s.last_seen
                FROM device d
                JOIN device_state s ON d.id = s.device_id
                WHERE s.last_seen IS NOT NULL
                  AND s.last_seen < NOW() - make_interval(secs => :timeout)
                  AND (s.state <> 'off' OR s.source <> 'manual')
            """), {"timeout": timeout_s}).fetchall()

            for d in stale:
                conn.execute(text("""
                    UPDATE device_state
                    SET state = 'off', source = 'manual', last_changed_at = NOW()
                    WHERE device_id = :pk
                """), {"pk": d.device_pk})
                record_event(
                    "device_offline",
                    d.device_pk,
                    {
                        "prev_state": d.state,
                        "prev_source": d.source,
                        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                        "timeout_s": timeout_s,
                    },
                    conn=conn,
                )


device_supervisor = DeviceSupervisor()
