"""
Check asset data availability in GCS.
Navigates: base_path → highest instance_id → latest obs_date
"""

from google.cloud import storage

# Map asset name → GCS base path
ASSET_PATHS = {
    "truedata": {
        "path": "gs://fe8f7b53-6cab-4a29-8efa-831ed8849353-2183-a/",
        "display": "Truedata",
        "cadence": "daily",
    },
    "nextglass": {
        "path": "gs://8bfec105-8abc-4af1-9c8d-e4d42cade844-2252-a/",
        "display": "Nextglass",
        "cadence": "monthly",
    },
    "unique_maid_list": {
        "path": "gs://fdaa9419-fd0b-44fa-9584-d060848c4caf-4373-a/",
        "display": "Unique MAID List",
        "cadence": "weekly",
    },
    "ccpa_online": {
        "path": "gs://898cc58e-0bb1-4031-a751-2e1154834da4-2464-s/",
        "display": "CCPA Online",
        "cadence": "monthly",
    },
    "ipi_ipv4": {
        "path": "gs://7395e23a-bb60-41f4-af0d-6754557cb538-2521-a/",
        "display": "IPI IPv4",
        "cadence": "weekly",
    },
    "ibotta": {
        "path": "gs://a255864d-c9e5-41bc-9fc1-ed58b6fa5c3d-2518-a/",
        "display": "Ibotta",
        "cadence": "monthly",
    },
    "startapp": {
        "path": "gs://e9c43575-43c6-49fd-9307-daef4d8ecd01-2571-a/",
        "display": "Startapp",
        "cadence": "daily",
    },
    "zeta": {
        "path": "gs://a48eaa4d-2c47-4938-b75d-205fc7173f6d-2934-a/",
        "display": "Zeta",
        "cadence": "monthly",
    },
    "truedata_ctv_raw": {
        "path": "gs://89e46ed9-b4f0-468f-97a3-80cba59b403b-4934-a/",
        "display": "TrueData CTV Raw",
        "cadence": "weekly",
    },
    "truedata_ctv": {
        "path": "gs://4980a90f-a83b-4565-bce5-dabd5cd38339-2652-a/",
        "display": "Truedata CTV",
        "cadence": "weekly",
    },
    "maf": {
        "path": "gs://05a40216-9391-40f5-a787-8caa68ab9319-2284-a/",
        "display": "MAF",
        "cadence": "monthly",
    },
    "adadvisor": {
        "path": "gs://a6c6cfa9-9556-4504-8d31-dcd47d5aaa8a-2499-a/",
        "display": "AdAdvisor",
        "cadence": "daily",
    },
    "gravy": {
        "path": "gs://7e846dd6-16a9-4bab-af56-f639a3f8f383-2516-a/",
        "display": "Gravy",
        "cadence": "daily",
    },
    "arin_ipv6": {
        "path": "gs://8569d6d0-df9a-4243-b6e1-55b2d19da11e-5450-a/",
        "display": "ARIN IPV6",
        "cadence": "weekly",
    },
    "arin_ipv4": {
        "path": "gs://553c55ca-1b66-46f9-9411-0c979d94ffea-5473-a/",
        "display": "ARIN IPV4",
        "cadence": "weekly",
    },
    "ipi_ipr": {
        "path": "gs://46cda202-9adb-4c76-8578-c4c036bd5a8a-2517-a/",
        "display": "IPI IPR",
        "cadence": "daily",
    },
    "stirista_ctv": {
        "path": "gs://ef07a99f-a4b0-4640-8ee6-2aa8f2c639a8-5139-a/",
        "display": "Stirista CTV",
        "cadence": "daily",
    },
    "kdi": {
        "path": "gs://31fb003f-58c1-4e03-a402-4f4e56eff2d5-2949-a/",
        "display": "KDI",
        "cadence": "monthly",
    },
    "ventive_iq": {
        "path": "gs://648d891a-0fbd-4d10-890c-44afbad09b26-5599-a/",
        "display": "Ventive IQ",
        "cadence": "weekly",
    },
    "liveintent": {
        "path": "gs://457bb09e-1849-4683-81ac-989ca9ec29da-6252-a/",
        "display": "LiveIntent",
        "cadence": "daily",
    },
    "third_party_internal_email": {
        "path": "gs://0d9f08cb-ab81-4524-8765-ad1a21722431-3212-a/",
        "display": "Third Party Internal Email",
        "cadence": "monthly",
    },
    "third_party_internal_phones": {
        "path": "gs://65dfd896-4f6d-4f60-a6e3-edc5d906b4ca-3213-a/",
        "display": "Third Party Internal Phones",
        "cadence": "monthly",
    },
    "third_party_id5_hem": {
        "path": "gs://79f36342-a1a9-4bd9-b14c-8ffeca89fdbb-5379-a/",
        "display": "Third Party ID5 HEM",
        "cadence": "monthly",
    },
    "third_party_ramp_id": {
        "path": "gs://f85d388b-a710-4342-bd8b-484602bbb6c5-5880-a/",
        "display": "Third Party Ramp ID",
        "cadence": "monthly",
    },
    "third_party_tradedesk": {
        "path": "gs://354e9396-3379-4a3e-a567-0ce8b15eb3ed-5216-a/",
        "display": "Third Party TradeDesk",
        "cadence": "bi-weekly",
    },
    "ipi_ipv6": {
        "path": "gs://81e7e936-53e4-4432-b46a-29949eaca4ac-5335-a/",
        "display": "IPI IPV6",
        "cadence": "weekly",
    },
    "ccpa_offline": {
        "path": "gs://1850aac2-fd3d-48e3-b6ac-588cb80389aa-2305-a/",
        "display": "CCPA Offline",
        "cadence": "monthly",
    },
    "positive_ccpa_optout": {
        "path": "gs://7c7d8ec5-8aa2-43a7-81d4-2e51ab2dbe99-5350-a/",
        "display": "Positive CCPA Optout",
        "cadence": "monthly",
    },
    "offline_enl_blend": {
        "path": "gs://450a97d6-9885-4ec6-b7a7-46882570026c-2293-a/",
        "display": "Offline ENL Blend",
        "cadence": "monthly",
    },
    "identity_events": {
        "path": "gs://927bbfd7-25b4-4ac6-8a0c-a05606c89d47-2525-a/",
        "display": "Identity Events",
        "cadence": "daily",
    },
    "offline_enl_phone": {
        "path": "gs://c75a2461-1f69-4f5a-afd2-357577b3ab3c-2310-a/",
        "display": "Offline ENL Phone",
        "cadence": "monthly",
    },
    "ipv4_ipv6_mapping_table": {
        "path": "gs://874b63dd-fd8e-4303-8d72-89aed43bf606-2707-a/",
        "display": "IPV4 IPV6 Mapping Table",
        "cadence": "weekly",
    },
    "offline_email_ekey_pid": {
        "path": "gs://81e41181-68c1-4d83-8295-a6c329226e19-2309-a/",
        "display": "Offline Email Ekey Pid",
        "cadence": "monthly",
    },
    "offline_enl_canonical": {
        "path": "gs://0b6a9808-9df0-4537-80fe-d5afd50c830e-2297-a/",
        "display": "Offline ENL Canonical",
        "cadence": "monthly",
    },
    "offline_enl_ekey_tier": {
        "path": "gs://99effa63-f25e-43a0-a303-4384036e9610-2308-a/",
        "display": "Offline ENL Ekey Tier",
        "cadence": "monthly",
    },
    "audience_acuity": {
        "path": "gs://54fdbe34-9fa9-4262-8110-de5fba26b4ea-3775-a/",
        "display": "Audience Acuity",
        "cadence": "daily",
    },
    "ipi_ipv4_pp": {
        "path": "gs://c2dbcd0e-c11f-4c94-8556-78e31c82e8b1-2981-a/",
        "display": "IPI IPv4 PP",
        "cadence": "weekly",
    },
    "combined_event_cookie": {
        "path": "gs://0d0fe3b2-4b88-4687-a265-ee09e4bbac2e-3401-a/",
        "display": "Combined Event Cookie",
        "cadence": "weekly",
    },
    "combined_event_device": {
        "path": "gs://097b368e-aec2-4f5d-b66c-c9094e4e6c55-3406-a/",
        "display": "Combined Event Device",
        "cadence": "weekly",
    },
    "first_party_cookie": {
        "path": "gs://d832a360-a1e8-4ebb-9125-cd096ce4da3f-3402-a/",
        "display": "First Party Cookie",
        "cadence": "weekly",
    },
    "device_hashed_email": {
        "path": "gs://ea8b8616-0f82-4838-a5ec-8b8abcd01ee6-10327-a/",
        "display": "Device Hashed Email",
        "cadence": "weekly",
    },
    "device_email": {
        "path": "gs://438b1998-a6f1-482f-9ea1-1f698336d0c6-10317-a/",
        "display": "Device Email",
        "cadence": "weekly",
    },
    "high_frequency_emails": {
        "path": "gs://b9f9ea55-3c2d-4e97-bf6c-9e7da23012a7-10318-a/",
        "display": "High Frequency Emails",
        "cadence": "monthly",
    },
    "cookie_hashed_email": {
        "path": "gs://e5c7c686-7705-466c-bac4-68f86e6d9639-10316-a/",
        "display": "Cookie Hashed Email",
        "cadence": "weekly",
    },
    "cookie_email": {
        "path": "gs://bd662e66-9db5-47bd-b997-8d8302535d8a-10313-a/",
        "display": "Cookie Email",
        "cadence": "weekly",
    },
    "canonical_email_ekey_pid_subset": {
        "path": "gs://518bdb03-e488-48cc-9606-a48e9eae2d53-10311-a/",
        "display": "Canonical Email Ekey Pid Subset",
        "cadence": "monthly",
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
    """Sort numerically if possible, else return None to skip."""
    try:
        return int(val)
    except ValueError:
        return None


def _looks_like_date(val):
    """Check if value is a date in any format."""
    import re
    if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
        return True
    if re.match(r'^\d{8}$', val):
        return True
    return False


def _get_latest_obs_date(client, bucket_name, base_prefix):
    """
    Navigates: version → instanceid → obs_date
    At each level: picks only numeric values, ignores text.
    At date level: picks only date-like values, ignores text.
    """
    current_prefix = base_prefix

    for step in range(4):
        folders = _list_prefixes(client, bucket_name, current_prefix)
        if not folders:
            return None

        # Extract values
        entries = []
        for d in folders:
            folder = d.rstrip("/").split("/")[-1]
            val = _extract_value(folder)
            entries.append((val, d))

        if not entries:
            return None

        # Check if this level has dates
        date_entries = []
        for val, path in entries:
            normalized = _normalize_date(val)
            if _looks_like_date(normalized):
                date_entries.append((normalized, path))

        if date_entries:
            # This is the date level — pick latest date, ignore non-dates
            date_entries.sort(key=lambda x: x[0], reverse=True)
            return date_entries[0][0]

        # Not dates — filter to numeric only, pick highest
        numeric_entries = []
        for val, path in entries:
            num = _sort_key(val)
            if num is not None:
                numeric_entries.append((num, path))

        if numeric_entries:
            numeric_entries.sort(key=lambda x: x[0], reverse=True)
            current_prefix = numeric_entries[0][1]
        else:
            # No numeric values found — try first folder anyway
            current_prefix = entries[0][1]

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
            # Try without spaces/dashes
            clean = asset_lower.replace(" ", "").replace("-", "")
            matched = False
            for key in ASSET_PATHS:
                key_clean = key.replace(" ", "").replace("-", "")
                if clean in key_clean or key_clean in clean:
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
                        on_time = (today - latest_date) <= timedelta(days=1)
                    elif cadence == "weekly":
                        on_time = (today - latest_date) <= timedelta(days=7)
                    elif cadence == "bi-weekly":
                        on_time = (today - latest_date) <= timedelta(days=15)
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
        msg += f"\n⚠️ Asset not found: {', '.join(f'`{a}`' for a in not_mapped)}\n"

    if not found and not not_mapped:
        msg += "No assets to check.\n"

    return msg