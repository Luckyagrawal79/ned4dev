from difflib import SequenceMatcher


def extract_metric_from_query(q, build_data=None):
    # Dynamically match query words against actual metric names in the data.
    # Falls back to hardcoded list if no data is passed.
    q_lower = q.lower()

    # Remove common chart/plot words so they don't accidentally match metric names
    ignore_words = ['plot', 'trend', 'chart', 'graph', 'pie', 'bar', 'barchart',
                    'show', 'display', 'the', 'for', 'and', 'current', 'previous',
                    'deviation', 
                    'past', 'last', 'builds', 'build_number']

    if build_data:
        # Get all unique metric names from the data
        all_metrics = set()
        for week, rows in build_data.items():
            for row in rows:
                all_metrics.add(row["metric"])

        # Step 1: Exact substring match
        matched = []
        for metric in all_metrics:
            metric_lower = metric.lower()
            for word in q_lower.split():
                if len(word) > 3 and word not in ignore_words and word in metric_lower:
                    matched.append(metric)
                    break

        if matched:
            return matched

        # Step 2: Fuzzy match — check each query word against metric name words
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
            # High confidence
            return [best_metric]
        elif best_metric and best_score >= 0.6:
            # Low confidence — return with suggestion flag
            return [{"suggestion": best_metric, "score": best_score, "all_metrics": list(all_metrics)}]

    # Fallback: hardcoded keywords
    metrics = []
    for m in ['maid', 'gravy', 'cookie', 'dig', 'liveintent']:
        if m in q_lower:
            metrics.append(m.capitalize())
    return metrics