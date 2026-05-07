from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, Response, request
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
