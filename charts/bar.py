import plotly.graph_objects as go
import pandas as pd
from datetime import datetime


def create_bar(metric_names, build_data, selected_build=None, num_builds=None, value_field="current"):
    """
    Create a bar chart. Supports asset-based filtering.
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

    all_builds = sorted(build_data.keys())

    if num_builds and num_builds > 1:
        builds_to_plot = all_builds[-num_builds:]
    elif selected_build:
        builds_to_plot = [selected_build] if selected_build in all_builds else [all_builds[-1]]
    else:
        builds_to_plot = [all_builds[-1]]

    if not builds_to_plot:
        return None

    chart_data = []
    for build in builds_to_plot:
        for row in build_data.get(build, []):
            if asset_filter and row.get("asset", "").lower() != asset_filter.lower():
                continue
            if actual_metrics:
                if not any(mn.lower() in row["metric"].lower() for mn in actual_metrics):
                    continue

            label = f"{row.get('asset', '')} - {row['metric']}" if row.get("asset") else row["metric"]
            chart_data.append({
                "build_number": build,
                "label": label,
                "value": row.get(value_field, 0),
            })

    if not chart_data:
        return None

    fig = go.Figure()

    if len(builds_to_plot) > 1:
        # Grouped bars by build
        labels_found = {}
        for entry in chart_data:
            labels_found.setdefault(entry["label"], {})[entry["build_number"]] = entry["value"]

        x_labels = list(labels_found.keys())
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

        for idx, build in enumerate(builds_to_plot):
            values = [labels_found.get(l, {}).get(build, 0) for l in x_labels]
            build_label = datetime.strptime(build, "%Y-%m-%d").strftime("%d-%m-%Y")
            fig.add_trace(go.Bar(
                name=build_label, x=x_labels, y=values,
                text=values, texttemplate='%{text:,}', textposition='outside',
                marker=dict(color=colors[idx % len(colors)]),
            ))

        title = f"Bar Chart{label_suffix} — {len(builds_to_plot)} builds"
        if asset_filter:
            title += f" — {asset_filter}"
        fig.update_layout(barmode='group', title=title, xaxis_title="Metric",
                          yaxis_title=value_field, showlegend=True, height=500, xaxis=dict(tickangle=-45))
    else:
        build = builds_to_plot[0]
        filtered = [d for d in chart_data if d["build_number"] == build]
        labels = [d["label"] for d in filtered]
        values = [d["value"] for d in filtered]

        fig.add_trace(go.Bar(
            x=labels, y=values, text=values,
            texttemplate='%{text:,}', textposition='outside',
            marker=dict(color='#1f77b4'),
        ))

        build_label = datetime.strptime(build, "%Y-%m-%d").strftime("%d-%m-%Y")
        title = f"Bar Chart{label_suffix} — {build_label}"
        if asset_filter:
            title += f" — {asset_filter}"
        fig.update_layout(title=title, xaxis_title="Metric", yaxis_title=value_field,
                          showlegend=False, height=500, xaxis=dict(tickangle=-45))

    return fig
