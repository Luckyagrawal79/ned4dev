import os
import traceback

from dotenv import load_dotenv

load_dotenv()

import streamlit as st
from store.json_store import JSONMetricStore
from charts.pie import create_pie
from charts.trend import create_trend
from charts.bar import create_bar
from nlp.intent import detect_plot_request, detect_harness_query
from nlp.metric_extractor import extract_metric_from_query
from nlp.field_detector import detect_value_field
from nlp.date_range_parser import parse_date_range, filter_builds_by_range
from datetime import datetime

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Debug – confirm correct file
st.error("RUNNING FILE: " + os.path.abspath(__file__) + "New Format 8")

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

GCS_METRICS_URI = None  # Set to "gs://..." to use GCS, or leave None for local data
store = JSONMetricStore(path="data/data_store.json", gcs_uri=GCS_METRICS_URI)

with st.sidebar.expander("Data Source Debug", expanded=False):
    st.code(f"gcs_uri = {store.gcs_uri}\nlocal_path = {os.path.abspath(store.local_path)}", language="bash")
    source = "GCS" if store.gcs_uri else "LOCAL"
    st.write("chosen source: ", f"**{source}**")

    try:
        data = store.load()
        st.success(f"Loaded {len(data)} rows from **{source}**")
        builds_found = sorted(set(row["build_number"] for row in data))
        st.write(f"**Total rows:** {len(data)}")
        st.write(f"**Builds found:** {builds_found}")
        for w in builds_found:
            count = sum(1 for r in data if r["build_number"] == w)
            st.write(f"  {w} → {count} metrics")
        st.json(data[:3])
    except Exception as e:
        st.error(f"Load failed -> likely GCS if gcs_uri is set. \n\n{e}")
        st.text("Traceback: ")
        st.text("".join(traceback.format_exc()))



RAW_BUILDS = store.group_by_build()

def pretty_build(w):
    return "Build " + datetime.strptime(w, "%Y-%m-%d").strftime("%d-%m-%Y")

pretty_map = {pretty_build(w): w for w in RAW_BUILDS.keys()}
selected_pretty = st.selectbox("📅 Select Build", list(pretty_map.keys()), key="build_selector")
selected_build = pretty_map[selected_pretty]

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
def analyze_data_query(query, selected_build, build_data):
    """
    Analyze data based on user query and return filtered results.
    """
    import re
    query_lower = query.lower()
    
    # Check if query is asking about which build metric(s) changed
    if "which build" in query_lower and ("increased" in query_lower or "increase" in query_lower or "decreased" in query_lower or "decrease" in query_lower):
        # Extract all metric conditions from query
        available_metrics = ['maid', 'gravy', 'cookie', 'dig', 'liveintent']
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
        matching_builds = []
        for build, build_rows in build_data.items():
            build_metrics = {m["metric"].lower(): m for m in build_rows}
            all_conditions_met = True
            build_details = {"build_number": build, "metrics": {}}
            
            for metric_name, condition in conditions:
                # Find the metric data for this metric name
                metric_data = None
                for metric_key, metric_value in build_metrics.items():
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
                
                build_details["metrics"][metric_name] = {
                    "metric": metric_data["metric"],
                    "current": current,
                    "previous": previous,
                    "change": change,
                    "condition": condition
                }
            
            if all_conditions_met:
                matching_builds.append(build_details)
        
        if not matching_builds:
            conditions_str = ", ".join([f"{m.capitalize()} {c}" for m, c in conditions])
            return f"No builds found where {conditions_str}."
        
        # Format response
        conditions_str = ", ".join([f"{m.capitalize()} {c}" for m, c in conditions])
        response = f"**Weeks where {conditions_str}:**\n\n"
        
        for build_info in matching_builds:
            week_pretty = datetime.strptime(build_info["build_number"], "%Y-%m-%d").strftime("%d-%m-%Y")
            response += f"• **Build {week_pretty}** ({build_info['build_number']}):\n"
            for metric_name, details in build_info["metrics"].items():
                change_sign = "+" if details["change"] >= 0 else ""
                response += f"  - {details['metric']}: {change_sign}{details['change']:,} "
                response += f"({details['current']:,} vs {details['previous']:,})\n"
            response += "\n"
        
        return response
    
    # Original deviation-based filtering
    build_rows = build_data.get(selected_build, [])
    
    if not build_rows:
        return f"No data found for build {selected_build}."
    
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
    for metric in build_rows:
        deviation = abs(metric.get("deviation", 0))
        if deviation_threshold is not None:
            if deviation > deviation_threshold:
                filtered_metrics.append(metric)
        else:
            # Default: show metrics with > 1% deviation if no threshold specified
            if deviation > 1.0:
                filtered_metrics.append(metric)
    
    if not filtered_metrics:
        return f"No metrics found with deviation greater than {deviation_threshold or 1}% for build {selected_build}."
    
    # Format response
    response = f"**Metrics from {selected_build} with deviation > {deviation_threshold or 1}%:**\n\n"
    for metric in filtered_metrics:
        deviation_sign = "+" if metric["deviation"] >= 0 else ""
        response += f"• **{metric['metric']}**: {deviation_sign}{metric['deviation']:.3f}% "
        response += f"(Current: {metric['current']:,}, Previous: {metric['previous']:,})\n"
    
    return response

