import json
import os
from difflib import SequenceMatcher


class AssetResolver:
    """
    Resolves casual asset mentions to actual asset names using
    the auto-built asset registry + fuzzy matching.

    Registry is rebuilt every time new data is synced from Scala.
    """

    def __init__(self, registry_path="data/asset_registry.json"):
        self.registry_path = registry_path
        self._assets = []
        self._metrics = []
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r") as f:
                reg = json.load(f)
            self._assets = reg.get("assets", [])
            self._metrics = reg.get("metrics", [])

    @property
    def assets(self):
        return self._assets

    @property
    def metrics(self):
        return self._metrics

    def rebuild_from_data(self, data):
        """Rebuild registry from the full data list. Called after new data is loaded."""
        self._assets = sorted(set(r.get("asset", "") for r in data if r.get("asset")))
        self._metrics = sorted(set(r["metric"] for r in data))
        registry = {"assets": self._assets, "metrics": self._metrics}
        with open(self.registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def resolve_asset(self, query):
        """
        Try to find an asset name in the query.

        Returns:
            dict with:
              - match: asset name or None
              - confident: bool
              - suggestions: list of possible assets (when not confident)
        """
        q_lower = query.lower()

        ignore_words = [
            "plot", "trend", "chart", "graph", "pie", "bar", "show", "display",
            "the", "for", "and", "current", "previous", "deviation", "past",
            "last", "build", "builds", "data", "metric", "compare", "versus",
        ]

        # Step 1: exact substring match against known assets
        for asset in self._assets:
            if asset.lower() in q_lower:
                return {"match": asset, "confident": True}

        # Step 2: fuzzy match query words against asset names
        query_words = [w for w in q_lower.split() if w not in ignore_words and len(w) > 2]

        best_asset = None
        best_score = 0

        for word in query_words:
            for asset in self._assets:
                # Match against full asset name and individual words
                targets = [asset.lower()] + asset.lower().replace("-", " ").split()
                for target in targets:
                    score = SequenceMatcher(None, word, target).ratio()
                    if score > best_score:
                        best_score = score
                        best_asset = asset

        if best_asset and best_score >= 0.8:
            return {"match": best_asset, "confident": True}
        elif best_asset and best_score >= 0.6:
            return {"match": best_asset, "confident": False, "suggestions": self._assets}

        # No match
        return {"match": None, "confident": True}

    def resolve_metric(self, query):
        """
        Try to find a metric name in the query.

        Returns:
            dict with:
              - match: metric name or None
              - confident: bool
              - suggestions: list of possible metrics (when not confident)
        """
        q_lower = query.lower()

        ignore_words = [
            "plot", "trend", "chart", "graph", "pie", "bar", "show", "display",
            "the", "for", "and", "past", "last", "build", "builds", "data",
            "compare", "versus",
        ]

        # Step 1: exact substring match
        for metric in self._metrics:
            if metric.lower() in q_lower:
                return {"match": metric, "confident": True}

        # Step 2: fuzzy match
        query_words = [w for w in q_lower.split() if w not in ignore_words and len(w) > 2]

        best_metric = None
        best_score = 0

        for word in query_words:
            for metric in self._metrics:
                targets = [metric.lower()] + metric.lower().replace("-", " ").split()
                for target in targets:
                    score = SequenceMatcher(None, word, target).ratio()
                    if score > best_score:
                        best_score = score
                        best_metric = metric

        if best_metric and best_score >= 0.8:
            return {"match": best_metric, "confident": True}
        elif best_metric and best_score >= 0.6:
            return {"match": best_metric, "confident": False, "suggestions": self._metrics}

        return {"match": None, "confident": True}
