def extract_metric_from_query(q, weekly_data=None):
   
    #Dynamically match query words against actual metric names in the data.
    #Falls back to hardcoded list if no data is passed.
    
    q_lower = q.lower()
    
    # If we have actual data, match against real metric names
    if weekly_data:
        # Get all unique metric names from the data
        all_metrics = set()
        for week, rows in weekly_data.items():
            for row in rows:
                all_metrics.add(row["metric"])
        
        # Check if any word in the query matches part of a metric name
        matched = []
        for metric in all_metrics:
            metric_lower = metric.lower()
            # Check each word in the query against the metric name
            for word in q_lower.split():
                if len(word) >= 3 and word in metric_lower:
                    matched.append(metric)
                    break
        
        if matched:
            return matched
    
    metrics = []
    for m in ['maid','gravy','cookie','dig', 'liveintent']:
        if m in q.lower():
            metrics.append(m.capitalize())
    return metrics
