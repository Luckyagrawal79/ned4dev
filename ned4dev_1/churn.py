def churn_risk(stat):
    return abs(stat['churn_current'] - stat['churn_previous'])
