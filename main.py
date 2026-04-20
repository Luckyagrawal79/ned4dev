import os
import re
import traceback
from datetime import datetime

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
from nlp.asset_resolver import AssetResolver

st.set_page_config(page_title="NED", layout="wide", initial_sidebar_state="expanded")

# ───────────────────── CSS ─────────────────────────────────────────────
st.markdown("""
    <style>
    footer {visibility: hidden;}
    header {visibility: hidden;}
    section[data-testid="stSidebar"] { visibility: visible !important; display: block !important; }

    /* TransUnion Theme */
    .stApp { background-color: #1a1f2e; color: #e0e0e0; }
    section[data-testid="stSidebar"] { background-color: #2E3644 !important; }
    h2, h3 { color: #00A2D1 !important; }

    /* KPI Cards */
    .kpi-container { display: flex; gap: 12px; margin: 10px 0 15px 0; }
    .kpi-card {
        flex: 1; padding: 14px 16px; border-radius: 10px;
        background: linear-gradient(135deg, #2E3644 0%, #1a1f2e 100%);
        border-left: 3px solid #00A2D1;
    }
    .kpi-label { font-size: 12px; color: #8899aa; margin-bottom: 4px; }
    .kpi-value { font-size: 22px; font-weight: 700; }
    .kpi-positive { color: #4ade80; }
    .kpi-negative { color: #f87171; }
    .kpi-neutral { color: #94a3b8; }

    /* Chat messages */
    div[data-testid="stChatMessage"] {
        background-color: #232b3a !important;
        border-radius: 10px !important;
        border: 1px solid #2E3644 !important;
        margin-bottom: 8px !important;
    }
    .stChatMessage [data-testid="stMarkdownContainer"] { color: #e0e0e0 !important; }

    /* Chat input — full width, match page background */
    div[data-testid="stBottom"] { background-color: #1a1f2e !important; padding: 0 !important; }
    div[data-testid="stBottom"] > div { background-color: #1a1f2e !important; }
    div[data-testid="stChatInput"] {
        background-color: #1a1f2e !important;
        position: sticky !important; bottom: 0 !important;
        z-index: 1000 !important; padding: 8px 0 !important;
    }
    div[data-testid="stChatInput"] > div { border: none !important; box-shadow: none !important; background: #1a1f2e !important; }
    div[data-testid="stChatInput"] textarea {
        background-color: #2E3644 !important;
        color: #e0e0e0 !important;
        border: 1px solid #3a4556 !important;
        border-radius: 8px !important;
        font-size: 16px !important;
        min-height: 50px !important;
        padding: 14px !important;
    }
    div[data-testid="stChatInput"] button { background-color: #00A2D1 !important; }

    /* Divider */
    .stDivider { border-color: #2E3644 !important; }
    </style>
""", unsafe_allow_html=True)

