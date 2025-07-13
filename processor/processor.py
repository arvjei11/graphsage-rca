
import json
import logging
import os
import time

from elasticsearch import Elasticsearch
from kafka import KafkaConsumer

# --- Environment Variables ---
KAFKA_BROKER = os.environ.get("KAFKA_BROKER")
ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST")
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
    try:
        # Index the document into Elasticsearch
        es_client.index(index=ELASTIC_INDEX, document=log_data)
        print(f"Indexed log to Elasticsearch: {log_data['traceId']}")
    except Exception as e:
        logging.error(f"Failed to index log to Elasticsearch. Error: {e}")
        logging.error(f"Log data: {log_data}")