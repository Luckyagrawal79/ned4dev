import plotly.express as px
import pandas as pd
import plotly.graph_objects as go

def create_trend(metric_names, weekly_data, value_field="current"):
    """
    Create a trend chart for one or more metrics.
    
    Args:
        metric_names: Single metric name (str) or list of metric names
        weekly_data: Dictionary of weekly data
    """
    # Handle both single metric and multiple metrics
    if isinstance(metric_names, str):
        metric_names = [metric_names]
    
    # Set the label suffix based on the value field
    label_suffix = f" ({value_field})" if value_field != "current" else ""

    # Collect data for all metrics
    all_rows = []
    for week, metrics in weekly_data.items():
        for m in metrics:
            for metric_name in metric_names:
                if metric_name.lower() in m["metric"].lower():
                    all_rows.append({
                        "week": week,
                        "value": m.get(value_field, 0),
                        "metric": metric_name
                    })
    
    if not all_rows:
        return None
    
    df = pd.DataFrame(all_rows).sort_values("week")
    
    # Create figure with multiple lines if multiple metrics
    if len(metric_names) > 1:
        fig = go.Figure()
        for metric_name in metric_names:
            metric_data = df[df["metric"] == metric_name]
            if not metric_data.empty:
                fig.add_trace(go.Scatter(
                    x=metric_data["week"],
                    y=metric_data["value"],
                    mode="lines+markers",
                    name=metric_name,
                    line=dict(width=2)
                ))
        fig.update_layout(
            title=f"Trend Comparison{label_suffix}: {', '.join(metric_names)}",
            xaxis_title="Week",
            yaxis_title=value_field,
            hovermode="x unified"
        )
    else:
        # Single metric - use simpler plot
        fig = px.line(df, x="week", y="value", title=f"{metric_names[0]} Trend{label_suffix}")
    
    return fig
 