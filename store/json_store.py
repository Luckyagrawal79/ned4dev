import json
import os
from collections import defaultdict
from urllib.parse import urlparse

try:
    # Optional dependency – only needed when loading from GCS
    from google.cloud import storage  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    storage = None


class JSONMetricStore:
    """
    Metric store that can read JSON data either from a local file
    (default behaviour) or from a Google Cloud Storage `gs://` URI.

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
        # Allow configuration via explicit argument or environment variable
        self.gcs_uri = gcs_uri or os.getenv("DATA_STORE_GCS_URI")

    def _load_from_local(self):
        with open(self.local_path, "r") as f:
            return json.load(f)

    def _load_from_gcs(self):
        if storage is None:
            raise RuntimeError(
                "google-cloud-storage is required to load data_store.json from GCS. "
                "Install it with `pip install google-cloud-storage`."
            )
        print("DEBUG >> Using GCS URI", self.gcs_uri)
        parsed = urlparse(self.gcs_uri)
        if parsed.scheme != "gs" or not parsed.netloc or not parsed.path:
            raise ValueError(
                f"Invalid GCS URI '{self.gcs_uri}'. Expected format: gs://bucket/path/to/data_store.json"
            )

        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        data_bytes = blob.download_as_bytes()
        return json.loads(data_bytes.decode("utf-8"))

    def load(self):
        # If a GCS URI is configured, prefer that over local file
        if self.gcs_uri:
            return self._load_from_gcs()

        return self._load_from_local()

    def group_by_week(self):
        data = self.load()
        grouped = defaultdict(list)
        for row in data:
            grouped[row["week"]].append(row)
        return dict(grouped)

    def get_week(self, week):
        return self.group_by_week().get(week, [])
