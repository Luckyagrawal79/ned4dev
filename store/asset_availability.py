"""
Check asset data availability in GCS.
Navigates: base_path → highest instance_id → latest obs_date
"""

from google.cloud import storage

# Map asset name → GCS base path
ASSET_PATHS = {
    "truedata": "gs://fe8f7b53-6cab-4a29-8efa-831ed8849353-2183-a/version=300/",
    "adadvisor": "gs://a6c6cfa9-9556-4504-8d31-dcd47d5aaa8a-2499-a/version=2200/",
    "truedata-ctv": "gs://4980a90f-a83b-4565-bce5-dabd5cd38339-2652-a/version=900/",
    "identity_event": "gs://927bbfd7-25b4-4ac6-8a0c-a05606c89d47-2525-a/version=1100/",
    "liv": "gs://457bb09e-1849-4683-81ac-989ca9ec29da-6252-a/version=100/",
    "gry": "gs://7e846dd6-16a9-4bab-af56-f639a3f8f383-2516-a/version=900/",
    "audacq": "gs://54fdbe34-9fa9-4262-8110-de5fba26b4ea-3775-a/version=100/",
}

# Assets to hide from user-facing list (internal/aggregate assets)
HIDDEN_ASSETS = {"Total", "Total_Cookie", "Total_Device", "Total_cookie", "total", "total_device", "total_cookie"}


def get_visible_assets():
    """Return asset names excluding hidden ones."""
    return sorted(k for k in ASSET_PATHS.keys() if k not in HIDDEN_ASSETS)


def _parse_gs_uri(uri):
    uri = uri.replace("gs://", "")
    parts = uri.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _list_prefixes(client, bucket_name, prefix):
    if not prefix.endswith("/"):
        prefix += "/"
    blobs = client.list_blobs(bucket_name, prefix=prefix, delimiter="/")
    _ = list(blobs)
    return list(blobs.prefixes)


def _get_latest_obs_date(client, bucket_name, base_prefix):
    # Step 1: List instance_id folders
    instance_dirs = _list_prefixes(client, bucket_name, base_prefix)
    if not instance_dirs:
        return None

    instances = []
    for d in instance_dirs:
        folder_name = d.rstrip("/").split("/")[-1]
        if "=" in folder_name:
            val = folder_name.split("=", 1)[1]
            try:
                instances.append((int(val), d))
            except ValueError:
                instances.append((0, d))
        else:
            instances.append((0, d))

    if not instances:
        return None

    instances.sort(key=lambda x: x[0], reverse=True)
    highest_instance_prefix = instances[0][1]

    # Step 2: List obs_date folders under highest instance
    obs_dirs = _list_prefixes(client, bucket_name, highest_instance_prefix)
    if not obs_dirs:
        return None

    dates = []
    for d in obs_dirs:
        folder_name = d.rstrip("/").split("/")[-1]
        if "=" in folder_name:
            val = folder_name.split("=", 1)[1]
            dates.append(val)
        else:
            dates.append(folder_name)

    if not dates:
        return None

    dates.sort(reverse=True)
    return dates[0]


def check_asset_availability(asset_names: list[str]) -> dict:
    """
    Returns dict with:
        - "found": list of {"asset": ..., "last_available": ...}
        - "not_mapped": list of asset names with no path mapping
    """
    client = storage.Client()

    if asset_names[0].lower() in ["all", "all-asset", "all assets"]:
        assets_to_check = get_visible_assets()
    else:
        assets_to_check = [a.strip() for a in asset_names if a.strip()]

    found = []
    not_mapped = []

    for asset in assets_to_check:
        asset_lower = asset.lower().strip()

        # Skip hidden assets
        if asset_lower in {h.lower() for h in HIDDEN_ASSETS}:
            continue

        # Find matching path
        gs_path = ASSET_PATHS.get(asset_lower)
        if not gs_path:
            # Try fuzzy match
            matched = False
            for key in ASSET_PATHS:
                if asset_lower in key or key in asset_lower:
                    gs_path = ASSET_PATHS[key]
                    asset_lower = key
                    matched = True
                    break
            if not matched:
                not_mapped.append(asset)
                continue

        try:
            bucket_name, prefix = _parse_gs_uri(gs_path)
            latest_date = _get_latest_obs_date(client, bucket_name, prefix)
            found.append({
                "asset": asset_lower,
                "last_available": latest_date if latest_date else "No data found",
            })
        except Exception as e:
            found.append({
                "asset": asset_lower,
                "last_available": f"Error: {str(e)[:60]}",
            })

    return {"found": found, "not_mapped": not_mapped}


def format_availability(result: dict) -> str:
    found = result["found"]
    not_mapped = result["not_mapped"]

    msg = "**🔍 Asset Availability**\n\n"

    if found:
        msg += "| Asset | Last Available |\n"
        msg += "|-------|---------------|\n"
        for r in found:
            msg += f"| {r['asset']} | {r['last_available']} |\n"

    if not_mapped:
        msg += f"\n⚠️ Unable to find mapping for: {', '.join(f'`{a}`' for a in not_mapped)}\n"

    if not found and not not_mapped:
        msg += "No assets to check.\n"

    return msg