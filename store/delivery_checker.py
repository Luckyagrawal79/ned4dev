import redis
from datetime import datetime, timedelta

REDIS_HOST = "10.117.65.11"
REDIS_PORT = 6379

DELIVERY_KEYS = {
    "MARKETING_EXTRACTS_DELIVERY": {"display": "Marketing Extracts Delivery", "cadence": "weekly"},
    "OF_FULLFILLMENT_DELIVERY": {"display": "OF Fullfillment Delivery", "cadence": "weekly"},
    "IP_MONTHLY_DELIVERY": {"display": "IP Monthly Delivery", "cadence": "monthly"},
}


def _get_expected_date(cadence, today):
    """
    Weekly: last Friday (or today if today is Friday)
    Monthly: 15th of current month if today >= 15, else 15th of previous month
    """
    if cadence == "weekly":
        # Friday = weekday 4
        days_since_friday = (today.weekday() - 4) % 7
        return today - timedelta(days=days_since_friday)
    else:
        # Monthly — 15th logic
        if today.day >= 15:
            return today.replace(day=15)
        else:
            # 15th of previous month
            first_of_month = today.replace(day=1)
            last_month = first_of_month - timedelta(days=1)
            return last_month.replace(day=15)


def check_delivery_status() -> list[dict]:
    today = datetime.utcnow().date()
    results = []

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        return [{"metric": "Redis", "cadence": "-", "expected": "-", "last_delivered": f"Connection error: {str(e)[:60]}"}]

    for key, config in DELIVERY_KEYS.items():
        try:
            val = r.hget("DELIVERY", key)
            expected = _get_expected_date(config["cadence"], today).strftime("%Y-%m-%d")
            results.append({
                "metric": config["display"],
                "cadence": config["cadence"].capitalize(),
                "expected": expected,
                "last_delivered": val.strip() if val else "No data",
            })
        except Exception as e:
            results.append({
                "metric": config["display"],
                "cadence": config["cadence"].capitalize(),
                "expected": "-",
                "last_delivered": f"Error: {str(e)[:60]}",
            })

    return results


def format_delivery_status(results: list[dict]) -> str:
    msg = "**🚚 Delivery Status**\n\n"
    msg += "| Metric | Cadence | Expected Delivery | Last Delivery |\n"
    msg += "|--------|---------|-------------------|---------------|\n"
    for r in results:
        msg += f"| {r['metric']} | {r['cadence']} | {r['expected']} | {r['last_delivered']} |\n"
    return msg