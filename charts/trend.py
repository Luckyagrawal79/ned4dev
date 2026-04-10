import plotly.express as px
import pandas as pd
import plotly.graph_objects as go


def create_trend(metric_names, build_data, value_field="current", build_filter=None):
    """
    Create a trend chart for metrics. Supports asset-based filtering.

    metric_names can contain:
      - plain metric names: "IP-PID Count"
      - asset filter dicts: {"type": "asset_filter", "asset": "Gravy", "metrics": [...]}
    """
    if isinstance(metric_names, str):
        metric_names = [metric_names]

    label_suffix = f" ({value_field})" if value_field != "current" else ""

    # Check for asset filter
    asset_filter = None
    actual_metrics = []
    for m in metric_names:
        if isinstance(m, dict) and m.get("type") == "asset_filter":
            asset_filter = m["asset"]
            actual_metrics = m.get("metrics", [])
        elif isinstance(m, str):
            actual_metrics.append(m)

    builds_to_use = sorted(build_filter) if build_filter else sorted(build_data.keys())

    all_rows = []
    for build in builds_to_use:
        for row in build_data.get(build, []):
            # Apply asset filter if present
            if asset_filter and row.get("asset", "").lower() != asset_filter.lower():
                continue

            # If we have specific metrics, filter by them
            if actual_metrics:
                if not any(mn.lower() in row["metric"].lower() for mn in actual_metrics):
                    continue

            label = f"{row.get('asset', '')} - {row['metric']}" if row.get("asset") else row["metric"]
            all_rows.append({
                "build_number": build,
                "value": row.get(value_field, 0),
                "label": label,
            })

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows).sort_values("build_number")

    unique_labels = df["label"].unique()
    if len(unique_labels) > 1:
        fig = go.Figure()
        for label in unique_labels:
            label_data = df[df["label"] == label]
            fig.add_trace(go.Scatter(
                x=label_data["build_number"],
                y=label_data["value"],
                mode="lines+markers",
                name=label,
                line=dict(width=2),
            ))
        title = f"Trend{label_suffix}"
        if asset_filter:
            title += f" — {asset_filter}"
        fig.update_layout(title=title, xaxis_title="Build", yaxis_title=value_field, hovermode="x unified")
    else:
        title = f"{unique_labels[0]} Trend{label_suffix}"
        fig = px.line(df, x="build_number", y="value", title=title)

    return fig
