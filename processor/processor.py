
import json
import logging
import os
import time

import redis
from elasticsearch import Elasticsearch
from kafka import KafkaConsumer

# --- Environment Variables ---
KAFKA_BROKER = os.environ.get("KAFKA_BROKER")
ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST")
REDIS_HOST = os.environ.get("REDIS_HOST")
KAFKA_TOPIC = 'service-logs'
ELASTIC_INDEX = 'service-logs-index'

# --- Elasticsearch Connection ---
es_client = None
while es_client is None:
    try:
        es_client = Elasticsearch(
            hosts=[{"host": ELASTICSEARCH_HOST, "port": 9200, "scheme": "http"}]
        )
        if not es_client.ping():
             raise ConnectionError("Elasticsearch not available")
        print("Successfully connected to Elasticsearch")
    except Exception as e:
        logging.error(f"Could not connect to Elasticsearch, retrying... Error: {e}")
        time.sleep(5)

# --- Redis Connection ---
redis_client = None
while redis_client is None:
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0)
        if not redis_client.ping():
            raise ConnectionError("Redis not available")
        print("Successfully connected to Redis")
    except Exception as e:
        logging.error(f"Could not connect to Redis, retrying... Error: {e}")
        time.sleep(5)

# --- Kafka Consumer ---
consumer = None
while consumer is None:
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='earliest',
            group_id='log-processor-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            api_version=(0, 11, 5)
        )
        print("Successfully connected to Kafka")
    except Exception as e:
        logging.error(f"Could not connect to Kafka, retrying... Error: {e}")
        time.sleep(5)

# --- Main Processing Loop ---
print("Starting log processing...")
for message in consumer:
    log_data = message.value
    
    # 1. Index the raw log to Elasticsearch
    try:
        es_client.index(index=ELASTIC_INDEX, document=log_data)
        print(f"Indexed log to Elasticsearch: {log_data['traceId']}")
    except Exception as e:
        logging.error(f"Failed to index log to Elasticsearch. Error: {e}")

    # 2. Process and store metrics in Redis
    try:
        service_name = log_data.get("serviceName", "unknown-service")
        status_code = log_data.get("statusCode", 0)

        # Increment total request count for the service
        redis_client.incr(f"metrics:{service_name}:total_requests")

        # Increment error count if status code is 400 or higher
        if status_code >= 400:
            redis_client.incr(f"metrics:{service_name}:error_count")
        
        print(f"Processed metrics for {service_name}")
            
    except Exception as e:
        logging.error(f"Failed to process metrics for Redis. Error: {e}")