import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

def create_bar(metric_names, weekly_data, selected_week=None, num_weeks=None, value_field="current"):
    """
    Create a bar chart for one or more metrics across one or more weeks.
    
    Args:
        metric_names: Single metric name (str) or list of metric names
        weekly_data: Dictionary of weekly data
        selected_week: Optional week to filter to (if None, uses latest week)
        num_weeks: Optional number of weeks to include (e.g., 2 for past 2 weeks)
        value_field: Which field to plot (current, previous, deviation, churn_current, etc.)
    """
    # Handle both single metric and multiple metrics
    if isinstance(metric_names, str):
        metric_names = [metric_names]
    
    label_suffix = f" ({value_field})" if value_field != "current" else ""
    
    # Determine which weeks to include
    all_weeks = sorted(weekly_data.keys())
    
    if num_weeks and num_weeks > 1:
        # Get the last N weeks
        weeks_to_plot = all_weeks[-num_weeks:]
    elif selected_week:
        # Use only the selected week
        weeks_to_plot = [selected_week] if selected_week in all_weeks else [all_weeks[-1]]
    else:
        # Default to latest week
        weeks_to_plot = [all_weeks[-1]]
    
    if not weeks_to_plot:
        return None
    
    # Collect data for all weeks and metrics
    chart_data = []
    for week in weeks_to_plot:
        week_data = weekly_data.get(week, [])
        for metric_entry in week_data:
            metric_name_lower = metric_entry["metric"].lower()
            for requested_metric in metric_names:
                if requested_metric.lower() in metric_name_lower:
                    chart_data.append({
                        "week": week,
                        "metric": metric_entry["metric"],
                        "value": metric_entry.get(value_field, 0)
                    })
                    break  # Found a match, move to next entry
    
    if not chart_data:
        return None
    
    # Create bar chart
    fig = go.Figure()
    
    # If multiple weeks, create grouped bars
    if len(weeks_to_plot) > 1:
        # Group data by metric
        metrics_found = {}
        for entry in chart_data:
            metric = entry["metric"]
            if metric not in metrics_found:
                metrics_found[metric] = {}
            metrics_found[metric][entry["week"]] = entry["value"]
        
        # Create grouped bar chart
        x_labels = list(metrics_found.keys())
        
        # Add a trace for each week
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        for idx, week in enumerate(weeks_to_plot):
            values = [metrics_found.get(metric, {}).get(week, 0) for metric in x_labels]
            week_label = datetime.strptime(week, "%Y-%m-%d").strftime("%d-%m-%Y")
            fig.add_trace(go.Bar(
                name=week_label,
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
            title=f"Bar Chart{label_suffix}: {', '.join(metric_names)} - {len(weeks_to_plot)} weeks",
            xaxis_title="Metric",
            yaxis_title=value_field,
            showlegend=True,
            height=500,
            xaxis=dict(tickangle=-45)
        )
    else:
        # Single week - simple bar chart
        week = weeks_to_plot[0]
        filtered_data = [d for d in chart_data if d["week"] == week]
        
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
        
        week_label = datetime.strptime(week, "%Y-%m-%d").strftime("%d-%m-%Y")
        fig.update_layout(
            title=f"Bar Chart{label_suffix}: {', '.join(metric_names)} - {week_label}",
            xaxis_title="Metric",
            yaxis_title=value_field,
            showlegend=False,
            height=500,
            xaxis=dict(tickangle=-45)
        )
    
    return fig