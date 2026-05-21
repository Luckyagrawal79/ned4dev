"""
Checks for version changes in GCS asset paths.
Sends email alert when version changes.
Run as cron inside Docker.
"""

import redis
import threading
import time
from datetime import datetime
from google.cloud import storage
from store.asset_availability import ASSET_PATHS, _parse_gs_uri, _list_prefixes, _sort_key
from store.email_sender import send_email, TEAM_EMAILS

REDIS_HOST = "10.117.65.11"
REDIS_PORT = 6379
REDIS_HASH = "ASSET_VERSIONS"
CHECK_INTERVAL_HOURS = 48  # every 2 days


def _get_latest_version(client, bucket_name, base_prefix):
    """List versions at base path, return highest numeric one."""
    folders = _list_prefixes(client, bucket_name, base_prefix)
    if not folders:
        return None

    versions = []
    for d in folders:
        folder = d.rstrip("/").split("/")[-1]
        if "=" in folder:
            val = folder.split("=", 1)[1]
        else:
            val = folder
        num = _sort_key(val)
        if num is not None:
            versions.append((num, folder, d))

    if not versions:
        return None

    versions.sort(key=lambda x: x[0], reverse=True)
    return versions[0][1]  # return the folder name like "version=1100"


def check_all_versions():
    """Check all assets for version changes. Send email if any changed."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    gcs_client = storage.Client()

    changes = []

    for key, config in ASSET_PATHS.items():
        gs_path = config["path"]
        display = config["display"]

        try:
            bucket_name, prefix = _parse_gs_uri(gs_path)
            current_version = _get_latest_version(gcs_client, bucket_name, prefix)

            if not current_version:
                continue

            # Get stored version from Redis
            stored_version = r.hget(REDIS_HASH, key)

            if stored_version is None:
                # First run — store it, no email
                r.hset(REDIS_HASH, key, current_version)
                print(f"[VERSION] Stored initial: {display} = {current_version}")
            elif stored_version != current_version:
                # Version changed!
                changes.append({
                    "asset": display,
                    "old_version": stored_version,
                    "new_version": current_version,
                })
                r.hset(REDIS_HASH, key, current_version)
                print(f"[VERSION] Changed: {display} {stored_version} → {current_version}")
            else:
                print(f"[VERSION] No change: {display} = {current_version}")

        except Exception as e:
            print(f"[VERSION] Error checking {display}: {e}")

    # Send email if any changes
    if changes:
        _send_version_alert(changes)
    else:
        print(f"[VERSION] No version changes detected at {datetime.utcnow()}")


def _send_version_alert(changes):
    """Send HTML email about version changes."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    rows = ""
    for c in changes:
        rows += f"""
        <tr>
            <td style="padding:8px; border:1px solid #ddd;">{c['asset']}</td>
            <td style="padding:8px; border:1px solid #ddd;">{c['old_version']}</td>
            <td style="padding:8px; border:1px solid #ddd; color: #d32f2f; font-weight:bold;">{c['new_version']}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family: Arial, sans-serif;">
    <div style="background: #00A2D1; padding: 15px 20px; color: white;">
        <h2 style="margin:0;">⚠️ NED — Asset Version Change Alert</h2>
        <p style="margin:4px 0 0 0; font-size:13px;">{today}</p>
    </div>
    <div style="padding: 20px;">
        <p>Hi All,</p>
        <p>The following asset versions have changed in OneTru:</p>
        <table style="border-collapse: collapse; margin: 15px 0;">
            <tr style="background: #00A2D1; color: white;">
                <th style="padding:8px; border:1px solid #ddd;">Asset</th>
                <th style="padding:8px; border:1px solid #ddd;">Old Version</th>
                <th style="padding:8px; border:1px solid #ddd;">New Version</th>
            </tr>
            {rows}
        </table>
        <p>Please update the production code accordingly.</p>
        <br>
        <p>Thanks,<br><b>NED</b><br>
        <span style="font-size:12px; color:#888;">Neural Executive Dashboard — OneTru Identity & Data Services</span></p>
    </div>
    </body></html>
    """

    result = send_email(
        to=TEAM_EMAILS,
        subject=f"⚠️ NED — Asset Version Change Alert : {today}",
        body_html=html,
        important=True,
    )
    print(f"[VERSION] Email sent: {result}")


def start_version_checker():
    """Start background thread that checks versions every 48 hours."""
    def _loop():
        while True:
            try:
                print(f"[VERSION] Running check at {datetime.utcnow()}")
                check_all_versions()
            except Exception as e:
                print(f"[VERSION] Error in check loop: {e}")
            time.sleep(CHECK_INTERVAL_HOURS * 3600)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print(f"[VERSION] Background checker started (every {CHECK_INTERVAL_HOURS}h)")