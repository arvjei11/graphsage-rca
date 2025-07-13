import json
import logging
import os
import time
import uuid
from datetime import datetime
import requests

from flask import Flask, jsonify
from kafka import KafkaProducer

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
        "serviceName": "payment-service",
        "traceId": trace_id,
        "message": message,
        "duration_ms": duration_ms,
        "statusCode": status_code,
        "endpoint": "/charge"
    }
    producer.send('service-logs', value=log_entry)
    producer.flush()
    print(f"Logged: {log_entry}")

# --- Flask App ---
app = Flask(__name__)

@app.route('/charge')
def charge():
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    # This service now calls the auth-service, creating a dependency
    try:
        auth_response = requests.get("http://auth-service:5000/auth", timeout=5)
        if auth_response.status_code != 200:
            raise Exception("Authentication service failed.")
        
        # If authentication is successful, proceed with payment
        log_message("INFO", "Payment processed successfully.", trace_id, round((time.time() - start_time) * 1000), 200)
        return jsonify({"status": "Payment Successful", "traceId": trace_id}), 200
        
    except Exception as e:
        # If authentication fails, this service also fails
        log_message("ERROR", f"Payment failed due to auth dependency error: {e}", trace_id, round((time.time() - start_time) * 1000), 503)
        return jsonify({"error": "Downstream service unavailable"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)