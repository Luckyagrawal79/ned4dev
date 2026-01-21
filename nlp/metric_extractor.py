def extract_metric_from_query(q):
    metrics = []
    for m in ['maid','gravy','cookie','dig']:
        if m in q.lower():
            metrics.append(m.capitalize())
    return metrics
