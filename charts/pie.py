import plotly.express as px

def create_pie(selected_week, weekly_data, keyword=None):
    data = weekly_data.get(selected_week, [])
    if keyword:
        data = [d for d in data if keyword.lower() in d["metric"].lower()]

    if not data:
        return None

    labels = [d["metric"] for d in data]
    values = [d["current"] for d in data]

    fig = px.pie(names=labels, values=values, title=f"Distribution – {selected_week}")
    return fig
