import plotly.express as px
import streamlit as st


def create_pie(selected_build, build_data, keyword=None):
    data = build_data.get(selected_build)
    if not data:
        return None

    if keyword:
        keyword = keyword.lower().strip()
        # Match against both metric and asset
        data = [d for d in data if keyword in d["metric"].lower() or keyword in d.get("asset", "").lower()]

    if not data:
        return None

    labels = [f"{d.get('asset', '')} - {d['metric']}" if d.get("asset") else d["metric"] for d in data]
    values = [d["current"] for d in data]

    fig = px.pie(names=labels, values=values, title=f"Distribution — {selected_build}")
    return fig
s