# ───────────────────── SIDEBAR ─────────────────────────────────────────
with st.sidebar:
    st.markdown("**Configuration**")
    ai_provider = st.selectbox("Provider", ["gemini", "claude", "openai"], index=0, key="ai_provider")
    if ai_provider == "claude":
        api_key = st.text_input("Claude API Key", type="password", key="claude_key")
        model = st.selectbox("Model", ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"], key="claude_model")
    elif ai_provider == "openai":
        api_key = st.text_input("OpenAI API Key", type="password", key="openai_key")
        model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o"], key="openai_model")
    else:
        api_key = None
        # model = st.selectbox("Model", ["gemini-2.5-flash-lite", "gemini-1.5-pro"], key="gemini_model")
        model = st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"], key="gemini_model")

# ───────────────────── DATA LOAD ───────────────────────────────────────
st.markdown('<h1 style="color: #00A2D1; font-size: 2.4rem; margin-bottom: 5px;">N.E.D – Neural Executive Dashboard</h1>', unsafe_allow_html=True)

GCS_METRICS_URI = "gs://oneid-media-dev/Lucky/NedJsonStore/source_stats1/"

@st.cache_resource
def get_store():
    return JSONMetricStore(path="data/data_store.json", gcs_uri=GCS_METRICS_URI)

store = get_store()

# Initialize asset resolver
resolver = AssetResolver(registry_path="data/asset_registry.json")

# Rebuild registry silently on load
try:
    _data = store.load()
    resolver.rebuild_from_data(_data)
except Exception:
    pass

# with st.sidebar.expander("Data Source Debug", expanded=False):
#     st.code(f"gcs_uri = {store.gcs_uri}\nlocal_path = {os.path.abspath(store.local_path)}", language="bash")
#     source = "GCS" if store.gcs_uri else "LOCAL"
#     st.write("Source:", f"**{source}**")
#     try:
#         data = store.load()
#         # Rebuild registry on every load so it stays current
#         resolver.rebuild_from_data(data)
#         st.success(f"Loaded {len(data)} rows from **{source}**")
#         st.write(f"**Assets:** {resolver.assets}")
#         st.write(f"**Metrics:** {resolver.metrics}")
#         st.json(data[:3])
#     except Exception as e:
#         st.error(f"Load failed: {e}")
#         st.text(traceback.format_exc())

@st.cache_data(ttl=3600)  # cache for 1 hour
def load_builds():
    return store.group_by_build()

RAW_BUILDS = load_builds()

def pretty_build(w):
    return "Build " + datetime.strptime(w, "%Y-%m-%d").strftime("%d-%m-%Y")

sorted_builds = sorted(RAW_BUILDS.keys(), reverse=True)
pretty_map = {pretty_build(w): w for w in sorted_builds}
selected_pretty = st.selectbox("📅 Select Build", list(pretty_map.keys()), key="build_selector")
selected_build = pretty_map[selected_pretty]

# ───────────────────── REFRESH ─────────────────────────────────────────
if st.button("🔄 Refresh Data", use_container_width=True):
    store.reload()
    load_builds.clear()
    st.rerun()

# ───────────────────── KPI CARDS ───────────────────────────────────────
build_rows = RAW_BUILDS.get(selected_build, [])

def get_deviation(rows, metric, asset):
    for r in rows:
        if r["metric"] == metric and r.get("asset", "") == asset:
            return r.get("deviation", None)
    return None

kpi_configs = [
    ("Device IP", "Device IP Signals", "Total"),
    ("Cookie IP", "Cookie IP Signals", "Total"),
    ("Device Email", "Device Email Signals", "Total_Device"),
    ("Cookie Email", "Cookie Email Signals", "Total_Cookie"),
]

kpi_html = '<div class="kpi-container">'
for label, metric, asset in kpi_configs:
    dev = get_deviation(build_rows, metric, asset)
    if dev is not None:
        sign = "+" if dev >= 0 else ""
        css_class = "kpi-positive" if dev >= 0 else "kpi-negative"
        val_str = f"{sign}{dev:.2f}%"
    else:
        css_class = "kpi-neutral"
        val_str = "N/A"
    kpi_html += f'''
        <div class="kpi-card">
            <div class="kpi-label">{label} Deviation</div>
            <div class="kpi-value {css_class}">{val_str}</div>
        </div>'''
kpi_html += '</div>'
st.markdown(kpi_html, unsafe_allow_html=True)

# ───────────────────── ACTION BUTTONS ──────────────────────────────────
b1, b2, b3, b4 = st.columns(4)
with b1:
    build_review_clicked = st.button("📋 Build Review", use_container_width=True)
with b2:
    ops_check_clicked = st.button("⚠️ Ops Failure Check", use_container_width=True)
with b3:
    delivery_clicked = st.button("🚚 Delivery Status", use_container_width=True)
with b4:
    availability_clicked = st.button("🔍 Asset Availability", use_container_width=True)

# ───────────────────── SESSION STATE ───────────────────────────────────
if "chart_fig" not in st.session_state:
    st.session_state.chart_fig = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ───────────────────── BUILD REVIEW ────────────────────────────────────
if build_review_clicked:
    flagged = [r for r in build_rows if abs(r.get("deviation", 0)) > 5]
    if flagged:
        msg = f"**📋 Build Review — {selected_build}**\n\n"
        msg += f"**{len(flagged)} metrics with deviation > 5%:**\n\n"
        msg += "| Metric | Asset | Current | Previous | Deviation |\n"
        msg += "|--------|-------|---------|----------|-----------|\n"
        for r in sorted(flagged, key=lambda x: abs(x.get("deviation", 0)), reverse=True):
            sign = "+" if r["deviation"] >= 0 else ""
            msg += (
                f"| {r['metric']} | {r.get('asset', '-')} | "
                f"{r.get('current', 0):,} | {r.get('previous', 0):,} | "
                f"{sign}{r['deviation']:.2f}% |\n"
            )
    else:
        msg = f"**📋 Build Review — {selected_build}**\n\n✅ All clear — no metrics with deviation > 5%."
    st.session_state.messages.append({"role": "user", "content": f"Build Review for {selected_build}"})
    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "text"})
    st.rerun()

if ops_check_clicked:
    st.session_state.messages.append({"role": "user", "content": "Ops Assist Fail Check"})
    st.session_state.messages.append({"role": "assistant", "content": "🚧 Ops Assist Fail Check — coming soon.", "type": "info"})
    st.rerun()

