import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

def create_bar(metric_names, build_data, selected_build=None, num_builds=None, value_field="current"):
    """
    Create a bar chart for one or more metrics across one or more weeks.
    
    Args:
        metric_names: Single metric name (str) or list of metric names
        build_data: Dictionary of weekly data
        selected_build: Optional week to filter to (if None, uses latest week)
        num_builds: Optional number of weeks to include (e.g., 2 for past 2 weeks)
        value_field: Which field to plot (current, previous, deviation, churn_current, etc.)
    """
    # Handle both single metric and multiple metrics
    if isinstance(metric_names, str):
        metric_names = [metric_names]
    
    label_suffix = f" ({value_field})" if value_field != "current" else ""
    
    # Determine which weeks to include
    all_builds = sorted(build_data.keys())
    
    if num_builds and num_builds > 1:
        # Get the last N weeks
        builds_to_plot = all_builds[-num_builds:]
    elif selected_build:
        # Use only the selected week
        builds_to_plot = [selected_build] if selected_build in all_builds else [all_builds[-1]]
    else:
        # Default to latest week
        builds_to_plot = [all_builds[-1]]
    
    if not builds_to_plot:
        return None
    
    # Collect data for all weeks and metrics
    chart_data = []
    for week in builds_to_plot:
        build_data_rows = build_data.get(week, [])
        for metric_entry in build_data_rows:
            metric_name_lower = metric_entry["metric"].lower()
            for requested_metric in metric_names:
                if requested_metric.lower() in metric_name_lower:
                    chart_data.append({
                        "build_number": week,
                        "metric": metric_entry["metric"],
                        "value": metric_entry.get(value_field, 0)
                    })
                    break  # Found a match, move to next entry
    
    if not chart_data:
        return None
    
    # Create bar chart
    fig = go.Figure()
    
    # If multiple weeks, create grouped bars
    if len(builds_to_plot) > 1:
        # Group data by metric
        metrics_found = {}
        for entry in chart_data:
            metric = entry["metric"]
            if metric not in metrics_found:
                metrics_found[metric] = {}
            metrics_found[metric][entry["build_number"]] = entry["value"]
        
        # Create grouped bar chart
        x_labels = list(metrics_found.keys())
        
        # Add a trace for each week
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        for idx, week in enumerate(builds_to_plot):
            values = [metrics_found.get(metric, {}).get(week, 0) for metric in x_labels]
            build_label = datetime.strptime(week, "%Y-%m-%d").strftime("%d-%m-%Y")
            fig.add_trace(go.Bar(
                name=build_label,
                x=x_labels,
                y=values,
                text=values,
                texttemplate='%{text:,}',
                textposition='outside',
                marker=dict(
                    color=colors[idx % len(colors)],
                    line=dict(color=colors[idx % len(colors)], width=1)
                )
            ))
        
        fig.update_layout(
            barmode='group',
            title=f"Bar Chart{label_suffix}: {', '.join(metric_names)} - {len(builds_to_plot)} weeks",
            xaxis_title="Metric",
            yaxis_title=value_field,
            showlegend=True,
            height=500,
            xaxis=dict(tickangle=-45)
        )
    else:
        # Single week - simple bar chart
        week = builds_to_plot[0]
        filtered_data = [d for d in chart_data if d["build_number"] == week]
        
        labels = [d["metric"] for d in filtered_data]
        values = [d["value"] for d in filtered_data]
        
        fig.add_trace(go.Bar(
            x=labels,
            y=values,
            text=values,
            texttemplate='%{text:,}',
            textposition='outside',
            marker=dict(
                color='#1f77b4',
                line=dict(color='#1f77b4', width=1)
            )
        ))
        
        build_label = datetime.strptime(week, "%Y-%m-%d").strftime("%d-%m-%Y")
        fig.update_layout(
            title=f"Bar Chart{label_suffix}: {', '.join(metric_names)} - {build_label}",
            xaxis_title="Metric",
            yaxis_title=value_field,
            showlegend=False,
            height=500,
            xaxis=dict(tickangle=-45)
        )
    
    return fig