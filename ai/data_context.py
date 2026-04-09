"""
Build rich data context for AI queries.

Extracts relevant metric rows based on the user's query (metric name + date range)
and formats them into a clear context string that can be sent to Gemini/Claude/OpenAI
so the AI can answer data questions accurately.
"""

import json
from nlp.metric_extractor import extract_metric_from_query
from nlp.date_range_parser import parse_date_range, filter_builds_by_range


def build_data_context(query: str, build_data: dict, selected_build: str) -> str:
    """
    Analyze the user's query, extract relevant data, and build a context string
    that gives the AI everything it needs to answer.

    Args:
        query: The user's raw question
        build_data: Full build data dict {week_key: [rows...]}
        selected_build: Currently selected week in the UI

    Returns:
        A formatted context string with actual data rows.
    """
    all_builds = sorted(build_data.keys())

    # --- 1. Try to detect which metric(s) the user is asking about ---
    metrics_found = extract_metric_from_query(query, build_data)

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
    date_range = parse_date_range(query, latest_build=all_builds[-1] if all_builds else None)
    builds_to_use = all_builds  # default: all weeks

    range_note = ""
    if date_range:
        filtered = filter_builds_by_range(all_builds, date_range["start_date"], date_range["end_date"])
        requested_label = (
            f"{date_range['start_month_name']} {date_range['start_year']}"
            f" to {date_range['end_month_name']} {date_range['end_year']}"
        )
        if filtered:
            builds_to_use = filtered
            range_note = f"Showing data for: {requested_label} ({len(filtered)} builds)"
        else:
            range_note = (
                f"No data found for {requested_label}. "
                f"Available data spans {all_builds[0]} to {all_builds[-1]}."
            )
            # Still use all weeks so AI has some context
            builds_to_use = all_builds

    # --- 3. Extract matching rows ---
    rows = []
    for build in builds_to_use:
        build_metrics = build_data.get(build, [])
        for row in build_metrics:
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
    parts.append(f"Currently selected build in UI: {selected_build}")
    parts.append(f"Total data range: {all_builds[0]} to {all_builds[-1]} ({len(all_builds)} builds)")

    # All unique metric names in the data
    all_metric_names = sorted(set(
        row["metric"] for wk in all_builds for row in build_data.get(wk, [])
    ))
    parts.append(f"Available metrics: {', '.join(all_metric_names)}")

    if metric_names:
        parts.append(f"Metric(s) detected in query: {', '.join(metric_names)}")
    else:
        parts.append("No specific metric detected in query — showing all metrics.")

    if range_note:
        parts.append(range_note)

    parts.append(f"\nData fields: build_number, metric, current, previous, deviation (%), "
    parts.append(f"Total rows matching query: {len(rows)}")

    if rows:
        # Cap at 100 rows to avoid token overload
        display_rows = rows[:100]
        parts.append(f"\n--- DATA ({len(display_rows)} rows) ---")
        for r in display_rows:
            parts.append(
                f"Build: {r['build_number']} | Metric: {r['metric']} | "
                f"Current: {r.get('current', 'N/A'):,} | "
                f"Previous: {r.get('previous', 'N/A'):,} | "
                f"Deviation: {r.get('deviation', 'N/A')}% | "
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
        "You have access to build metric data from the dashboard. "
        "Answer the user's question based on the data provided below. "
        "Be specific — use actual numbers, builds, and percentages from the data. "
        "If the data doesn't contain what's needed to answer, say so clearly. "
        "Keep your response concise and focused.\n\n"
        f"{data_context}\n\n"
        f"User's question: {query}"
    )
