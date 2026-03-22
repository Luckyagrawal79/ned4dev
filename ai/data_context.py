"""
Build rich data context for AI queries.

Extracts relevant metric rows based on the user's query (metric name + date range)
and formats them into a clear context string that can be sent to Gemini/Claude/OpenAI
so the AI can answer data questions accurately.
"""

import json
from nlp.metric_extractor import extract_metric_from_query
from nlp.date_range_parser import parse_date_range, filter_weeks_by_range


def build_data_context(query: str, weekly_data: dict, selected_week: str) -> str:
    """
    Analyze the user's query, extract relevant data, and build a context string
    that gives the AI everything it needs to answer.

    Args:
        query: The user's raw question
        weekly_data: Full weekly data dict {week_key: [rows...]}
        selected_week: Currently selected week in the UI

    Returns:
        A formatted context string with actual data rows.
    """
    all_weeks = sorted(weekly_data.keys())

    # --- 1. Try to detect which metric(s) the user is asking about ---
    metrics_found = extract_metric_from_query(query, weekly_data)

    # Handle suggestion dicts (low-confidence fuzzy match)
    metric_names = []
    if metrics_found:
        for m in metrics_found:
            if isinstance(m, dict):
                # Low confidence suggestion — still use it for context
                metric_names.append(m.get("suggestion", ""))
            else:
                metric_names.append(m)

    # --- 2. Try to detect a date range ---
    date_range = parse_date_range(query, latest_week=all_weeks[-1] if all_weeks else None)
    weeks_to_use = all_weeks  # default: all weeks

    range_note = ""
    if date_range:
        filtered = filter_weeks_by_range(all_weeks, date_range["start_date"], date_range["end_date"])
        requested_label = (
            f"{date_range['start_month_name']} {date_range['start_year']}"
            f" to {date_range['end_month_name']} {date_range['end_year']}"
        )
        if filtered:
            weeks_to_use = filtered
            range_note = f"Showing data for: {requested_label} ({len(filtered)} weeks)"
        else:
            range_note = (
                f"No data found for {requested_label}. "
                f"Available data spans {all_weeks[0]} to {all_weeks[-1]}."
            )
            # Still use all weeks so AI has some context
            weeks_to_use = all_weeks

    # --- 3. Extract matching rows ---
    rows = []
    for week in weeks_to_use:
        week_metrics = weekly_data.get(week, [])
        for row in week_metrics:
            if metric_names:
                # Only include rows matching the detected metrics
                if any(mn.lower() in row["metric"].lower() for mn in metric_names):
                    rows.append(row)
            else:
                # No specific metric detected — include everything for this week
                rows.append(row)

    # --- 4. Build the context string ---
    parts = []

    parts.append("=== NED DASHBOARD DATA CONTEXT ===")
    parts.append(f"Currently selected week in UI: {selected_week}")
    parts.append(f"Total data range: {all_weeks[0]} to {all_weeks[-1]} ({len(all_weeks)} weeks)")

    # All unique metric names in the data
    all_metric_names = sorted(set(
        row["metric"] for wk in all_weeks for row in weekly_data.get(wk, [])
    ))
    parts.append(f"Available metrics: {', '.join(all_metric_names)}")

    if metric_names:
        parts.append(f"Metric(s) detected in query: {', '.join(metric_names)}")
    else:
        parts.append("No specific metric detected in query — showing all metrics.")

    if range_note:
        parts.append(range_note)

    parts.append(f"\nData fields: week, metric, current, previous, deviation (%), "
                 f"churn_current, churn_previous, churn_deviation (%)")
    parts.append(f"Total rows matching query: {len(rows)}")

    if rows:
        # Cap at 100 rows to avoid token overload
        display_rows = rows[:100]
        parts.append(f"\n--- DATA ({len(display_rows)} rows) ---")
        for r in display_rows:
            parts.append(
                f"Week: {r['week']} | Metric: {r['metric']} | "
                f"Current: {r.get('current', 'N/A'):,} | "
                f"Previous: {r.get('previous', 'N/A'):,} | "
                f"Deviation: {r.get('deviation', 'N/A')}% | "
                f"Churn Current: {r.get('churn_current', 'N/A')} | "
                f"Churn Previous: {r.get('churn_previous', 'N/A')} | "
                f"Churn Deviation: {r.get('churn_deviation', 'N/A')}%"
            )
        if len(rows) > 100:
            parts.append(f"... ({len(rows) - 100} more rows truncated)")
    else:
        parts.append("\nNo matching data rows found.")

    parts.append("=== END DATA CONTEXT ===")

    return "\n".join(parts)


def build_ai_prompt(query: str, data_context: str) -> str:
    """
    Build the full prompt to send to the AI, combining the user's question
    with the data context and instructions.
    """
    return (
        "You are NED (Neural Executive Dashboard), a data analyst assistant. "
        "You have access to weekly metric data from the dashboard. "
        "Answer the user's question based on the data provided below. "
        "Be specific — use actual numbers, weeks, and percentages from the data. "
        "If the data doesn't contain what's needed to answer, say so clearly. "
        "Keep your response concise and focused.\n\n"
        f"{data_context}\n\n"
        f"User's question: {query}"
    )
