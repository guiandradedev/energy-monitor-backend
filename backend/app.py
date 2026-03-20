from flask import Flask, render_template, Response
from flask_cors import CORS
import threading
import json
from infra.broker.mqtt import MQTTClient
import queue
import os

app = Flask(__name__)
CORS(app)

# Queue for server-sent events
data_queue = queue.Queue()

# Initialize MQTT client
mqtt_client = MQTTClient()

def mqtt_data_callback(data_point):
    """Callback when MQTT receives new data"""
    data_queue.put(data_point)

# Register the callback
mqtt_client.register_callback(mqtt_data_callback)

# Start MQTT client in a separate thread
mqtt_thread = threading.Thread(target=mqtt_client.start, daemon=True)
mqtt_thread.start()

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/data')
def get_initial_data():
    """Get initial data points"""
    return {
        'data': mqtt_client.get_data()
    }

@app.route('/api/stream')
def stream():
    """Server-sent events endpoint for real-time updates"""
    def event_generator():
        while True:
            try:
                data_point = data_queue.get(timeout=1)
                yield f"data: {json.dumps(data_point)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"
    
    return Response(event_generator(), mimetype="text/event-stream")

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes')
    
    app.run(host=host, port=port, debug=debug, threaded=True)
