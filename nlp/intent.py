def detect_plot_request(q):
    q = q.lower()
    return any(k in q for k in ['plot', 'trend', 'chart', 'graph', 'pie'])
    
def detect_harness_query(q):
    q = q.lower()
    return any(k in q for k in ['harness','commit','repository','git'])
