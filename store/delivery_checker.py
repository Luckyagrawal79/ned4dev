"""
Check GCP Dataproc job status for delivery jobs.
Uses google-cloud-dataproc Python SDK.
"""

import json
from datetime import datetime, timedelta

try:
    from google.cloud import dataproc_v1
except ImportError:
    dataproc_v1 = None


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


def check_delivery_status(project_id: str, region: str = "us-central1") -> list[dict]:
    if dataproc_v1 is None:
        raise RuntimeError("pip install google-cloud-dataproc")

    client = dataproc_v1.JobControllerClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"}
    )

    results = []
    today = datetime.utcnow().date()

    for display_name, config in DELIVERY_JOBS.items():
        prefix = config["prefix"]
        schedule = config["schedule"]

        try:
            request = dataproc_v1.ListJobsRequest(
                project_id=project_id,
                region=region,
                filter="status.state = DONE",
            )

            latest_date = None
            for job in client.list_jobs(request=request):
                job_id = job.reference.job_id if job.reference else ""
                if not job_id.lower().startswith(prefix.lower()):
                    continue

                if job.status and job.status.state_start_time:
                    job_date = job.status.state_start_time.date()
                    if latest_date is None or job_date > latest_date:
                        latest_date = job_date
                        break  # already sorted by most recent

            if latest_date:
                if schedule == "weekly":
                    on_time = (today - latest_date) <= timedelta(days=7)
                else:
                    on_time = (today - latest_date) <= timedelta(days=31)
                results.append({
                    "job": display_name,
                    "last_delivered": latest_date.strftime("%Y-%m-%d"),
                    "on_time": on_time,
                })
            else:
                results.append({
                    "job": display_name,
                    "last_delivered": "No successful runs",
                    "on_time": False,
                })

        except Exception as e:
            results.append({
                "job": display_name,
                "last_delivered": f"Error: {str(e)[:80]}",
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