"""Simulador simples de ESP de carga. Publica hello no boot, responde a ping e cmd.

Uso:
    python scripts/mock_device.py AA:BB:CC:DD:EE:01 [inicial_on|off]

Variáveis de ambiente:
    MQTT_HOST (default localhost), MQTT_PORT (default 1883).
"""
import json
import os
import sys
import time
import uuid

import paho.mqtt.client as mqtt


DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "AA:BB:CC:DD:EE:01"
INITIAL_STATE = sys.argv[2] if len(sys.argv) > 2 else "on"
BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))

state = {"value": INITIAL_STATE if INITIAL_STATE in ("on", "off") else "on"}


def now():
    return int(time.time())


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[mock {DEVICE_ID}] connected rc={reason_code}")
    client.publish(
        f"cargas/{DEVICE_ID}/hello",
        json.dumps({
            "device_id": DEVICE_ID,
            "fw": "0.0.1-mock",
            "state": state["value"],
            "ts": now(),
        }),
        qos=1,
    )
    client.subscribe(f"cargas/{DEVICE_ID}/cmd", qos=1)
    client.subscribe(f"cargas/{DEVICE_ID}/ping", qos=0)
    print(f"[mock {DEVICE_ID}] subscribed cmd + ping, state={state['value']}")


def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"[mock {DEVICE_ID}] payload inválido em {topic}")
        return

    if topic.endswith("/cmd"):
        action = payload.get("action")
        reason = payload.get("reason")
        req_id = payload.get("req_id")
        if action in ("on", "off"):
            state["value"] = action
            source = "auto" if reason in ("load_shedding", "restore") else "manual"
            print(f"[mock {DEVICE_ID}] cmd {action} (reason={reason}) -> state={action}, source={source}")
            client.publish(
                f"cargas/{DEVICE_ID}/state",
                json.dumps({
                    "state": state["value"],
                    "source": source,
                    "req_id": req_id,
                    "ts": now(),
                }),
                qos=1,
            )
        else:
            print(f"[mock {DEVICE_ID}] cmd com action inválido: {action}")
    elif topic.endswith("/ping"):
        client.publish(
            f"cargas/{DEVICE_ID}/pong",
            json.dumps({
                "req_id": payload.get("req_id"),
                "state": state["value"],
                "ts": now(),
            }),
            qos=0,
        )


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"mock_{DEVICE_ID}_{uuid.uuid4().hex[:4]}",
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
