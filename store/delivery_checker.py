"""
Check GCP Dataproc job status for delivery jobs.
Uses gcloud CLI — no extra pip dependencies needed.
"""

import subprocess
import json
from datetime import datetime, timedelta


DELIVERY_JOBS = {
    "OF-Weekly Files Delivery": {
        "prefix": "of-wkly-delivery",
        "schedule": "weekly",
    },
    "OF-Monthly Files Delivery": {
        "prefix": "of-monthly-delivery",
        "schedule": "monthly",
    },
    "Mig- Marketing Extracts Delivery": {
        "prefix": "lighthouse-delivery",
        "schedule": "weekly",
    },
}


def _run_gcloud(prefix: str, project_id: str) -> dict | None:
    """Find most recent successful job matching the prefix."""
    cmd = [
        "gcloud", "dataproc", "jobs", "list",
        f"--project={project_id}",
        "--state-filter=done",
        f"--filter=reference.job_id:{prefix}",
        "--sort-by=~status.stateStartTime",
        "--limit=1",
        "--format=json",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr.strip()}

        jobs = json.loads(result.stdout)
        if not jobs:
            return None

        return jobs[0]
    except Exception as e:
        return {"error": str(e)}


def check_delivery_status(project_id: str) -> list[dict]:
    """Check latest successful run for each delivery job."""
    results = []
    today = datetime.utcnow().date()

    for display_name, config in DELIVERY_JOBS.items():
        prefix = config["prefix"]
        schedule = config["schedule"]

        job = _run_gcloud(prefix, project_id)

        if job is None:
            results.append({
                "job": display_name,
                "last_delivered": "No runs found",
                "on_time": False,
            })
            continue

        if "error" in job:
            results.append({
                "job": display_name,
                "last_delivered": f"Error: {job['error'][:50]}",
                "on_time": False,
            })
            continue

        # Extract end time
        try:
            state_time = job.get("status", {}).get("stateStartTime", "")
            job_date = datetime.fromisoformat(state_time.replace("Z", "+00:00")).date()

            if schedule == "weekly":
                on_time = (today - job_date) <= timedelta(days=7)
            else:
                on_time = (today - job_date) <= timedelta(days=31)

            results.append({
                "job": display_name,
                "last_delivered": job_date.strftime("%Y-%m-%d"),
                "on_time": on_time,
            })
        except Exception as e:
            results.append({
                "job": display_name,
                "last_delivered": f"Parse error: {str(e)[:50]}",
                "on_time": False,
            })

    return results


def format_delivery_status(results: list[dict]) -> str:
    msg = "**🚚 Delivery Status**\n\n"
    msg += "| Job | Last Delivered | On Time |\n"
    msg += "|-----|---------------|----------|\n"
    for r in results:
        tick = "✅" if r["on_time"] else "❌"
        msg += f"| {r['job']} | {r['last_delivered']} | {tick} |\n"
    return msg