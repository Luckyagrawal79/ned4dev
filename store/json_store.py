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
    Metric store that reads JSON data from local file or GCS.

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
        with open(self.local_path, "r") as f:
            return json.load(f)

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
        blob = bucket.blob(parsed.path.lstrip("/"))
        return json.loads(blob.download_as_bytes().decode("utf-8"))

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