if delivery_clicked:
    st.session_state.messages.append({"role": "user", "content": "Delivery Status Check"})
    try:
        from store.delivery_checker import check_delivery_status, format_delivery_status
        results = check_delivery_status(
            project_id="your-gcp-project-id",
            region="your-region",           # e.g. "us-central1"
            cluster_name="your-cluster"     # optional, remove if not needed
        )
        msg = format_delivery_status(results)
    except Exception as e:
        msg = f"**🚚 Delivery Status**\n\nError checking jobs: {str(e)}"
    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "text"})
    st.rerun()

if availability_clicked:
    st.session_state.messages.append({"role": "user", "content": "Asset Availability in OneTru"})
    st.session_state.messages.append({"role": "assistant", "content": "🚧 Asset Availability in OneTru— coming soon.", "type": "info"})
    st.rerun()
# ───────────────────── KPI SUMMARY ─────────────────────────────────────
# data = RAW_BUILDS.get(selected_build, [])
# if data:
#     m1, m2, m3 = st.columns(3)
#     m1.metric("User Satisfaction", "0.0%")
#     m2.metric("System Health", "98.2%")
#     m3.metric("Active Metrics", len(data))

# ───────────────────── CHAT HISTORY ────────────────────────────────────
st.divider()
st.markdown("### 💬 Conversation")

for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        elif message.get("type") == "chart":
            st.plotly_chart(message["content"], use_container_width=True, key=f"chart_{idx}")
        elif message.get("type") == "error":
            st.error(message["content"])
        elif message.get("type") == "info":
            st.info(message["content"])
        elif message.get("type") == "warning":
            st.warning(message["content"])
        else:
            st.write(message["content"])



