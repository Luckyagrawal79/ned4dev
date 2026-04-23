"""
Check asset data availability in GCS.
Navigates: base_path → highest instance_id → latest obs_date
"""

from google.cloud import storage

# Map asset name → GCS base path
ASSET_PATHS = {
    "truedata": {
        "path": "gs://fe8f7b53-6cab-4a29-8efa-831ed8849353-2183-a/",
        "display": "TrueData",
        "cadence": "daily",
    },
    "adadvisor": {
        "path": "gs://a6c6cfa9-9556-4504-8d31-dcd47d5aaa8a-2499-a/",
        "display": "AdAdvisor",
        "cadence": "daily",
    },
    "truedata-ctv": {
        "path": "gs://4980a90f-a83b-4565-bce5-dabd5cd38339-2652-a/",
        "display": "TrueData CTV",
        "cadence": "weekly",
    },
    "liv": {
        "path": "gs://457bb09e-1849-4683-81ac-989ca9ec29da-6252-a/",
        "display": "LiveIntent",
        "cadence": "daily",
    },
    "gry": {
        "path": "gs://7e846dd6-16a9-4bab-af56-f639a3f8f383-2516-a/",
        "display": "Gravy",
        "cadence": "daily",
    },
    "audacq": {
        "path": "gs://54fdbe34-9fa9-4262-8110-de5fba26b4ea-3775-a/",
        "display": "Audience Acuity",
        "cadence": "daily",
    },
}

# Assets to hide from user-facing list (internal/aggregate assets)
HIDDEN_ASSETS = {"Total", "Total_Cookie", "Total_Device", "Total_cookie", "total", "total_device", "total_cookie"}

def get_display_to_key_map():
    mapping = {}
    for key, config in ASSET_PATHS.items():
        display = config["display"]
        mapping[display.lower()] = key                                    # "truedata ctv" → key
        mapping[display.lower().replace(" ", "")] = key                   # "truedatactv" → key
        mapping[display.lower().replace(" ", "").replace("-", "")] = key  # "truedatactv" → key
        mapping[key.lower()] = key                                        # "truedata-ctv" → key
        mapping[key.lower().replace("-", "")] = key                       # "truedatactv" → key
    return mapping
    

def get_visible_assets():
    return sorted(k for k in ASSET_PATHS.keys() if k not in {h.lower() for h in HIDDEN_ASSETS})

def get_visible_display_names():
    return {k: v["display"] for k, v in ASSET_PATHS.items() if k not in {h.lower() for h in HIDDEN_ASSETS}}

def _parse_gs_uri(uri):
    uri = uri.replace("gs://", "")
    parts = uri.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _list_prefixes(client, bucket_name, prefix):
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    blobs = client.list_blobs(bucket_name, prefix=prefix or None, delimiter="/")
    _ = list(blobs)
    return list(blobs.prefixes)

def _normalize_date(val):
    """Convert any date format to yyyy-mm-dd. Returns original if not a date."""
    import re
    val = val.strip()
    
    # Already yyyy-mm-dd
    if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
        return val
    
    # yyyymmdd (no dashes)
    if re.match(r'^\d{8}$', val):
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    
    # yyyy/mm/dd
    if re.match(r'^\d{4}/\d{2}/\d{2}$', val):
        return val.replace("/", "-")
    
    # dd-mm-yyyy
    if re.match(r'^\d{2}-\d{2}-\d{4}$', val):
        return f"{val[6:10]}-{val[3:5]}-{val[0:2]}"
    
    # Not a date — return as-is
    return val


def _extract_value(folder_name):
    """Extract value after '=' or return folder name."""
    if "=" in folder_name:
        return folder_name.split("=", 1)[1]
    return folder_name


def _sort_key(val):
    """Sort numerically if possible, else alphabetically."""
    try:
        return (1, int(val))
    except ValueError:
        return (0, val)


