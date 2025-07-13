import streamlit as st
import requests
import os
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="Aegis Observability Platform",
    layout="wide"
)

# --- Environment Variables ---
AGENT_API_URL = os.environ.get("AGENT_API_URL", "http://localhost:8000")

# --- UI Components ---
st.title("Aegis: AI-Powered Observability Platform")
st.markdown("This dashboard allows you to simulate failures in a microservice environment and use an AI agent to perform automated root-cause analysis.")

st.sidebar.header("Grafana Dashboard")
st.sidebar.markdown("[View Live System Metrics](http://localhost:3000)", unsafe_allow_html=True)

st.sidebar.header("Service Endpoints")
st.sidebar.markdown("Visit these endpoints to generate logs:")
st.sidebar.markdown("- [Auth Service (Normal)](http://localhost:5001/auth)")
st.sidebar.markdown("- [Payment Service (Normal)](http://localhost:5002/charge)")


# --- Failure Simulation ---
st.header("1. Simulate a Failure")
col1, col2 = st.columns(2)

with col1:
    if st.button("Inject Failure into Auth Service"):
        try:
            response = requests.post("http://localhost:5001/fail", json={"fail": True})
            if response.status_code == 200:
                st.success("Failure injection signal sent to auth-service.")
            else:
                st.error(f"Failed to send signal: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Error connecting to auth-service: {e}")

with col2:
    if st.button("Restore Auth Service"):
        try:
            response = requests.post("http://localhost:5001/fail", json={"fail": False})
            if response.status_code == 200:
                st.success("Restoration signal sent to auth-service.")
            else:
                st.error(f"Failed to send signal: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Error connecting to auth-service: {e}")

st.markdown("---")


# --- AI Analysis ---
st.header("2. Perform AI Analysis")

# Root Cause Analysis
st.subheader("Root Cause Analysis (RCA)")
trace_id_input = st.text_input("Enter a Trace ID from a failed transaction to analyze:", "")
if st.button("Analyze Root Cause"):
    if trace_id_input:
        with st.spinner("AI Agent is analyzing the trace..."):
            try:
                response = requests.post(f"{AGENT_API_URL}/analyze/root-cause", json={"traceId": trace_id_input})
                if response.status_code == 200:
                    result = response.json()
                    st.markdown("**AI Agent Report:**")
                    st.info(result.get("summary", "No summary available."))
                    with st.expander("View Raw Analysis"):
                        st.json(result.get("raw_analysis"))
                else:
                    st.error(f"Analysis failed: {response.json().get('error', response.text)}")
            except requests.exceptions.RequestException as e:
                st.error(f"Error connecting to the agent service: {e}")
    else:
        st.warning("Please enter a Trace ID.")

# Blast Radius Analysis
st.subheader("Blast Radius Analysis")
service_name_input = st.selectbox("Select a service to analyze its failure impact:", ["auth-service", "payment-service"])
if st.button("Analyze Blast Radius"):
    with st.spinner("AI Agent is analyzing the service dependencies..."):
        try:
            response = requests.post(f"{AGENT_API_URL}/analyze/blast-radius", json={"serviceName": service_name_input})
            if response.status_code == 200:
                result = response.json()
                st.markdown("**AI Agent Report:**")
                st.info(result.get("summary", "No summary available."))
                with st.expander("View Raw Analysis"):
                    st.json(result.get("raw_analysis"))
            else:
                st.error(f"Analysis failed: {response.json().get('error', response.text)}")
        except requests.exceptions.RequestException as e:
            st.error(f"Error connecting to the agent service: {e}")