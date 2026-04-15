import paho.mqtt.client as mqtt
import os
import struct
from collections import deque
from datetime import datetime

class MQTTClient:
    def __init__(self, broker_host='localhost', broker_port=1883, max_data_points=100):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Data storage for real-time chart
        self.data_points = deque(maxlen=max_data_points)
        self.callbacks = []
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(broker_host, broker_port, 60)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}")
        client.subscribe("teste/esp")

    def on_message(self, client, userdata, msg):
        data = msg.payload
        
        # Format: timestamp (I), rms_sct1 (f), rms_sct2 (f), rms_zmpt1 (f), rms_zmpt2 (f)
        struct_format = '<Iffff'
        struct_size = struct.calcsize(struct_format)
        
        # Parse all structs in the payload
        num_structs = len(data) // struct_size
        for i in range(num_structs):
            start = i * struct_size
            end = start + struct_size
            chunk = data[start:end]
            
            timestamp, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2 = struct.unpack(struct_format, chunk)
            
            # Store data point
            data_point = {
                'timestamp': timestamp,
                'rms_sct1': rms_sct1,
                'rms_sct2': rms_sct2,
                'rms_zmpt1': rms_zmpt1,
                'rms_zmpt2': rms_zmpt2,
                'received_at': datetime.now().strftime('%H:%M:%S')
            }
            self.data_points.append(data_point)
            print(f"Received: timestamp={timestamp}, sct1={rms_sct1:.3f}, sct2={rms_sct2:.3f}, zmpt1={rms_zmpt1:.3f}, zmpt2={rms_zmpt2:.3f}")
            
            # Notify all callbacks
            for callback in self.callbacks:
                callback(data_point)

    def register_callback(self, callback):
        """Register a callback to be called when new data arrives"""
        self.callbacks.append(callback)

    def get_data(self):
        """Get all stored data points"""
        return list(self.data_points)

    def start(self):
        self.client.loop_forever()