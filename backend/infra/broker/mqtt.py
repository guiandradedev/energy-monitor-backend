import paho.mqtt.client as mqtt
import os
import re
from collections import deque
from datetime import datetime
from infra.database.postgres import get_engine, text
import hashlib
import struct

breaker_id = "1"

class MQTTClient:
    def __init__(self, broker_host='localhost', broker_port=1883, max_data_points=100):
        import uuid
        client_id = f"backend_mqtt_{uuid.uuid4().hex[:8]}"
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        
        self.data_points = deque(maxlen=max_data_points)
        self.callbacks = []
        self.last_message_hash = None
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.connect(broker_host, broker_port, 60)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected [{self.client_id}] with result code {reason_code}")
        client.unsubscribe("teste/esp")
        client.subscribe("teste/esp")
        print(f"Subscribed to teste/esp [{self.client_id}]")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"Disconnected with reason code {reason_code}")

    def on_message(self, client, userdata, msg):
        data = msg.payload
        message_hash = hashlib.md5(data).hexdigest()
        
        if message_hash == self.last_message_hash:
            return
        
        self.last_message_hash = message_hash
        print(f"Received raw data: {len(data)} bytes")
        
        struct_format = '<Iffff'
        struct_size = struct.calcsize(struct_format)
        
        data_points_list = []
        
        num_structs = len(data) // struct_size
        for i in range(num_structs):
            start = i * struct_size
            end = start + struct_size
            chunk = data[start:end]
            
            timestamp, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2 = struct.unpack(struct_format, chunk)
            
            data_point = {
                'timestamp': timestamp,
                'rms_sct1': rms_sct1,
                'rms_sct2': rms_sct2,
                'rms_zmpt1': rms_zmpt1,
                'rms_zmpt2': rms_zmpt2,
                'received_at': datetime.now().strftime('%H:%M:%S')
            }
            data_points_list.append(data_point)
            self.data_points.append(data_point)
            print(f"timestamp={timestamp}, sct1={rms_sct1:.3f}, sct2={rms_sct2:.3f}, zmpt1={rms_zmpt1:.3f}, zmpt2={rms_zmpt2:.3f}")
            
            for callback in self.callbacks:
                callback(data_point)

        with get_engine().connect() as conn:
            for dp in data_points_list:
                query = text("""
                    INSERT INTO breaker (timestamp, breaker_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2)
                    VALUES (CAST(:timestamp AS timestamp with time zone), :breaker_id, :rms_sct1, :rms_sct2, :rms_zmpt1, :rms_zmpt2)
                """)
                conn.execute(query, {
                    'timestamp': dp['timestamp'],
                    'breaker_id': breaker_id,
                    'rms_sct1': dp['rms_sct1'],
                    'rms_sct2': dp['rms_sct2'],
                    'rms_zmpt1': dp['rms_zmpt1'],
                    'rms_zmpt2': dp['rms_zmpt2']
                })
            print(f"Inserted {len(data_points_list)} data points into the database")
            conn.commit()

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def get_data(self):
        return list(self.data_points)

    def start(self):
        self.client.loop_forever()