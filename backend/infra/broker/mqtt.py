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
 
        size = struct.calcsize('<f')
        for i in range(len(data)//size):
            chunk = data[i*size:(i+1)*size]
            current, = struct.unpack('<f', chunk)
            
            # Store data point
            data_point = {
                'value': current,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            self.data_points.append(data_point)
            print(f"Received: {current}")
            
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