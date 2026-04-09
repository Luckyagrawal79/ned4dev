import plotly.express as px
import streamlit as st

def create_pie(selected_build, build_data, keyword=None):
    st.write("DEBUG selected_build:", selected_build)
    st.write("DEBUG build_data keys:", list(build_data.keys()))

    data = build_data.get(selected_build)
    st.write("DEBUG raw week data:", data)

    if not data:
        st.error("DEBUG: No data found for this week key")
        return None

    if keyword:
        keyword = keyword.lower().strip()
        data = [d for d in data if keyword in d["metric"].lower()]
        st.write("DEBUG filtered data:", data)

    if not data:
        st.error("DEBUG: Keyword filter removed all rows")
        return None

    labels = [d["metric"] for d in data]
    values = [d["current"] for d in data]

    fig = px.pie(names=labels, values=values, title=f"Distribution – {selected_build}")
    return fig
