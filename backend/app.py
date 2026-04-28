from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, Response
from flask_cors import CORS
import threading
import json
from infra.broker.mqtt import MQTTClient
import queue
import os
from infra.database.postgres import get_engine, text

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

@app.route('/api/initial-data')
def get_initial_data():
    """Serve the main dashboard page"""
    return {
        'data': mqtt_client.get_data()
    }

@app.route('/api/data')
def get_data():
    """API endpoint to get all data points"""
    query = text("""
        SELECT created_at, device_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2
        FROM breaker
        ORDER BY created_at DESC
    """)
    with get_engine().connect() as conn:
        result = conn.execute(query)
        data = []
        for row in result:
            data.append({
                'created_at': str(row.created_at),
                'device_id': row.device_id,
                'rms_sct1': float(row.rms_sct1),
                'rms_sct2': float(row.rms_sct2),
                'rms_zmpt1': float(row.rms_zmpt1),
                'rms_zmpt2': float(row.rms_zmpt2)
            })
    return {'data': data}

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes')
    
    # Disable Flask reloader to prevent multiple MQTT client instances
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)
