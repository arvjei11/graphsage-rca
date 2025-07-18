import json
import logging
import os
import time
import uuid
import redis
from elasticsearch import Elasticsearch
from kafka import KafkaConsumer
from neo4j import GraphDatabase

# --- Environment Variables ---
KAFKA_BROKER = os.environ.get("KAFKA_BROKER")
ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST")
REDIS_HOST = os.environ.get("REDIS_HOST")
NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USER")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")
KAFKA_TOPIC = 'service-logs'
ELASTIC_INDEX = 'service-logs-index'

# --- Elasticsearch Connection ---
es_client = None
while es_client is None:
    try:
        es_client = Elasticsearch(hosts=[{"host": ELASTICSEARCH_HOST, "port": 9200, "scheme": "http"}])
        if not es_client.ping(): raise ConnectionError("Elasticsearch not available")
        print("Successfully connected to Elasticsearch")
    except Exception as e:
        logging.error(f"Could not connect to Elasticsearch, retrying... Error: {e}")
        time.sleep(5)
redis_client = None
while redis_client is None:
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0)
        if not redis_client.ping(): raise ConnectionError("Redis not available")
        print("Successfully connected to Redis")
    except Exception as e:
        logging.error(f"Could not connect to Redis, retrying... Error: {e}")
        time.sleep(5)
neo4j_driver = None
while neo4j_driver is None:
    try:
        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        neo4j_driver.verify_connectivity()
        print("Successfully connected to Neo4j")
    except Exception as e:
        logging.error(f"Could not connect to Neo4j, retrying... Error: {e}")
        time.sleep(5)
consumer = None
while consumer is None:
    try:
        consumer = KafkaConsumer(KAFKA_TOPIC, bootstrap_servers=[KAFKA_BROKER], auto_offset_reset='earliest', group_id='log-processor-group', value_deserializer=lambda x: json.loads(x.decode('utf-8')), api_version=(0, 11, 5))
        print("Successfully connected to Kafka")
    except Exception as e:
        logging.error(f"Could not connect to Kafka, retrying... Error: {e}")
        time.sleep(5)

# --- Graph Setup ---
def setup_initial_graph(driver):
    with driver.session() as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Trace) REQUIRE t.id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:LogEvent) REQUIRE l.id IS UNIQUE")
        session.run("""
            MERGE (p:Service {name: 'payment-service'})
            MERGE (a:Service {name: 'auth-service'})
            MERGE (p)-[:DEPENDS_ON]->(a)
        """)
        print("Initial graph setup complete.")
setup_initial_graph(neo4j_driver)

# --- Main Loop ---
print("Starting log processing...")
for message in consumer:
    log_data = message.value
    # 1. Index to ES
    try:
        es_client.index(index=ELASTIC_INDEX, document=log_data)
        print(f"Indexed log to Elasticsearch: {log_data['traceId']}")
    except Exception as e:
        logging.error(f"Failed to index log to Elasticsearch. Error: {e}")
    # 2. Process Redis metrics
    try:
        service_name = log_data.get("serviceName", "unknown-service")
        status_code = log_data.get("statusCode", 0)
        redis_client.incr(f"metrics:{service_name}:total_requests")
        if status_code >= 400:
            redis_client.incr(f"metrics:{service_name}:error_count")
        print(f"Processed metrics for {service_name}")
    except Exception as e:
        logging.error(f"Failed to process metrics for Redis. Error: {e}")
    # 3. Update Neo4j graph
    try:
        service_name = log_data.get("serviceName")
        trace_id = log_data.get("traceId")
        level = log_data.get("level")
        
        if service_name and trace_id:
            with neo4j_driver.session() as session:
                # Always create the service and trace nodes
                session.run("""
                    MERGE (s:Service {name: $serviceName})
                    MERGE (t:Trace {id: $traceId})
                    MERGE (t)-[:PASSED_THROUGH]->(s)
                """, serviceName=service_name, traceId=trace_id)
                
                # If the log is an error, create a specific LogEvent node
                if level == "ERROR":
                    log_id = str(uuid.uuid4())
                    session.run("""
                        MATCH (t:Trace {id: $traceId})
                        CREATE (l:LogEvent {
                            id: $logId, 
                            message: $message, 
                            timestamp: $timestamp
                        })
                        MERGE (l)-[:PART_OF]->(t)
                    """, traceId=trace_id, logId=log_id, message=log_data.get("message"), timestamp=log_data.get("timestamp"))
                print(f"Updated graph for trace: {trace_id}")
    except Exception as e:
        logging.error(f"Failed to update Neo4j graph. Error: {e}")
neo4j_driver.close()