# ───────────────────── CHAT INPUT ──────────────────────────────────────
query = st.chat_input("Ask about your data (e.g. 'show gravy trend')")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        if detect_harness_query(query):
            msg = "Harness integration coming soon..."
            st.info(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg, "type": "info"})
        
        elif any(phrase in query.lower() for phrase in ["delivery status", "delivery done", "delivery check", "is delivery"]):
            try:
                from store.delivery_checker import check_delivery_status, format_delivery_status
                results = check_delivery_status(
                    project_id="pon-build-prod-mig-wkly-0441"
                )
                msg = format_delivery_status(results)
            except Exception as e:
                msg = f"Error checking delivery: {str(e)}"
            st.write(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg, "type": "text"})

        elif detect_plot_request(query):
            query_lower = query.lower()
            metrics_found = extract_metric_from_query(query, RAW_BUILDS)

            # ── Handle low-confidence suggestion ──
            if metrics_found and isinstance(metrics_found[0], dict) and "suggestion" in metrics_found[0]:
                s = metrics_found[0]
                msg = f"Did you mean **{s['suggestion']}**?\n\nAvailable metrics:\n\n"
                for m in sorted(s["all_metrics"]):
                    msg += f"• {m}\n\n"
                msg += "\nAvailable assets:\n\n"
                for a in resolver.assets:
                    msg += f"• {a}\n\n"
                msg += "\nTry again with the exact name."
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg, "type": "warning"})

            elif not metrics_found:
                # Last resort: check if it's an asset-only query
                asset_result = resolver.resolve_asset(query)
                if asset_result["match"] and asset_result["confident"]:
                    metrics_found = [{"type": "asset_filter", "asset": asset_result["match"], "metrics": list(resolver.metrics)}]
                elif asset_result["match"] and not asset_result["confident"]:
                    msg = f"Did you mean asset **{asset_result['match']}**?\n\nAvailable assets:\n\n"
                    for a in asset_result.get("suggestions", resolver.assets):
                        msg += f"• {a}\n\n"
                    st.markdown(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "warning"})
                    metrics_found = None
                else:
                    msg = "No matching metric or asset found.\n\nAvailable metrics:\n\n"
                    for m in resolver.metrics:
                        msg += f"• {m}\n\n"
                    msg += "\nAvailable assets:\n\n"
                    for a in resolver.assets:
                        msg += f"• {a}\n\n"
                    st.error(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "error"})

            if metrics_found:
                # Detect value field
                field_result = detect_value_field(query_lower)

                if not field_result["confident"]:
                    msg = f"Did you mean **{field_result['match']}**?\n\nAvailable fields:\n\n"
                    for f in field_result["suggestions"]:
                        msg += f"• {f}\n\n"
                    st.markdown(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "warning"})
                else:
                    value_field = field_result["match"]

                    if "pie" in query_lower:
                        keyword = None
                        if isinstance(metrics_found[0], dict) and metrics_found[0].get("type") == "asset_filter":
                            keyword = metrics_found[0]["asset"]
                        elif isinstance(metrics_found[0], str):
                            keyword = metrics_found[0].lower()

                        fig = create_pie(selected_build, RAW_BUILDS, keyword)
                        if fig:
                            next_idx = len(st.session_state.messages)
                            st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                            st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                        else:
                            msg = "No matching data found for this query."
                            st.error(msg)
                            st.session_state.messages.append({"role": "assistant", "content": msg, "type": "error"})

                    elif "bar" in query_lower or "barchart" in query_lower:
                        num_builds = None
                        n_match = re.search(r'(?:last|past|recent)\s+(\d+)\s+(?:weeks?|builds?)', query_lower)
                        if n_match:
                            num_builds = int(n_match.group(1))
                            
                        for pattern in [r'past\s+(\d+)\s+builds?', r'last\s+(\d+)\s+builds?', r'(\d+)\s+builds?']:
                            match = re.search(pattern, query_lower)
                            if match:
                                num_builds = int(match.group(1))
                                break

                        fig = create_bar(metrics_found, RAW_BUILDS, selected_build, num_builds, value_field)
                        if fig:
                            next_idx = len(st.session_state.messages)
                            st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                            st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                        else:
                            msg = "No matching data found for this query."
                            st.error(msg)
                            st.session_state.messages.append({"role": "assistant", "content": msg, "type": "error"})

                    else:
                        # Trend chart
                        build_filter = None
                        n_match = re.search(r'(?:last|past|recent)\s+(\d+)\s+(?:weeks?|builds?)', query_lower)
                        if n_match:
                            n = int(n_match.group(1))
                            build_filter = sorted(RAW_BUILDS.keys())[-n:]
                            date_range = None
                        elif any(p in query_lower for p in ["last week", "latest week", "this week", "last build", "latest build"]):
                            build_filter = [sorted(RAW_BUILDS.keys())[-1]]
                            date_range = None
                        else:
                            date_range = parse_date_range(query, latest_build=sorted(RAW_BUILDS.keys())[-1])
                        range_info_msg = None

                        if date_range:
                            all_builds = sorted(RAW_BUILDS.keys())
                            filtered = filter_builds_by_range(all_builds, date_range["start_date"], date_range["end_date"])
                            requested_label = (
                                f"{date_range['start_month_name']} {date_range['start_year']}"
                                f" to {date_range['end_month_name']} {date_range['end_year']}"
                            )
                            if not filtered:
                                range_info_msg = (
                                    f"No data for **{requested_label}**. "
                                    f"Available: **{all_builds[0]}** to **{all_builds[-1]}**."
                                )
                            else:
                                build_filter = filtered
                                first_d = datetime.strptime(filtered[0], "%Y-%m-%d").date()
                                last_d = datetime.strptime(filtered[-1], "%Y-%m-%d").date()
                                if first_d > date_range["start_date"] or last_d < date_range["end_date"]:
                                    range_info_msg = (
                                        f"Requested: **{requested_label}**. "
                                        f"Showing {first_d.strftime('%B %Y')} to {last_d.strftime('%B %Y')} "
                                        f"({len(filtered)} builds)."
                                    )

                        if range_info_msg and build_filter is None:
                            st.warning(range_info_msg)
                            st.session_state.messages.append({"role": "assistant", "content": range_info_msg, "type": "warning"})
                        else:
                            if range_info_msg:
                                st.info(range_info_msg)
                                st.session_state.messages.append({"role": "assistant", "content": range_info_msg, "type": "info"})

                            fig = create_trend(metrics_found, RAW_BUILDS, value_field, build_filter)
                            if fig:
                                next_idx = len(st.session_state.messages)
                                st.plotly_chart(fig, use_container_width=True, key=f"chart_{next_idx}")
                                st.session_state.messages.append({"role": "assistant", "content": fig, "type": "chart"})
                            else:
                                msg = "No matching data found."
                                st.error(msg)
                                st.session_state.messages.append({"role": "assistant", "content": msg, "type": "error"})

        else:
            # Non-plot query — send to AI with actual data context
            if api_key or ai_provider == "gemini":
                try:
                    from ai.router import call_ai
                    from ai.data_context import build_data_context, build_ai_prompt

                    data_context = build_data_context(query, RAW_BUILDS, selected_build, resolver)
                    enhanced_query = build_ai_prompt(query, data_context)

                    response = call_ai(ai_provider, enhanced_query, api_key, model)
                    st.write(response)
                    st.session_state.messages.append({"role": "assistant", "content": response, "type": "text"})
                except Exception as e:
                    msg = f"Error calling AI: {str(e)}"
                    st.error(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg, "type": "error"})
            else:
                msg = "Please configure API key in sidebar for AI queries"
                st.warning(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg, "type": "warning"})


# Auto-scroll to latest message
import streamlit.components.v1 as components
components.html("""
    <script>
    const messages = parent.document.querySelectorAll('[data-testid="stChatMessage"]');
    if (messages.length > 0) {
        messages[messages.length - 1].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    </script>
""", height=0)