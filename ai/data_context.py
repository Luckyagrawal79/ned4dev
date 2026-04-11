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
    import re
    q_lower = query.lower()
    builds_to_use = all_builds
    range_note = ""
    skip_date_parse = False

    # Handle "last N weeks/builds" patterns
    n_match = re.search(r'(?:last|past|recent)\s+(\d+)\s+(?:weeks?|builds?)', q_lower)
    if n_match:
        n = int(n_match.group(1))
        builds_to_use = all_builds[-n:]
        range_note = f"Showing last {n} builds: {builds_to_use[0]} to {builds_to_use[-1]}"
        skip_date_parse = True
    elif any(phrase in q_lower for phrase in ["last week", "latest week", "this week", "recent week", "last build", "latest build", "current build", "current week"]):
        builds_to_use = [all_builds[-1]]
        range_note = f"Showing latest build only: {all_builds[-1]}"
        skip_date_parse = True

    if not skip_date_parse:
        date_range = parse_date_range(query, latest_build=all_builds[-1] if all_builds else None)
    else:
        date_range = None

    

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
        asset_result = resolver.resolve_asset(query)

        # If a word matches both metric and asset, prefer metric
        if metric_result["match"] and metric_result["confident"]:
            metric_filter = metric_result["match"]
            # Don't also filter by asset if the same word triggered both
            if asset_result["match"] and asset_result["confident"]:
                if asset_result["match"].lower() not in metric_filter.lower():
                    asset_filter = asset_result["match"]
        elif asset_result["match"] and asset_result["confident"]:
            asset_filter = asset_result["match"]

    # if resolver:
    #     metric_result = resolver.resolve_metric(query)
    #     if metric_result["match"]:
    #         metric_filter = metric_result["match"]

    #     asset_result = resolver.resolve_asset(query)
    #     if asset_result["match"]:
    #         asset_filter = asset_result["match"]

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
    parts.append(f"Builds included in this response: {', '.join(builds_to_use)}")
    parts.append(f"IMPORTANT: Show data for ALL builds listed above. Do not skip any.")


    all_metric_names = sorted(set(
        row["metric"] for b in all_builds for row in build_data.get(b, [])
    ))
    all_asset_names = sorted(set(
        row.get("asset", "") for b in all_builds for row in build_data.get(b, []) if row.get("asset")
    ))

    parts.append(f"Available metrics: {', '.join(all_metric_names)}")
    parts.append(f"Available assets: {', '.join(all_asset_names)}")

    parts.append(
        "NOTE: Users may refer to assets by informal names. "
        "Match user queries to the closest asset name above. "
        "For example: 'liveintent' could mean 'liv', 'truedata ctv' could mean 'truedata-ctv', "
        "or truedata could just mean 'truedata', etc."
        "Always try to find the closest matching asset before saying data is not available."
    )

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
        "Data has: build_number (date), metric (what is measured), asset (partner/source). "
        "CRITICAL: ONLY use numbers that appear in the data below. "
        "NEVER estimate, round, or make up numbers. Copy exact values from the data rows. "
        "If a value is not in the data, say 'data not available' — do not guess. "
        "When asked to find or filter data, list ALL matching rows. "
        "Match user queries to the closest asset name in the data. "
        "For example: 'liveintent' means 'liv', 'truedata' means 'truedata-ctv'. "
        "\nFORMATTING RULES: "
        "Present data in a clean table or bullet format. "
        "Group by build number. Use bold for headers. "
        "Format it nicely not like wiritng paragraphs"
        "IMPORTANT DATE RULES: "
        "'last week' or 'latest build' = the MOST RECENT build (highest date). "
        "'current week' or 'this week' = the MOST RECENT build. "
        "'last 2 weeks' = the 2 MOST RECENT builds (highest dates). "
        "'last N builds' = the N MOST RECENT builds. "
        "Always pick from the END of the data (newest), not the beginning.\n\n"
        f"{data_context}\n\n"
        f"User's question: {query}"
    )
