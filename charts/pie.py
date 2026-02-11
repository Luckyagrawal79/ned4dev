import plotly.express as px
import streamlit as st

def create_pie(selected_week, weekly_data, keyword=None):
    st.write("DEBUG selected_week:", selected_week)
    st.write("DEBUG weekly_data keys:", list(weekly_data.keys()))

    data = weekly_data.get(selected_week)
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

    fig = px.pie(names=labels, values=values, title=f"Distribution – {selected_week}")
    return fig
