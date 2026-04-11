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

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# ───────────────────── CSS ─────────────────────────────────────────────
st.markdown("""
    <style>
    footer {visibility: hidden;}
    header {visibility: hidden;}
    section[data-testid="stSidebar"] { visibility: visible !important; display: block !important; }
    div[data-testid="stChatInput"] { position: sticky !important; bottom: 0 !important; background: white !important; z-index: 1000 !important; padding: 1rem 0 !important; }
    </style>
""", unsafe_allow_html=True)

# ───────────────────── SIDEBAR ─────────────────────────────────────────
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

# ───────────────────── DATA LOAD ───────────────────────────────────────
st.markdown("## 🧠 N.E.D – Neural Executive Dashboard")

GCS_METRICS_URI = "gs://oneid-media-dev/Lucky/NedJsonStore/source_stats/"
store = JSONMetricStore(gcs_uri=GCS_METRICS_URI)

# Initialize asset resolver
resolver = AssetResolver(registry_path="data/asset_registry.json")

with st.sidebar.expander("Data Source Debug", expanded=False):
    st.code(f"gcs_uri = {store.gcs_uri}\nlocal_path = {os.path.abspath(store.local_path)}", language="bash")
    source = "GCS" if store.gcs_uri else "LOCAL"
    st.write("Source:", f"**{source}**")
    try:
        data = store.load()
        # Rebuild registry on every load so it stays current
        resolver.rebuild_from_data(data)
        st.success(f"Loaded {len(data)} rows from **{source}**")
        st.write(f"**Assets:** {resolver.assets}")
        st.write(f"**Metrics:** {resolver.metrics}")
        st.json(data[:3])
    except Exception as e:
        st.error(f"Load failed: {e}")
        st.text(traceback.format_exc())

RAW_BUILDS = store.group_by_build()


def pretty_build(w):
    return "Build " + datetime.strptime(w, "%Y-%m-%d").strftime("%d-%m-%Y")


pretty_map = {pretty_build(w): w for w in RAW_BUILDS.keys()}
selected_pretty = st.selectbox("📅 Select Build", list(pretty_map.keys()), key="build_selector")
selected_build = pretty_map[selected_pretty]

# Buttons
c1, c2, c3 = st.columns(3)
with c1: st.button("Executive Snapshot", key="btn_snapshot")
with c2: st.button("System Alerts", key="btn_alerts")
with c3: st.button("Key Performance Metrics", key="btn_metrics")

# ───────────────────── SESSION STATE ───────────────────────────────────
if "chart_fig" not in st.session_state:
    st.session_state.chart_fig = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ───────────────────── DATA ANALYSIS ───────────────────────────────────
def analyze_data_query(query, selected_build, build_data):
    query_lower = query.lower()

    # ── "Which build did X increase/decrease" pattern ──
    if "which build" in query_lower and any(w in query_lower for w in ["increased", "increase", "decreased", "decrease"]):
        conditions = []
        parts = re.split(r'\s+(but|and|,)\s+', query_lower)

        # Resolve asset from query
        asset_result = resolver.resolve_asset(query)
        target_asset = asset_result["match"] if asset_result["match"] else None

        for part in parts:
            part = part.strip()
            if "increased" in part or "increase" in part:
                conditions.append(("increased",))
            elif "decreased" in part or "decrease" in part:
                conditions.append(("decreased",))

        matching_builds = []
        for build, build_rows in build_data.items():
            rows = build_rows
            if target_asset:
                rows = [r for r in rows if r.get("asset", "").lower() == target_asset.lower()]

            for row in rows:
                current = row.get("current", 0)
                previous = row.get("previous", 0)
                for cond in conditions:
                    if cond[0] == "increased" and current > previous:
                        matching_builds.append({
                            "build_number": build,
                            "metric": row["metric"],
                            "asset": row.get("asset", ""),
                            "current": current,
                            "previous": previous,
                            "change": current - previous,
                        })
                    elif cond[0] == "decreased" and current < previous:
                        matching_builds.append({
                            "build_number": build,
                            "metric": row["metric"],
                            "asset": row.get("asset", ""),
                            "current": current,
                            "previous": previous,
                            "change": current - previous,
                        })

        if not matching_builds:
            return "No matching builds found for that condition."

        response = "**Matching builds:**\n\n"
        for b in matching_builds[:20]:
            bp = datetime.strptime(b["build_number"], "%Y-%m-%d").strftime("%d-%m-%Y")
            sign = "+" if b["change"] >= 0 else ""
            response += (
                f"• **Build {bp}** — {b['asset']} / {b['metric']}: "
                f"{sign}{b['change']:,} ({b['current']:,} vs {b['previous']:,})\n"
            )
        return response

    # ── Deviation filtering ──
    build_rows = build_data.get(selected_build, [])
    if not build_rows:
        return f"No data found for build {selected_build}."

    # Apply asset filter if mentioned
    asset_result = resolver.resolve_asset(query)
    if asset_result["match"]:
        build_rows = [r for r in build_rows if r.get("asset", "").lower() == asset_result["match"].lower()]

    deviation_threshold = None
    patterns = [
        r'more than\s+([\d.]+)\s*%', r'greater than\s+([\d.]+)\s*%',
        r'>\s*([\d.]+)\s*%', r'([\d.]+)\s*%\s*deviation',
    ]
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            deviation_threshold = abs(float(match.group(1)))
            break

    filtered = []
    for m in build_rows:
        dev = abs(m.get("deviation", 0))
        if deviation_threshold is not None:
            if dev > deviation_threshold:
                filtered.append(m)
        elif dev > 1.0:
            filtered.append(m)

    if not filtered:
        return f"No metrics with deviation > {deviation_threshold or 1}% for build {selected_build}."

    response = f"**Metrics from {selected_build} with deviation > {deviation_threshold or 1}%:**\n\n"
    for m in filtered:
        sign = "+" if m["deviation"] >= 0 else ""
        asset_label = f" [{m.get('asset', '')}]" if m.get("asset") else ""
        response += (
            f"• **{m['metric']}{asset_label}**: {sign}{m['deviation']:.3f}% "
            f"(Current: {m['current']:,}, Previous: {m['previous']:,})\n"
        )
    return response


# ───────────────────── KPI SUMMARY ─────────────────────────────────────
data = RAW_BUILDS.get(selected_build, [])
if data:
    m1, m2, m3 = st.columns(3)
    m1.metric("User Satisfaction", "0.0%")
    m2.metric("System Health", "98.2%")
    m3.metric("Active Metrics", len(data))

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
query = st.chat_input("Ask about your data (e.g. 'show gravy trend', 'plot DIG bar chart')")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        if detect_harness_query(query):
            msg = "Harness integration coming soon..."
            st.info(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg, "type": "info"})

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
                        date_range = parse_date_range(query, latest_build=sorted(RAW_BUILDS.keys())[-1])
                        build_filter = None
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
            # Non-plot → AI
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
