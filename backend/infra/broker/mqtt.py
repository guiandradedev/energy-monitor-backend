import paho.mqtt.client as mqtt
import os

class MQTTClient:
    def __init__(self, broker_host='localhost', broker_port=1883):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        print("Setting MQTT credentials from environment variables...")
        print(os.getenv("MOSQUITTO_USERNAME"), os.getenv("MOSQUITTO_PASSWORD"))
        self.client.username_pw_set(os.getenv("MOSQUITTO_USERNAME"), os.getenv("MOSQUITTO_PASSWORD"))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(broker_host, broker_port, 60)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}")
        client.subscribe("teste/esp")

    def on_message(self, client, userdata, msg):
        print(f"Received: {msg.payload.decode()}")

    def start(self):
        self.client.loop_forever()