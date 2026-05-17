from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, Response, request
from flask_cors import CORS
import threading
import json
from infra.broker.mqtt import get_mqtt_client
import queue
import os
from infra.database.postgres import get_engine, text
from services.config_cache import config_cache
from services.device_supervisor import device_supervisor
from infra.http.priorities import priorities_bp
from infra.http.devices import devices_bp
from infra.http.safety_limits import safety_limits_bp
from infra.http.parameters import parameters_bp
from infra.http.events import events_bp
from infra.http.telemetry import telemetry_bp

app = Flask(__name__)
CORS(app)

# Bootstrap síncrono do cache + thread de refresh periódico
config_cache.start()

app.register_blueprint(priorities_bp)
app.register_blueprint(devices_bp)
app.register_blueprint(safety_limits_bp)
app.register_blueprint(parameters_bp)
app.register_blueprint(events_bp)
app.register_blueprint(telemetry_bp)

# Queue for server-sent events
data_queue = queue.Queue()

# Initialize MQTT client (singleton)
mqtt_client = get_mqtt_client()

def mqtt_data_callback(data_point):
    """Callback when MQTT receives new data"""
    data_queue.put(data_point)

mqtt_client.register_callback(mqtt_data_callback)

# Start MQTT client in a separate thread
mqtt_thread = threading.Thread(target=mqtt_client.start, daemon=True)
mqtt_thread.start()

# Supervisor de cargas (heartbeat + offline detection)
device_supervisor.attach_mqtt_client(mqtt_client)
device_supervisor.start()

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

@app.route('/api/data/<int:breaker_id>')
def get_data(breaker_id):
    """API endpoint to get data points with configurable grouping"""
    group = request.args.get('group', '24h')  # Default to 24h
    
    # Define time interval and grouping unit based on group parameter
    group_config = {
        '24h': {'interval': "INTERVAL '24 hours'", 'trunc': 'hour'},
        '7d': {'interval': "INTERVAL '7 days'", 'trunc': 'hour'},
        '30d': {'interval': "INTERVAL '30 days'", 'trunc': 'day'},
        '3m': {'interval': "INTERVAL '3 months'", 'trunc': 'day'},
        '6m': {'interval': "INTERVAL '6 months'", 'trunc': 'week'},
        '1y': {'interval': "INTERVAL '1 year'", 'trunc': 'month'},
        '2y': {'interval': "INTERVAL '2 years'", 'trunc': 'month'},
        'at': {'interval': "INTERVAL '100 years'", 'trunc': 'month'}  # All time approximation
    }
    
    # Use default config if invalid group parameter
    config = group_config.get(group, group_config['24h'])
    interval = config['interval']
    trunc_unit = config['trunc']
    
    query = text(f"""
        SELECT 
            DATE_TRUNC('{trunc_unit}', timestamp) as timestamp,
            breaker_id,
            AVG(rms_sct1) as rms_sct1,
            AVG(rms_sct2) as rms_sct2,
            AVG(rms_zmpt1) as rms_zmpt1,
            AVG(rms_zmpt2) as rms_zmpt2
        FROM breaker
        WHERE timestamp >= NOW() - {interval} AND breaker_id = CAST(:breaker_id AS text)
        GROUP BY DATE_TRUNC('{trunc_unit}', timestamp), breaker_id
        ORDER BY timestamp DESC
    """)
    
    with get_engine().connect() as conn:
        result = conn.execute(query, {'breaker_id': breaker_id}).fetchall()
        data = []
        for row in result:
            data.append({
                'timestamp': str(row.timestamp),
                'breaker_id': row.breaker_id,
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