def _get_latest_obs_date(client, bucket_name, base_prefix):
    """
    Tries: version → instanceid → date
    Skips any level that doesn't exist.
    """

    def _pick_latest(folders):
        entries = []
        for d in folders:
            folder = d.rstrip("/").split("/")[-1]
            val = _extract_value(folder)
            entries.append((_sort_key(val), _normalize_date(val), d))
        entries.sort(key=lambda x: x[0], reverse=True)
        return entries

    def _looks_like_date(val):
        import re
        return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', val))

    current_prefix = base_prefix

    for step in range(4):  # max 4 levels deep
        folders = _list_prefixes(client, bucket_name, current_prefix)
        if not folders:
            return None

        entries = _pick_latest(folders)

        # Check if this level has dates
        if _looks_like_date(entries[0][1]):
            return entries[0][1]

        # Not dates — go deeper into highest value
        current_prefix = entries[0][2]

    return None



def check_asset_availability(asset_names: list[str]) -> dict:
    client = storage.Client()
    from datetime import datetime, timedelta

    if asset_names[0].lower() in ["all", "all-asset", "all assets"]:
        assets_to_check = get_visible_assets()
    else:
        assets_to_check = [a.strip() for a in asset_names if a.strip()]

    today = datetime.utcnow().date()
    found = []
    not_mapped = []

    for asset in assets_to_check:
        asset_lower = asset.lower().strip()

        if asset_lower in {h.lower() for h in HIDDEN_ASSETS}:
            continue

        config = ASSET_PATHS.get(asset_lower)
        if not config:
            # Try fuzzy match
            matched = False
            for key in ASSET_PATHS:
                if asset_lower in key or key in asset_lower:
                    config = ASSET_PATHS[key]
                    asset_lower = key
                    matched = True
                    break
            if not matched:
                if asset.startswith("__ambiguous__"):
                    parts = asset.replace("__ambiguous__", "").split("||")
                    original = parts[0]
                    options = parts[1:]
                    not_mapped.append(f"{original} (did you mean: {', '.join(options)}?)")
                else:
                    not_mapped.append(asset)

        gs_path = config["path"]
        display = config["display"]
        cadence = config["cadence"]

        try:
            bucket_name, prefix = _parse_gs_uri(gs_path)
            latest_date_str = _get_latest_obs_date(client, bucket_name, prefix)

            if latest_date_str:
                # Check if on time based on cadence
                try:
                    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
                    if cadence == "daily":
                        on_time = (today - latest_date) <= timedelta(days=2)
                    elif cadence == "weekly":
                        on_time = (today - latest_date) <= timedelta(days=7)
                    else:  # monthly
                        on_time = (today - latest_date) <= timedelta(days=31)
                except ValueError:
                    on_time = False  # couldn't parse date

                found.append({
                    "asset": display,
                    "cadence": cadence.capitalize(),
                    "last_available": latest_date_str,
                    "on_time": on_time,
                })
            else:
                found.append({
                    "asset": display,
                    "cadence": cadence.capitalize(),
                    "last_available": "No data found",
                    "on_time": False,
                })

        except Exception as e:
            found.append({
                "asset": display,
                "cadence": cadence.capitalize(),
                "last_available": f"Error: {str(e)[:60]}",
                "on_time": False,
            })

    return {"found": found, "not_mapped": not_mapped}


def format_availability(result: dict) -> str:
    found = result["found"]
    not_mapped = result["not_mapped"]

    msg = "**🔍 Asset Availability**\n\n"

    if found:
        msg += "| Asset | Cadence | Last Available | Up to Date |\n"
        msg += "|-------|---------|---------------|------------|\n"
        for r in found:
            tick = "✅" if r["on_time"] else "❌"
            msg += f"| {r['asset']} | {r['cadence']} | {r['last_available']} | {tick} |\n"

    if not_mapped:
        msg += f"\n⚠️ Unable to find mapping for: {', '.join(f'`{a}`' for a in not_mapped)}\n"

    if not found and not not_mapped:
        msg += "No assets to check.\n"

    return msg