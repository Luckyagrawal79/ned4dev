import json
import os
from collections import defaultdict
from urllib.parse import urlparse

try:
    from google.cloud import storage  # type: ignore
except ImportError:
    storage = None


class JSONMetricStore:
    """
    Metric store that reads JSON data from local file/directory or GCS.
    Handles Spark output directories with part files and _SUCCESS markers.

    Configuration precedence:
    - Explicit `gcs_uri` argument
    - `DATA_STORE_GCS_URI` environment variable
    - Fallback to local `path`
    """

    def __init__(
        self,
        path: str = "data/data_store.json",
        gcs_uri: str | None = None,
    ):
        self.local_path = path
        self.gcs_uri = gcs_uri or os.getenv("DATA_STORE_GCS_URI")

    def _load_from_local(self):
        """Load from a single JSON file or a directory of Spark JSON part files."""
        if os.path.isdir(self.local_path):
            return self._read_json_parts_local(self.local_path)
        with open(self.local_path, "r") as f:
            return json.load(f)

    def _read_json_parts_local(self, directory):
        """Read all JSON part files from a directory, skip _SUCCESS and other markers."""
        all_rows = []
        for filename in sorted(os.listdir(directory)):
            if filename.startswith("_") or not filename.endswith(".json"):
                continue
            filepath = os.path.join(directory, filename)
            with open(filepath, "r") as f:
                content = f.read().strip()
                if not content:
                    continue
                # Spark JSON can be newline-delimited (one JSON object per line)
                # or a standard JSON array
                if content.startswith("["):
                    all_rows.extend(json.loads(content))
                else:
                    for line in content.splitlines():
                        line = line.strip()
                        if line:
                            all_rows.append(json.loads(line))
        print(f"DEBUG >> Loaded {len(all_rows)} rows from {len(os.listdir(directory))} files in {directory}")
        return all_rows

    def _load_from_gcs(self):
        if storage is None:
            raise RuntimeError(
                "google-cloud-storage is required. "
                "Install with: pip install google-cloud-storage"
            )
        parsed = urlparse(self.gcs_uri)
        if parsed.scheme != "gs" or not parsed.netloc or not parsed.path:
            raise ValueError(f"Invalid GCS URI '{self.gcs_uri}'.")

        client = storage.Client()
        bucket = client.bucket(parsed.netloc)
        prefix = parsed.path.lstrip("/")

        # Check if it's a single file or a directory
        blob = bucket.blob(prefix)
        if blob.exists():
            # Single file — load directly
            return json.loads(blob.download_as_bytes().decode("utf-8"))

        # Directory — list all part files under the prefix
        return self._read_json_parts_gcs(bucket, prefix)

    def _read_json_parts_gcs(self, bucket, prefix):
        """Read all JSON part files from a GCS directory prefix."""
        if not prefix.endswith("/"):
            prefix += "/"

        all_rows = []
        blobs = list(bucket.list_blobs(prefix=prefix))
        json_blobs = [
            b for b in blobs
            if b.name.endswith(".json") and not b.name.split("/")[-1].startswith("_")
        ]

        for blob in sorted(json_blobs, key=lambda b: b.name):
            content = blob.download_as_bytes().decode("utf-8").strip()
            if not content:
                continue
            # Handle both JSON arrays and newline-delimited JSON (Spark default)
            if content.startswith("["):
                all_rows.extend(json.loads(content))
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        all_rows.append(json.loads(line))

        print(f"DEBUG >> Loaded {len(all_rows)} rows from {len(json_blobs)} part files in gs://.../{prefix}")
        return all_rows

    def load(self):
        if self.gcs_uri:
            return self._load_from_gcs()
        return self._load_from_local()

    # ── Grouping helpers ──────────────────────────────────────────────

    def group_by_build(self):
        data = self.load()
        grouped = defaultdict(list)
        for row in data:
            grouped[row["build_number"]].append(row)
        return dict(grouped)

    def get_build(self, build_number):
        return self.group_by_build().get(build_number, [])

    def group_by_asset(self):
        data = self.load()
        grouped = defaultdict(list)
        for row in data:
            grouped[row.get("asset", "")].append(row)
        return dict(grouped)

    def group_by_metric(self):
        data = self.load()
        grouped = defaultdict(list)
        for row in data:
            grouped[row["metric"]].append(row)
        return dict(grouped)

    def get_unique_assets(self):
        data = self.load()
        return sorted(set(r.get("asset", "") for r in data if r.get("asset")))

    def get_unique_metrics(self):
        data = self.load()
        return sorted(set(r["metric"] for r in data))

    # ── Filtered query ────────────────────────────────────────────────

    def query(self, build_number=None, metric=None, asset=None):
        """
        Filter data by any combination of build_number, metric, asset.
        All filters are optional — omit to skip that filter.
        """
        data = self.load()
        if build_number:
            data = [r for r in data if r["build_number"] == build_number]
        if metric:
            data = [r for r in data if r["metric"].lower() == metric.lower()]
        if asset:
            data = [r for r in data if r.get("asset", "").lower() == asset.lower()]
        return data