
import json
import os
import time
import logging
from flask import Flask, request, jsonify
from neo4j import GraphDatabase

# --- Environment Variables ---
NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USER")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

# --- Neo4j Connection ---
neo4j_driver = None
while neo4j_driver is None:
    try:
        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        neo4j_driver.verify_connectivity()
        print("Agent successfully connected to Neo4j")
    except Exception as e:
        logging.error(f"Agent could not connect to Neo4j, retrying... Error: {e}")
        time.sleep(5)

# --- Core Agent Functions ---
def find_root_cause(tx, trace_id):
    """Finds the first error event in a given trace."""
    query = """
    MATCH (t:Trace {id: $traceId})<-[:PART_OF]-(l:LogEvent)
    RETURN l.message as message, l.timestamp as timestamp
    ORDER BY l.timestamp
    LIMIT 1
    """
    result = tx.run(query, traceId=trace_id)
    return result.single()

def find_blast_radius(tx, service_name):
    """Finds all services that depend on a given service."""
    query = """
    MATCH (s:Service {name: $serviceName})<-[:DEPENDS_ON*]-(downstream:Service)
    RETURN collect(distinct downstream.name) as impacted_services
    """
    result = tx.run(query, serviceName=service_name)
    return result.single()

async def get_llm_summary(analysis_text):
    """Uses Gemini to summarize the findings."""
    prompt = f"""
    You are an expert Site Reliability Engineer. Based on the following technical analysis, 
    write a concise and clear root-cause analysis report for a busy engineering manager.
    
    Analysis:
    {analysis_text}
    
    Report:
    """
    try:
        chatHistory = [{"role": "user", "parts": [{"text": prompt}]}]
        payload = {"contents": chatHistory}
        apiKey = "" # API key is optional for gemini-2.0-flash
        apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={apiKey}"
        
        response = await fetch(apiUrl, {
            'method': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(payload)
        })
        
        result = await response.json()
        
        if result.get("candidates"):
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "Could not generate a summary. The raw analysis is provided above."
    except Exception as e:
        logging.error(f"LLM API call failed: {e}")
        return f"Could not generate a summary due to an error. The raw analysis is provided above. Error: {e}"

# --- Flask API ---
app = Flask(__name__)

@app.route('/analyze/root-cause', methods=['POST'])
async def analyze_root_cause_endpoint():
    data = request.get_json()
    trace_id = data.get('traceId')
    if not trace_id:
        return jsonify({"error": "traceId is required"}), 400

    with neo4j_driver.session() as session:
        record = session.read_transaction(find_root_cause, trace_id)
    
    if record:
        raw_analysis = f"Root cause analysis for trace {trace_id} points to the earliest error: '{record['message']}' at {record['timestamp']}."
        summary = await get_llm_summary(raw_analysis)
        return jsonify({"summary": summary, "raw_analysis": raw_analysis})
    else:
        return jsonify({"summary": f"No root cause found for trace {trace_id}. The trace may not contain any error-level LogEvents."}), 404

@app.route('/analyze/blast-radius', methods=['POST'])
async def analyze_blast_radius_endpoint():
    data = request.get_json()
    service_name = data.get('serviceName')
    if not service_name:
        return jsonify({"error": "serviceName is required"}), 400

    with neo4j_driver.session() as session:
        record = session.read_transaction(find_blast_radius, service_name)
        
    if record and record['impacted_services']:
        raw_analysis = f"A failure in '{service_name}' is likely to impact the following downstream services: {', '.join(record['impacted_services'])}."
        summary = await get_llm_summary(raw_analysis)
        return jsonify({"summary": summary, "raw_analysis": raw_analysis})
    else:
        return jsonify({"summary": f"No downstream services depend on '{service_name}'."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)  