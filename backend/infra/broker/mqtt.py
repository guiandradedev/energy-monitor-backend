import hashlib
import json
import re
import struct
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from infra.database.postgres import get_engine, text
from services.events import record_event


BREAKER_TOPIC = "teste/esp"
CARGAS_HELLO_SUB = "cargas/+/hello"
CARGAS_STATE_SUB = "cargas/+/state"
CARGAS_PONG_SUB = "cargas/+/pong"

CARGAS_HELLO_RE = re.compile(r"^cargas/([^/]+)/hello$")
CARGAS_STATE_RE = re.compile(r"^cargas/([^/]+)/state$")
CARGAS_PONG_RE = re.compile(r"^cargas/([^/]+)/pong$")

BREAKER_ID = "1"
TELEMETRY_STRUCT = struct.Struct("<Iffff")

VALID_STATES = {"on", "off", "unknown"}
VALID_SOURCES = {"auto", "manual"}


class MQTTClient:
    def __init__(self, broker_host="localhost", broker_port=1883, max_data_points=100):
        self.client_id = f"backend_mqtt_{uuid.uuid4().hex[:8]}"
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        self.broker_host = broker_host
        self.broker_port = broker_port

        self.data_points = deque(maxlen=max_data_points)
        self.callbacks = []
        self.last_telemetry_hash: Optional[str] = None

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.connect(broker_host, broker_port, 60)

    # ---- lifecycle callbacks ----

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected [{self.client_id}] with result code {reason_code}")
        client.subscribe([
            (BREAKER_TOPIC, 0),
            (CARGAS_HELLO_SUB, 1),
            (CARGAS_STATE_SUB, 1),
            (CARGAS_PONG_SUB, 0),
        ])
        print(f"Subscribed [{self.client_id}]: {BREAKER_TOPIC}, cargas/+/{{hello,state,pong}}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"Disconnected [{self.client_id}] reason code {reason_code}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            if topic == BREAKER_TOPIC:
                self._handle_breaker(msg.payload)
                return
            m = CARGAS_HELLO_RE.match(topic)
            if m:
                self._handle_hello(m.group(1), msg.payload)
                return
            m = CARGAS_STATE_RE.match(topic)
            if m:
                self._handle_state(m.group(1), msg.payload)
                return
            m = CARGAS_PONG_RE.match(topic)
            if m:
                self._handle_pong(m.group(1), msg.payload)
                return
        except Exception as exc:
            print(f"[mqtt] erro processando {topic}: {exc}")

    # ---- telemetry handler (medidor) ----

    def _handle_breaker(self, payload: bytes):
        message_hash = hashlib.md5(payload).hexdigest()
        if message_hash == self.last_telemetry_hash:
            return
        self.last_telemetry_hash = message_hash

        struct_size = TELEMETRY_STRUCT.size
        num_structs = len(payload) // struct_size
        if num_structs == 0:
            return

        data_points_list = []
        for i in range(num_structs):
            chunk = payload[i * struct_size:(i + 1) * struct_size]
            unix_ts, sct1, sct2, zmpt1, zmpt2 = TELEMETRY_STRUCT.unpack(chunk)
            dp = {
                "timestamp": datetime.fromtimestamp(unix_ts),
                "unix_timestamp": unix_ts,
                "rms_sct1": sct1,
                "rms_sct2": sct2,
                "rms_zmpt1": zmpt1,
                "rms_zmpt2": zmpt2,
                "received_at": datetime.now().strftime("%H:%M:%S"),
            }
            data_points_list.append(dp)
            self.data_points.append(dp)
            for cb in self.callbacks:
                cb(dp)

        with get_engine().begin() as conn:
            for dp in data_points_list:
                conn.execute(text("""
                    INSERT INTO breaker (timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2)
                    VALUES (to_timestamp(:ts) AT TIME ZONE 'UTC', :breaker_id, :sct1, :sct2, :zmpt1, :zmpt2)
                """), {
                    "ts": dp["unix_timestamp"],
                    "breaker_id": BREAKER_ID,
                    "sct1": dp["rms_sct1"],
                    "sct2": dp["rms_sct2"],
                    "zmpt1": dp["rms_zmpt1"],
                    "zmpt2": dp["rms_zmpt2"],
                })
        print(f"[mqtt] breaker: {len(data_points_list)} pontos persistidos")

    # ---- carga handlers ----

    def _parse_json(self, payload: bytes):
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _handle_hello(self, device_id_str: str, payload: bytes):
        data = self._parse_json(payload) or {}
        state = data.get("state")
        if state not in VALID_STATES:
            state = "unknown"
        # Boot announcement → confiamos no dispositivo. Estado inicial vem como manual
        # (caso o device tenha sido ligado/religado pelo usuário ou venha de cold boot).
        self._apply_device_update(
            device_id_str,
            state=state,
            source="manual",
            extra_event="device_hello",
            payload_extra=data,
        )

    def _handle_state(self, device_id_str: str, payload: bytes):
        data = self._parse_json(payload) or {}
        state = data.get("state") if data.get("state") in VALID_STATES else None
        source = data.get("source") if data.get("source") in VALID_SOURCES else "manual"
        if state is None:
            return
        self._apply_device_update(
            device_id_str,
            state=state,
            source=source,
            extra_event=None,
            payload_extra=data,
        )

    def _handle_pong(self, device_id_str: str, payload: bytes):
        data = self._parse_json(payload) or {}
        state = data.get("state") if data.get("state") in VALID_STATES else None
        # Pong é primariamente heartbeat: bate last_seen; só atualiza estado se vier.
        self._apply_device_update(
            device_id_str,
            state=state,
            source=None,
            extra_event=None,
            payload_extra=None,
        )

    def _apply_device_update(
        self,
        device_id_str: str,
        state: Optional[str],
        source: Optional[str],
        extra_event: Optional[str],
        payload_extra: Optional[dict],
    ):
        with get_engine().begin() as conn:
            current = conn.execute(text("""
                SELECT d.id AS device_pk, s.state AS prev_state, s.source AS prev_source
                FROM device d
                LEFT JOIN device_state s ON d.id = s.device_id
                WHERE d.device_id = :did
            """), {"did": device_id_str}).first()

            if current is None:
                record_event(
                    "unknown_device",
                    None,
                    {"device_id": device_id_str, "trigger": extra_event or "message"},
                    conn=conn,
                )
                return

            pk = current.device_pk
            prev_state = current.prev_state
            prev_source = current.prev_source

            sets = ["last_seen = NOW()"]
            params = {"pk": pk}
            new_state = prev_state
            new_source = prev_source

            if state is not None:
                sets.append("state = :state")
                params["state"] = state
                new_state = state
                if state != prev_state:
                    sets.append("last_changed_at = NOW()")
            if source is not None:
                sets.append("source = :source")
                params["source"] = source
                new_source = source

            conn.execute(
                text(f"UPDATE device_state SET {', '.join(sets)} WHERE device_id = :pk"),
                params,
            )

            if state is not None and new_state != prev_state:
                record_event(
                    "device_state_changed",
                    pk,
                    {
                        "from": prev_state,
                        "to": new_state,
                        "source": new_source,
                        "trigger": extra_event or "state_msg",
                    },
                    conn=conn,
                )

            if extra_event == "device_hello":
                record_event("device_hello", pk, payload_extra, conn=conn)

    # ---- publishers ----

    def publish_cmd(self, device_id_str: str, action: str, reason: str = "manual"):
        if action not in ("on", "off"):
            raise ValueError(f"action inválido: {action}")
        req_id = uuid.uuid4().hex
        payload = json.dumps({
            "action": action,
            "reason": reason,
            "req_id": req_id,
            "ts": int(datetime.now(timezone.utc).timestamp()),
        })
        info = self.client.publish(f"cargas/{device_id_str}/cmd", payload, qos=1)
        return req_id, info.rc

    def publish_ping(self, device_id_str: str):
        req_id = uuid.uuid4().hex
        payload = json.dumps({
            "req_id": req_id,
            "ts": int(datetime.now(timezone.utc).timestamp()),
        })
        info = self.client.publish(f"cargas/{device_id_str}/ping", payload, qos=0)
        return req_id, info.rc

    # ---- compat (telemetria) ----

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def get_data(self):
        return list(self.data_points)

    def start(self):
        self.client.loop_forever()


# ---- singleton ----

_instance: Optional[MQTTClient] = None


def get_mqtt_client() -> MQTTClient:
    global _instance
    if _instance is None:
        _instance = MQTTClient()
    return _instance
