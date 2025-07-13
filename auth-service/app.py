
import json
import logging
import os
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, request
from kafka import KafkaProducer

# --- State for Failure Simulation ---
SHOULD_FAIL = False

# --- Kafka Producer Setup ---
kafka_broker = os.environ.get("KAFKA_BROKER")
producer = None
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=[kafka_broker],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 11, 5)
        )
    except Exception as e:
        logging.warning(f"Kafka not ready, retrying... Error: {e}")
        time.sleep(5)

# --- Logging Helper ---
def log_message(level, message, trace_id, duration_ms, status_code):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "serviceName": "auth-service",
        "traceId": trace_id,
        "message": message,
        "duration_ms": duration_ms,
        "statusCode": status_code,
        "endpoint": "/auth"
    }
    producer.send('service-logs', value=log_entry)
    producer.flush()
    print(f"Logged: {log_entry}")

# --- Flask App ---
app = Flask(__name__)

@app.route('/auth')
def authenticate():
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    if SHOULD_FAIL:
        log_message(
            "ERROR",
            "Authentication database connection failed.",
            trace_id,
            duration_ms=round((time.time() - start_time) * 1000),
            status_code=500
        )
        return jsonify({"error": "Internal Server Error"}), 500
    else:
        log_message(
            "INFO",
            "User authentication successful.",
            trace_id,
            duration_ms=round((time.time() - start_time) * 1000),
            status_code=200
        )
        return jsonify({"status": "Authenticated", "traceId": trace_id}), 200

@app.route('/fail', methods=['POST'])
def fail():
    """Endpoint to control the failure state of the service."""
    global SHOULD_FAIL
    data = request.get_json()
    fail_state = data.get('fail', False)
    SHOULD_FAIL = bool(fail_state)
    return jsonify({"status": f"Failure mode set to {SHOULD_FAIL}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)