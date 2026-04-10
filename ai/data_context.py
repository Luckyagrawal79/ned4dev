"""
Build rich data context for AI queries.

Search funnel: build_number → metric → asset
Extracts relevant rows and formats them for Gemini/Claude/OpenAI.
"""

import json
from nlp.asset_resolver import AssetResolver
from nlp.date_range_parser import parse_date_range, filter_builds_by_range


def build_data_context(query: str, build_data: dict, selected_build: str, resolver: AssetResolver = None) -> str:
    """
    Analyze query, extract relevant data via the funnel, and build context string.
    """
    all_builds = sorted(build_data.keys())
    if not all_builds:
        return "No data available."

    # ── Step 1: Parse build range ─────────────────────────────────────
    date_range = parse_date_range(query, latest_build=all_builds[-1])
    builds_to_use = all_builds
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
            range_note = f"No data for {requested_label}. Available: {all_builds[0]} to {all_builds[-1]}."

    # ── Step 2: Parse metric ──────────────────────────────────────────
    metric_filter = None
    asset_filter = None

    if resolver:
        metric_result = resolver.resolve_metric(query)
        if metric_result["match"]:
            metric_filter = metric_result["match"]

        asset_result = resolver.resolve_asset(query)
        if asset_result["match"]:
            asset_filter = asset_result["match"]

    # ── Step 3: Filter rows through the funnel ────────────────────────
    rows = []
    for build in builds_to_use:
        for row in build_data.get(build, []):
            if metric_filter and metric_filter.lower() not in row["metric"].lower():
                continue
            if asset_filter and asset_filter.lower() != row.get("asset", "").lower():
                continue
            rows.append(row)

    # ── Step 4: Build context string ──────────────────────────────────
    parts = []
    parts.append("=== NED DASHBOARD DATA CONTEXT ===")
    parts.append(f"Currently selected build: {selected_build}")
    parts.append(f"Data range: {all_builds[0]} to {all_builds[-1]} ({len(all_builds)} builds)")

    all_metric_names = sorted(set(
        row["metric"] for b in all_builds for row in build_data.get(b, [])
    ))
    all_asset_names = sorted(set(
        row.get("asset", "") for b in all_builds for row in build_data.get(b, []) if row.get("asset")
    ))

    parts.append(f"Available metrics: {', '.join(all_metric_names)}")
    parts.append(f"Available assets: {', '.join(all_asset_names)}")

    if metric_filter:
        parts.append(f"Metric filter: {metric_filter}")
    if asset_filter:
        parts.append(f"Asset filter: {asset_filter}")
    if range_note:
        parts.append(range_note)

    parts.append(f"\nData fields: build_number, metric, asset, current, previous, deviation (%)")
    parts.append(f"Total rows matching: {len(rows)}")

    if rows:
        display_rows = rows[:100]
        parts.append(f"\n--- DATA ({len(display_rows)} rows) ---")
        for r in display_rows:
            parts.append(
                f"Build: {r['build_number']} | Metric: {r['metric']} | "
                f"Asset: {r.get('asset', '-')} | "
                f"Current: {r.get('current', 'N/A'):,} | "
                f"Previous: {r.get('previous', 'N/A'):,} | "
                f"Deviation: {r.get('deviation', 'N/A')}%"
            )
        if len(rows) > 100:
            parts.append(f"... ({len(rows) - 100} more rows truncated)")
    else:
        parts.append("\nNo matching data rows found.")

    parts.append("=== END DATA CONTEXT ===")
    return "\n".join(parts)


def build_ai_prompt(query: str, data_context: str) -> str:
    return (
        "You are NED (Neural Executive Dashboard), a data analyst assistant. "
        "You have access to build metric data from the dashboard. "
        "Data has: build_number (date), metric (what is measured), asset (partner/source). "
        "Answer using actual numbers, builds, and percentages from the data. "
        "If the data doesn't contain what's needed, say so clearly. "
        "Keep your response concise and focused.\n\n"
        f"{data_context}\n\n"
        f"User's question: {query}"
    )
