import os

from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from store.json_store import JSONMetricStore
from charts.pie import create_pie
from charts.trend import create_trend
from charts.bar import create_bar
from nlp.intent import detect_plot_request, detect_harness_query
from nlp.metric_extractor import extract_metric_from_query
from datetime import datetime

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Debug – confirm correct file
st.error("RUNNING FILE: " + os.path.abspath(__file__) + "New Format 1")

# Add custom CSS for fixed header/footer and visible sidebar
st.markdown("""
    <style>
    /* Hide Streamlit's default footer */
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Ensure sidebar is visible and always open */
    section[data-testid="stSidebar"] {
        visibility: visible !important;
        display: block !important;
        transform: translateX(0) !important;
    }
    
    /* Make sidebar toggle always visible */
    button[kind="header"] {
        visibility: visible !important;
        display: block !important;
    }
    
    /* Force sidebar open state */
    .stApp[data-sidebar-state] section[data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
    }
    
    /* Fixed header - use more specific selectors */
    .main .block-container > div[data-testid="stVerticalBlock"]:first-of-type,
    .main .block-container > div[data-testid="stVerticalBlock"]:nth-of-type(2),
    .main .block-container > div[data-testid="stVerticalBlock"]:nth-of-type(3),
    .main .block-container > div[data-testid="stVerticalBlock"]:nth-of-type(4) {
        position: -webkit-sticky !important;
        position: sticky !important;
        top: 0 !important;
        background-color: white !important;
        background: white !important;
        z-index: 999 !important;
        padding: 0.5rem 0 !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Add shadow to header area */
    .main .block-container > div[data-testid="stVerticalBlock"]:first-of-type {
        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
        padding-bottom: 1rem !important;
        margin-bottom: 1rem !important;
    }
    
    /* Fixed footer - target last block */
    .main .block-container > div[data-testid="stVerticalBlock"]:last-of-type {
        position: -webkit-sticky !important;
        position: sticky !important;
        bottom: 0 !important;
        background-color: white !important;
        background: white !important;
        z-index: 999 !important;
        padding: 1rem 0 !important;
        margin-top: 1rem !important;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.15) !important;
    }
    
    /* Ensure input fields and chat input are always interactive */
    input[type="text"],
    input[data-testid*="chat"],
    div[data-testid="stChatInput"] {
        pointer-events: auto !important;
        z-index: 1000 !important;
    }
    
    /* Ensure sticky footer doesn't block interactions */
    .main .block-container > div[data-testid="stVerticalBlock"]:last-of-type,
    .main .block-container > div[data-testid="stVerticalBlock"]:last-of-type * {
        pointer-events: auto !important;
    }
    
    /* Chat input container */
    div[data-testid="stChatInput"] {
        position: sticky !important;
        bottom: 0 !important;
        background: white !important;
        z-index: 1000 !important;
        padding: 1rem 0 !important;
    }
    
    /* Add padding to content area */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------- SIDEBAR: AI CONFIGURATION ---------------------- #
with st.sidebar:
    st.markdown("## 🤖 AI Configuration")
    
    ai_provider = st.selectbox("Provider", ["gemini", "claude", "openai"], index=0, key="ai_provider")
    
    if ai_provider == "claude":
        api_key = st.text_input("Claude API Key", type="password", key="claude_key")
        model = st.selectbox("Model", ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"], key="claude_model")
    elif ai_provider == "openai":
        api_key = st.text_input("OpenAI API Key", type="password", key="openai_key")
        model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o"], key="openai_model")
    else:
        api_key = None
        model = st.selectbox("Model", ["gemini-2.5-flash-lite", "gemini-1.5-pro"], key="gemini_model")

# ---------------------- HEADER ---------------------- #
st.markdown("## 🧠 N.E.D – Neural Executive Dashboard")

# Week selector in header

GCS_METRICS_URI = "gs://oneid-media-dev/Lucky/TrialJsonFormat/read.json"
store = JSONMetricStore(gcs_uri=GCS_METRICS_URI)
RAW_WEEKLY = store.group_by_week()

def pretty_week(w):
    return "Week of " + datetime.strptime(w, "%Y-%m-%d").strftime("%d-%m-%Y")

pretty_map = {pretty_week(w): w for w in RAW_WEEKLY.keys()}
selected_pretty = st.selectbox("📅 Select Week", list(pretty_map.keys()), key="week_selector")
selected_week = pretty_map[selected_pretty]

# Buttons in header
c1, c2, c3 = st.columns(3)
with c1:
    st.button("Executive Snapshot", key="btn_snapshot")
with c2:
    st.button("System Alerts", key="btn_alerts")
with c3:
    st.button("Key Performance Metrics", key="btn_metrics")

# ------------------ SESSION STATE --------------------- #
if "chart_fig" not in st.session_state:
    st.session_state.chart_fig = None

# Initialize conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------ DATA ANALYSIS FUNCTION --------------------- #
def analyze_data_query(query, selected_week, weekly_data):
    """
    Analyze data based on user query and return filtered results.
    """
    import re
    query_lower = query.lower()
    
    # Check if query is asking about which week metric(s) changed
    if "which week" in query_lower and ("increased" in query_lower or "increase" in query_lower or "decreased" in query_lower or "decrease" in query_lower):
        # Extract all metric conditions from query
        available_metrics = ['maid', 'gravy', 'cookie', 'dig']
        conditions = []  # List of (metric, condition) tuples where condition is 'increased' or 'decreased'
        
        # Split query by common conjunctions
        parts = re.split(r'\s+(but|and|,)\s+', query_lower)
        
        for part in parts:
            part = part.strip()
            # Check for each metric
            for metric in available_metrics:
                if metric in part:
                    # Determine condition
                    if "increased" in part or "increase" in part:
                        conditions.append((metric, "increased"))
                    elif "decreased" in part or "decrease" in part:
                        conditions.append((metric, "decreased"))
                    break
        
        # If no conditions found, try simple pattern (single metric)
        if not conditions:
            for metric in available_metrics:
                if metric in query_lower:
                    if "increased" in query_lower or "increase" in query_lower:
                        conditions.append((metric, "increased"))
                    elif "decreased" in query_lower or "decrease" in query_lower:
                        conditions.append((metric, "decreased"))
                    break
        
        if not conditions:
            return "Could not identify metrics and conditions. Please specify metrics (maid, gravy, cookie, dig) and whether they increased or decreased."
        
        # Find weeks where all conditions are met
        matching_weeks = []
        for week, week_data in weekly_data.items():
            week_metrics = {m["metric"].lower(): m for m in week_data}
            all_conditions_met = True
            week_details = {"week": week, "metrics": {}}
            
            for metric_name, condition in conditions:
                # Find the metric data for this metric name
                metric_data = None
                for metric_key, metric_value in week_metrics.items():
                    if metric_name in metric_key:
                        metric_data = metric_value
                        break
                
                if not metric_data:
                    all_conditions_met = False
                    break
                
                # Check condition
                current = metric_data.get("current", 0)
                previous = metric_data.get("previous", 0)
                
                if condition == "increased":
                    if current <= previous:
                        all_conditions_met = False
                        break
                    change = current - previous
                else:  # decreased
                    if current >= previous:
                        all_conditions_met = False
                        break
                    change = current - previous
                
                week_details["metrics"][metric_name] = {
                    "metric": metric_data["metric"],
                    "current": current,
                    "previous": previous,
                    "change": change,
                    "condition": condition
                }
            
            if all_conditions_met:
                matching_weeks.append(week_details)
        
        if not matching_weeks:
            conditions_str = ", ".join([f"{m.capitalize()} {c}" for m, c in conditions])
            return f"No weeks found where {conditions_str}."
        
        # Format response
        conditions_str = ", ".join([f"{m.capitalize()} {c}" for m, c in conditions])
        response = f"**Weeks where {conditions_str}:**\n\n"
        
        for week_info in matching_weeks:
            week_pretty = datetime.strptime(week_info["week"], "%Y-%m-%d").strftime("%d-%m-%Y")
            response += f"• **Week of {week_pretty}** ({week_info['week']}):\n"
            for metric_name, details in week_info["metrics"].items():
                change_sign = "+" if details["change"] >= 0 else ""
                response += f"  - {details['metric']}: {change_sign}{details['change']:,} "
                response += f"({details['current']:,} vs {details['previous']:,})\n"
            response += "\n"
        
        return response
    
    # Original deviation-based filtering
    week_data = weekly_data.get(selected_week, [])
    
    if not week_data:
        return f"No data found for week {selected_week}."
    
    # Extract deviation threshold from query
    deviation_threshold = None
    if "more than" in query_lower or "greater than" in query_lower or ">" in query_lower:
        # Try to extract number after "more than" or "greater than"
        patterns = [
            r'more than\s+([\d.]+)\s*%',
            r'greater than\s+([\d.]+)\s*%',
            r'>\s*([\d.]+)\s*%',
            r'([\d.]+)\s*%\s*deviation',
        ]
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                deviation_threshold = abs(float(match.group(1)))
                break
    
    # Filter metrics based on deviation
    filtered_metrics = []
    for metric in week_data:
        deviation = abs(metric.get("deviation", 0))
        if deviation_threshold is not None:
            if deviation > deviation_threshold:
                filtered_metrics.append(metric)
        else:
            # Default: show metrics with > 1% deviation if no threshold specified
            if deviation > 1.0:
                filtered_metrics.append(metric)
    
    if not filtered_metrics:
        return f"No metrics found with deviation greater than {deviation_threshold or 1}% for week {selected_week}."
    
    # Format response
    response = f"**Metrics from {selected_week} with deviation > {deviation_threshold or 1}%:**\n\n"
    for metric in filtered_metrics:
        deviation_sign = "+" if metric["deviation"] >= 0 else ""
        response += f"• **{metric['metric']}**: {deviation_sign}{metric['deviation']:.3f}% "
        response += f"(Current: {metric['current']:,}, Previous: {metric['previous']:,})\n"
    
    return response

# ------------------- KPI SUMMARY ---------------------- #
data = RAW_WEEKLY.get(selected_week, [])
if data:
    m1, m2, m3 = st.columns(3)
    m1.metric("User Satisfaction", "0.0%")
    m2.metric("System Health", "98.2%")
    m3.metric("Active Metrics", len(data))

# ----------------- CHAT CONVERSATION HISTORY ----------------- #
st.divider()
st.markdown("### 💬 Conversation")

# Display conversation history
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            # Check if it's a chart or text response
            if message.get("type") == "chart":
                # Use unique key for each chart to avoid duplicate ID error
                st.plotly_chart(message["content"], use_container_width=True, key=f"chart_{idx}")
            elif message.get("type") == "error":
                st.error(message["content"])
            elif message.get("type") == "info":
                st.info(message["content"])
            elif message.get("type") == "warning":
                st.warning(message["content"])
            else:
                st.write(message["content"])

# ---------------------- CHAT INPUT ---------------------- #
# Use chat_input for better UX (clears after submission)
query = st.chat_input("Ask about your data (e.g. plot gravy piechart)")

# Process query
if query:
    # Add user message to history and display immediately
    user_msg = {"role": "user", "content": query}
    st.session_state.messages.append(user_msg)
    
    # Display user message immediately
    with st.chat_message("user"):
        st.write(query)
    
    # Process query and generate response
    with st.chat_message("assistant"):
        if detect_harness_query(query):
            response_text = "Harness integration coming soon..."
            st.info(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text, "type": "info"})

        elif detect_plot_request(query):
            metrics_found = extract_metric_from_query(query)
            query_lower = query.lower()
            
            if "pie" in query_lower:
                # For pie charts, use first metric or None
                keyword = metrics_found[0].lower() if metrics_found else None
                fig = create_pie(selected_week, RAW_WEEKLY, keyword)
            elif "bar" in query_lower or "barchart" in query_lower:
                # For bar charts, pass all found metrics
                if metrics_found:
                    # Extract number of weeks from query (e.g., "past 2 weeks", "last 3 weeks")
                    num_weeks = None
                    import re
                    week_patterns = [
                        r'past\s+(\d+)\s+weeks?',
                        r'last\s+(\d+)\s+weeks?',
                        r'(\d+)\s+weeks?',
                    ]
                    for pattern in week_patterns:
                        match = re.search(pattern, query_lower)
                        if match:
                            num_weeks = int(match.group(1))
                            break
                    
                    fig = create_bar(metrics_found, RAW_WEEKLY, selected_week, num_weeks)
                else:
                    fig = None
            else:
                # For trend charts, pass all found metrics
                if metrics_found:
                    # Pass list of all metrics for multi-metric support
                    fig = create_trend(metrics_found, RAW_WEEKLY)
                else:
                    fig = None

            if fig is not None:
                # Get next index for unique key
                next_idx = len(st.session_state.messages)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
            else:
                error_msg = "No matching data found for this query."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})

        else:
            # Check if this is a data analysis query
            query_lower = query.lower()
            is_data_query = any(keyword in query_lower for keyword in [
                "deviation", "show", "list", "filter", "metrics", "latest week", 
                "current week", "greater than", "more than", "less than", "which week", "increased"
            ])
            
            if is_data_query:
                # Handle data analysis queries directly
                response = analyze_data_query(query, selected_week, RAW_WEEKLY)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response, "type": "text"})
            else:
                # Use AI router for other queries
                if api_key or ai_provider == "gemini":
                    try:
                        from ai.router import call_ai
                        # Enhance prompt with data context for better responses
                        data_context = f"\n\nAvailable data: Latest week is {selected_week}. Data contains metrics with fields: metric, current, previous, deviation (%), churn_current, churn_previous, churn_deviation (%)."
                        enhanced_query = query + data_context
                        response = call_ai(ai_provider, enhanced_query, api_key, model)
                        st.write(response)
                        st.session_state.messages.append({"role": "assistant", "content": response, "type": "text"})
                    except Exception as e:
                        error_msg = f"Error calling AI: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})
                else:
                    warning_msg = "Please configure API key in sidebar for AI queries"
                    st.warning(warning_msg)
                    st.session_state.messages.append({"role": "assistant", "content": warning_msg, "type": "warning"})