# ------------------- KPI SUMMARY ---------------------- #
data = RAW_BUILDS.get(selected_build, [])
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
            metrics_found = extract_metric_from_query(query, RAW_BUILDS)
            query_lower = query.lower()
            
            # Check if metric extractor returned a suggestion (fuzzy match, low confidence)
            if metrics_found and isinstance(metrics_found[0], dict) and "suggestion" in metrics_found[0]:
                # Show suggestion to the user
                suggestion = metrics_found[0]
                suggest_msg = f"Did you mean **{suggestion['suggestion']}**?\n\nAvailable metrics:\n\n"

                # Show all available metrics in the suggestion
                for m in sorted(suggestion["all_metrics"]):
                    suggest_msg += f"• {m}\n\n"
                suggest_msg += "\n\nTry again with the exact metric name."

                # Show warning to the user
                st.markdown(suggest_msg)
                st.session_state.messages.append({"role": "assistant", "content": suggest_msg, "type": "warning"})


            elif not metrics_found:
                # Show error to the user
                error_msg = "No matching metric found. Try using a keyword from your data."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})


            else:
                # Detect which value field to plot 
                field_result = detect_value_field(query_lower)

                # Show suggestion to the user
                if not field_result["confident"]:
                    # Show suggestion to the user
                    suggest_msg = f"Did you mean **{field_result['match']}**?\n\nAvailable fields:\n\n"

                    # Show all available fields in the suggestion
                    for f in field_result["suggestions"]:
                        suggest_msg += f"• {f}\n\n"
                    suggest_msg += "\n\nTry again with the exact field name."

                    # Show warning to the user
                    st.markdown(suggest_msg)
                    st.session_state.messages.append({"role": "assistant", "content": suggest_msg, "type": "warning"})
                else:
                    # Set the value field to the matched field
                    value_field = field_result["match"]

                    # Create the chart
                    if "pie" in query_lower:
                        # For pie charts, use first metric or None
                        keyword = metrics_found[0].lower() if metrics_found else None
                        fig = create_pie(selected_build, RAW_BUILDS, keyword)

                        if fig is not None:
                            next_idx = len(st.session_state.messages)
                            st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                            st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                        else:
                            error_msg = "No matching data found for this query."
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})

                    elif "bar" in query_lower or "barchart" in query_lower:
                        # Extract number of weeks from query if present
                        num_builds = None
                        import re
                        build_patterns = [
                            r'past\s+(\d+)\s+builds?',
                            r'last\s+(\d+)\s+builds?',
                            r'(\d+)\s+builds?',
                        ]
                        for pattern in build_patterns:
                            match = re.search(pattern, query_lower)
                            if match:
                                num_builds = int(match.group(1))
                                break
                        
                        fig = create_bar(metrics_found, RAW_BUILDS, selected_build, num_builds, value_field)

                        if fig is not None:
                            next_idx = len(st.session_state.messages)
                            st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                            st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                        else:
                            error_msg = "No matching data found for this query."
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})
                    else:
                        # Default: trend chart — check for date range
                        date_range = parse_date_range(query, latest_build=sorted(RAW_BUILDS.keys())[-1])
                        build_filter = None
                        range_info_msg = None

                        if date_range:
                            all_builds = sorted(RAW_BUILDS.keys())
                            filtered = filter_builds_by_range(
                                all_builds,
                                date_range["start_date"],
                                date_range["end_date"],
                            )

                            requested_label = (
                                f"{date_range['start_month_name']} {date_range['start_year']}"
                                f" to {date_range['end_month_name']} {date_range['end_year']}"
                            )

                            if not filtered:
                                # No data at all in the requested range
                                range_info_msg = (
                                    f"No data available for **{requested_label}**. "
                                    f"Available data spans **{all_builds[0]}** to **{all_builds[-1]}**."
                                )
                            else:
                                build_filter = filtered

                                # Check if filtered range covers the full request
                                from datetime import date as _date
                                first_build_date = datetime.strptime(filtered[0], "%Y-%m-%d").date()
                                last_build_date = datetime.strptime(filtered[-1], "%Y-%m-%d").date()

                                # If first available week is after requested start OR
                                # last available week is before requested end → partial
                                partial = (
                                    first_build_date > date_range["start_date"]
                                    or last_build_date < date_range["end_date"]
                                )
                                if partial:
                                    avail_start = first_build_date.strftime("%B %Y")
                                    avail_end = last_build_date.strftime("%B %Y")
                                    range_info_msg = (
                                        f"Requested range: **{requested_label}**. "
                                        f"Available data covers **{avail_start}** to **{avail_end}** "
                                        f"({len(filtered)} week{'s' if len(filtered) != 1 else ''}). "
                                        f"Showing what's available."
                                    )

                        # Show info message if there's one
                        if range_info_msg and build_filter is None:
                            # No data at all — just show the message, no chart
                            st.warning(range_info_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": range_info_msg,
                                "type": "warning",
                            })
                        else:
                            # Show partial-data info if applicable
                            if range_info_msg:
                                st.info(range_info_msg)
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": range_info_msg,
                                    "type": "info",
                                })

                            fig = create_trend(metrics_found, RAW_BUILDS, value_field, build_filter)
 
                            if fig is not None:
                                next_idx = len(st.session_state.messages)
                                st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                                st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                            else:
                                error_msg = "No matching data found for this query."
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg, "type": "error"})
 
        else:
            # Non-plot query — send to AI with actual data context
            if api_key or ai_provider == "gemini":
                try:
                    from ai.router import call_ai
                    from ai.data_context import build_data_context, build_ai_prompt

                    # Build rich context with actual metric data
                    data_context = build_data_context(query, RAW_BUILDS, selected_build)
                    enhanced_query = build_ai_prompt(query, data_context)

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
 