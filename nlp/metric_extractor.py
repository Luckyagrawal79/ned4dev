"""
Query parser that extracts build range, metric, and asset from a user query.

Search funnel:
  ① build_number (date/range) — handled by date_range_parser
  ② metric name             — resolved here via asset_resolver
  ③ asset name              — resolved here via asset_resolver
"""

from nlp.asset_resolver import AssetResolver


def parse_query_filters(query, resolver: AssetResolver):
    """
    Extract metric and asset from a query string using the asset resolver.

    Returns:
        dict with:
          - metric: resolved metric dict (match, confident, suggestions)
          - asset:  resolved asset dict  (match, confident, suggestions)
    """
    metric_result = resolver.resolve_metric(query)
    asset_result = resolver.resolve_asset(query)
    return {"metric": metric_result, "asset": asset_result}


def extract_metric_from_query(q, build_data=None):
    """
    Legacy wrapper — still used by charts and main.py.
    Returns list of matched metric names for backwards compat.
    """
    if not build_data:
        return []

    all_metrics = set()
    all_assets = set()
    for _, rows in build_data.items():
        for row in rows:
            all_metrics.add(row["metric"])
            if row.get("asset"):
                all_assets.add(row["asset"])

    q_lower = q.lower()

    ignore_words = [
        "plot", "trend", "chart", "graph", "pie", "bar", "barchart",
        "show", "display", "the", "for", "and", "current", "previous",
        "deviation", "past", "last", "builds", "build_number",
    ]

    # Check for asset name matches first — return all metrics for that asset
    for asset in all_assets:
        if asset.lower() in q_lower:
            return [{"type": "asset_filter", "asset": asset, "metrics": list(all_metrics)}]

    # Check for metric name matches
    matched = []
    for metric in all_metrics:
        metric_lower = metric.lower()
        for word in q_lower.split():
            if len(word) > 3 and word not in ignore_words and word in metric_lower:
                matched.append(metric)
                break

    if matched:
        return matched

    # Fuzzy fallback
    from difflib import SequenceMatcher

    best_metric = None
    best_score = 0
    for metric in all_metrics:
        metric_words = metric.lower().replace("-", " ").split()
        for q_word in q_lower.split():
            if len(q_word) <= 3 or q_word in ignore_words:
                continue
            for m_word in metric_words:
                score = SequenceMatcher(None, q_word, m_word).ratio()
                if score > best_score:
                    best_score = score
                    best_metric = metric

    if best_metric and best_score >= 0.8:
        return [best_metric]
    elif best_metric and best_score >= 0.6:
        return [{"suggestion": best_metric, "score": best_score, "all_metrics": list(all_metrics)}]

    return []
