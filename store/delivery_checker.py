import redis

REDIS_HOST = "10.117.65.11"
REDIS_PORT = 6379

DELIVERY_KEYS = {
    "MARKETING_EXTRACTS_DELIVERY": {"display": "Marketing Extracts Delivery", "cadence": "weekly"},
    "OF_FULLFILLMENT_DELIVERY": {"display": "OF Fullfillment Delivery", "cadence": "weekly"},
    "IP_MONTHLY_DELIVERY": {"display": "IP Monthly Delivery", "cadence": "monthly"},
}


def check_delivery_status() -> list[dict]:
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    results = []

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        return [{"file": "Redis", "last_delivered": f"Connection error: {str(e)[:60]}", "on_time": False}]

    for key, config in DELIVERY_KEYS.items():
        try:
            val = r.get(key)
            if val:
                results.append({
                    "file": config["display"],
                    "last_delivered": val.strip(),
                    "on_time": _check_on_time(val.strip(), config["cadence"], today),
                })
            else:
                results.append({
                    "file": config["display"],
                    "last_delivered": "No data",
                    "on_time": False,
                })
        except Exception as e:
            results.append({
                "file": config["display"],
                "last_delivered": f"Error: {str(e)[:60]}",
                "on_time": False,
            })

    return results


def _check_on_time(date_str, cadence, today):
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        gap = (today - d).days
        if cadence == "weekly":
            return gap <= 7
        elif cadence == "monthly":
            return gap <= 31
        elif cadence == "daily":
            return gap <= 1
        return False
    except ValueError:
        return False


def format_delivery_status(results: list[dict]) -> str:
    msg = "**🚚 Delivery Status**\n\n"
    msg += "| Files | Last Delivered | On Time |\n"
    msg += "|-------|---------------|---------|\n"
    for r in results:
        tick = "✅" if r["on_time"] else "❌"
        msg += f"| {r['file']} | {r['last_delivered']} | {tick} |\n"
    return msg